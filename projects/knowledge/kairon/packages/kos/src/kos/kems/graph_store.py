"""Versioned, evidence-backed persistence for the KEMS knowledge graph.

The store intentionally uses a small relational schema.  SQLite is the local
implementation; the domain objects and SQL boundaries are portable to the
production PostgreSQL adapter described in the KEMS production plan.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

ReviewState = Literal["machine", "pending", "human_verified", "rejected"]


@dataclass(frozen=True)
class GraphEntity:
    entity_id: str
    entity_type: str
    canonical_name: str
    source_document_id: str
    source_version_id: str
    evidence_span: str
    confidence: float
    review_state: ReviewState = "machine"
    valid_from: str | None = None
    valid_to: str | None = None
    created_by_run: str | None = None


@dataclass(frozen=True)
class GraphRelation:
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    source_document_id: str
    source_version_id: str
    evidence_refs: tuple[str, ...]
    confidence: float
    review_state: ReviewState = "machine"
    valid_from: str | None = None
    valid_to: str | None = None
    created_by_run: str | None = None


@dataclass(frozen=True)
class EvidenceSpan:
    evidence_id: str
    document_id: str
    version_id: str
    locator: str
    quote: str
    extractor: str
    confidence: float
    created_by_run: str | None = None


@dataclass(frozen=True)
class DocumentVersion:
    document_id: str
    version_id: str
    source_sha256: str
    domain: str
    text: str
    sensitivity: str = "internal"
    review_state: ReviewState = "pending"
    run_id: str | None = None


class GraphStore:
    """SQLite graph store with idempotent writes and explicit provenance."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS document_versions (
                    document_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    review_state TEXT NOT NULL,
                    run_id TEXT,
                    PRIMARY KEY (document_id, version_id),
                    UNIQUE (source_sha256)
                );
                CREATE TABLE IF NOT EXISTS evidence_spans (
                    evidence_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    extractor TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    created_by_run TEXT,
                    FOREIGN KEY (document_id, version_id)
                        REFERENCES document_versions(document_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    source_document_id TEXT NOT NULL,
                    source_version_id TEXT NOT NULL,
                    evidence_span TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    review_state TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    created_by_run TEXT,
                    FOREIGN KEY (source_document_id, source_version_id)
                        REFERENCES document_versions(document_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL REFERENCES entities(entity_id),
                    predicate TEXT NOT NULL,
                    object_id TEXT NOT NULL REFERENCES entities(entity_id),
                    source_document_id TEXT NOT NULL,
                    source_version_id TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    review_state TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    created_by_run TEXT,
                    FOREIGN KEY (source_document_id, source_version_id)
                        REFERENCES document_versions(document_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS extraction_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    source_sha256 TEXT,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_decisions (
                    decision_id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
                CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source_document_id, source_version_id);
                CREATE INDEX IF NOT EXISTS idx_relations_subject ON relations(subject_id);
                CREATE INDEX IF NOT EXISTS idx_relations_object ON relations(object_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_document ON evidence_spans(document_id, version_id);
                """
            )

    def put_document_version(self, document: DocumentVersion) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO document_versions
                (document_id, version_id, source_sha256, domain, text, sensitivity, review_state, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id, version_id) DO UPDATE SET
                    text=excluded.text, sensitivity=excluded.sensitivity,
                    review_state=excluded.review_state, run_id=excluded.run_id""",
                tuple(document.__dict__.values()),
            )

    def add_evidence(self, evidence: EvidenceSpan) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO evidence_spans
                (evidence_id, document_id, version_id, locator, quote, extractor, confidence, created_by_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET quote=excluded.quote,
                    locator=excluded.locator, confidence=excluded.confidence""",
                tuple(evidence.__dict__.values()),
            )

    def add_entity(self, entity: GraphEntity) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET canonical_name=excluded.canonical_name,
                    confidence=excluded.confidence, review_state=excluded.review_state,
                    valid_to=excluded.valid_to""",
                tuple(entity.__dict__.values()),
            )

    def add_relation(self, relation: GraphRelation) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relation_id) DO UPDATE SET evidence_refs=excluded.evidence_refs,
                    confidence=excluded.confidence, review_state=excluded.review_state,
                    valid_to=excluded.valid_to""",
                (
                    relation.relation_id,
                    relation.subject_id,
                    relation.predicate,
                    relation.object_id,
                    relation.source_document_id,
                    relation.source_version_id,
                    json.dumps(relation.evidence_refs),
                    relation.confidence,
                    relation.review_state,
                    relation.valid_from,
                    relation.valid_to,
                    relation.created_by_run,
                ),
            )

    def record_extraction_run(
        self,
        *,
        run_id: str,
        scenario_id: str,
        source_sha256: str | None,
        model_id: str,
        status: str,
        evidence_refs: Iterable[str],
        created_at: str,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO extraction_runs VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,
                    evidence_refs=excluded.evidence_refs""",
                (run_id, scenario_id, source_sha256, model_id, status, json.dumps(list(evidence_refs)), created_at),
            )

    def record_review(
        self,
        *,
        decision_id: str,
        target_type: str,
        target_id: str,
        decision: str,
        reviewer: str,
        reason: str,
        created_at: str,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO review_decisions VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET decision=excluded.decision,
                    reason=excluded.reason""",
                (decision_id, target_type, target_id, decision, reviewer, reason, created_at),
            )

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        return dict(row) if row else None

    def search_entities(
        self, query: str, *, review_state: ReviewState | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Search active entities without returning source document text."""
        if not query.strip():
            raise ValueError("entity search requires a non-empty query")
        if limit <= 0 or limit > 500:
            raise ValueError("entity search limit must be between 1 and 500")
        self.initialize()
        clauses = ["canonical_name LIKE ?", "review_state != 'rejected'", "valid_to IS NULL"]
        values: list[object] = [f"%{query.strip()}%"]
        if review_state is not None:
            clauses.append("review_state = ?")
            values.append(review_state)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT entity_id, entity_type, canonical_name, source_document_id, source_version_id, "
                f"evidence_span, confidence, review_state, valid_from, valid_to, created_by_run "
                f"FROM entities WHERE {' AND '.join(clauses)} ORDER BY canonical_name, entity_id LIMIT ?",
                (*values, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def neighbors(self, entity_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return active, evidence-linked graph edges around one entity."""
        if limit <= 0 or limit > 500:
            raise ValueError("neighbor limit must be between 1 and 500")
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT r.relation_id, r.predicate, r.subject_id, r.object_id,
                          r.evidence_refs, r.confidence, r.review_state,
                          e.entity_id AS neighbor_id, e.entity_type AS neighbor_type,
                          e.canonical_name AS neighbor_name
                   FROM relations r
                   JOIN entities e ON e.entity_id = CASE
                       WHEN r.subject_id = ? THEN r.object_id ELSE r.subject_id END
                   WHERE (r.subject_id = ? OR r.object_id = ?)
                     AND r.review_state != 'rejected' AND r.valid_to IS NULL
                     AND e.review_state != 'rejected' AND e.valid_to IS NULL
                   ORDER BY r.relation_id LIMIT ?""",
                (entity_id, entity_id, entity_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["evidence_refs"] = json.loads(str(item["evidence_refs"]))
            result.append(item)
        return result

    def review_entity(
        self,
        *,
        entity_id: str,
        decision: Literal["human_verified", "rejected", "pending"],
        reviewer: str,
        reason: str,
        decision_id: str,
        created_at: str | None = None,
    ) -> None:
        """Record an auditable human decision without deleting graph history."""
        if not reviewer.strip() or not reason.strip():
            raise ValueError("graph review requires reviewer and reason")
        self.initialize()
        timestamp = created_at or datetime.now(UTC).isoformat()
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE entities SET review_state = ?, valid_to = CASE WHEN ? = 'rejected' THEN ? ELSE valid_to END WHERE entity_id = ?",
                (decision, decision, timestamp, entity_id),
            ).rowcount
            if not updated:
                raise KeyError(f"unknown graph entity: {entity_id}")
            connection.execute(
                "INSERT INTO review_decisions VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(decision_id) DO UPDATE SET decision=excluded.decision, reason=excluded.reason",
                (decision_id, "entity", entity_id, decision, reviewer, reason, timestamp),
            )

    def rollback_run(self, run_id: str, *, reviewer: str, reason: str, decision_id: str) -> dict[str, int]:
        """Invalidate all facts produced by a run while preserving its audit trail."""
        if not run_id.strip() or not reviewer.strip() or not reason.strip():
            raise ValueError("graph rollback requires run_id, reviewer, and reason")
        self.initialize()
        timestamp = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            counts = {
                "entities": connection.execute(
                    "UPDATE entities SET review_state='rejected', valid_to=? WHERE created_by_run=? AND valid_to IS NULL",
                    (timestamp, run_id),
                ).rowcount,
                "relations": connection.execute(
                    "UPDATE relations SET review_state='rejected', valid_to=? WHERE created_by_run=? AND valid_to IS NULL",
                    (timestamp, run_id),
                ).rowcount,
                "documents": connection.execute(
                    "UPDATE document_versions SET review_state='rejected' WHERE run_id=? AND review_state != 'rejected'",
                    (run_id,),
                ).rowcount,
            }
            connection.execute(
                "INSERT INTO review_decisions VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(decision_id) DO UPDATE SET decision=excluded.decision, reason=excluded.reason",
                (decision_id, "run", run_id, "rollback", reviewer, reason, timestamp),
            )
        return counts

    def list_evidence(self, document_id: str, version_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence_spans WHERE document_id = ? AND version_id = ? ORDER BY evidence_id",
                (document_id, version_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def export_snapshot(self, *, include_text: bool = False) -> dict[str, list[dict[str, Any]]]:
        """Return a deterministic snapshot; raw document text is opt-in."""
        self.initialize()
        with self._connect() as connection:
            result: dict[str, list[dict[str, Any]]] = {}
            for table in ("document_versions", "evidence_spans", "entities", "relations"):
                columns = "*"
                if table == "document_versions" and not include_text:
                    columns = "document_id, version_id, source_sha256, domain, sensitivity, review_state, run_id"
                rows = connection.execute(f"SELECT {columns} FROM {table} ORDER BY rowid").fetchall()
                result[table] = [dict(row) for row in rows]
        return result
