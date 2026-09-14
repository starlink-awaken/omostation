"""Persistent, redacted human-adjudication queue for KEMS evaluation data."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .annotation_schema import validate_annotation_labels

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SPLITS = {"train", "validation", "test", "shadow"}
_PRIVATE_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}


def _reject_private(value: object) -> None:
    if isinstance(value, dict):
        if _PRIVATE_KEYS.intersection(str(key).lower() for key in value):
            raise ValueError("raw content fields are forbidden")
        for child in value.values():
            _reject_private(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private(child)


def _required_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _validate_queue_item(record: object) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("adjudication queue item must be an object")
    _reject_private(record)
    sample_id = _required_text(record, "sample_id")
    source_sha256 = _required_text(record, "source_sha256")
    if not _SHA256.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be a lowercase SHA-256")
    source_ref = _required_text(record, "source_ref")
    if not source_ref.startswith("vault://redacted/"):
        raise ValueError("source_ref must use vault://redacted/")
    split = _required_text(record, "split")
    if split not in _SPLITS:
        raise ValueError("split is unsupported")
    status = record.get("annotation_status", "pending")
    if status != "pending":
        raise ValueError("new queue items must be pending")
    return {
        "sample_id": sample_id,
        "source_sha256": source_sha256,
        "source_ref": source_ref,
        "scenario_id": _required_text(record, "scenario_id"),
        "split": split,
    }


class AdjudicationStore:
    """Persist redacted metadata, independent annotations, and final adjudication."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS adjudication_queue (
                    sample_id TEXT PRIMARY KEY,
                    source_sha256 TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    split TEXT NOT NULL,
                    annotation_status TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    annotation_version TEXT NOT NULL,
                    annotator TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(adjudication_queue)").fetchall()}
            if "adjudicator" not in columns:
                connection.execute("ALTER TABLE adjudication_queue ADD COLUMN adjudicator TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS adjudication_annotations (
                    annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id TEXT NOT NULL,
                    annotator TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    annotation_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(sample_id, annotator),
                    FOREIGN KEY (sample_id) REFERENCES adjudication_queue(sample_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS adjudication_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id TEXT NOT NULL,
                    annotator TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    UNIQUE(sample_id, annotator),
                    FOREIGN KEY (sample_id) REFERENCES adjudication_queue(sample_id)
                )
                """
            )
            connection.execute(
                """INSERT OR IGNORE INTO adjudication_claims (sample_id, annotator, claimed_at)
                   SELECT sample_id, annotator, claimed_at
                   FROM adjudication_queue
                   WHERE annotator != ''"""
            )

    def ingest_queue(self, items: list[object]) -> int:
        if not items:
            raise ValueError("adjudication queue must not be empty")
        normalized = [_validate_queue_item(item) for item in items]
        now = datetime.now(UTC).isoformat()
        self.initialize()
        inserted = 0
        with self._connect() as connection:
            for item in normalized:
                existing = connection.execute(
                    "SELECT source_sha256, source_ref, scenario_id, split FROM adjudication_queue WHERE sample_id=?",
                    (item["sample_id"],),
                ).fetchone()
                if existing:
                    if any(
                        existing[field] != item[field]
                        for field in ("source_sha256", "source_ref", "scenario_id", "split")
                    ):
                        raise ValueError(f"sample_id already exists with different metadata: {item['sample_id']}")
                    continue
                connection.execute(
                    """INSERT INTO adjudication_queue
                       (sample_id, source_sha256, source_ref, scenario_id, split,
                        annotation_status, labels_json, annotation_version, annotator,
                        claimed_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item["sample_id"],
                        item["source_sha256"],
                        item["source_ref"],
                        item["scenario_id"],
                        item["split"],
                        "pending",
                        "{}",
                        "",
                        "",
                        "",
                        now,
                    ),
                )
                inserted += 1
        return inserted

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["labels"] = json.loads(str(result.pop("labels_json")))
        return result

    def _annotation_summary(self, sample_id: str) -> tuple[int, list[str], bool]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT annotator, labels_json FROM adjudication_annotations WHERE sample_id=? ORDER BY annotation_id",
                (sample_id,),
            ).fetchall()
        labels = [str(row["labels_json"]) for row in rows]
        return (
            len(rows),
            [str(row["annotator"]) for row in rows],
            len(set(labels)) > 1,
        )

    def _claim_summary(self, sample_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT annotator FROM adjudication_claims WHERE sample_id=? ORDER BY claim_id",
                (sample_id,),
            ).fetchall()
        return [str(row["annotator"]) for row in rows]

    def _with_annotation_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        count, annotators, conflict = self._annotation_summary(str(item["sample_id"]))
        item["annotation_count"] = count
        item["annotation_annotators"] = annotators
        item["annotation_conflict"] = conflict
        item["claimed_annotators"] = self._claim_summary(str(item["sample_id"]))
        return item

    def list_items(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if status is not None and status not in {"pending", "reviewed", "conflict", "adjudicated"}:
            raise ValueError("annotation status is unsupported")
        self.initialize()
        with self._connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM adjudication_queue WHERE annotation_status=? ORDER BY updated_at, sample_id LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM adjudication_queue ORDER BY updated_at, sample_id LIMIT ?", (limit,)
                ).fetchall()
        return [self._with_annotation_summary(self._row(row)) for row in rows]

    def get_item(self, sample_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM adjudication_queue WHERE sample_id=?", (sample_id,)).fetchone()
        return self._with_annotation_summary(self._row(row)) if row else None

    def submit_annotation(
        self,
        sample_id: str,
        *,
        labels: dict[str, Any],
        annotation_version: str,
        annotator: str,
    ) -> dict[str, Any]:
        """Record one immutable independent annotation; never overwrite another annotator."""
        if not labels:
            raise ValueError("labels must be a non-empty object")
        _reject_private(labels)
        annotation_version = annotation_version.strip()
        annotator = annotator.strip()
        if not annotation_version or not annotator:
            raise ValueError("annotation_version and annotator are required")
        self.initialize()
        now = datetime.now(UTC).isoformat()
        labels_json = json.dumps(labels, ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT annotation_status, scenario_id FROM adjudication_queue WHERE sample_id=?",
                (sample_id,),
            ).fetchone()
            if row is None:
                raise KeyError(sample_id)
            if row["annotation_status"] == "adjudicated":
                raise ValueError("adjudicated samples cannot receive new annotations")
            claimed = connection.execute(
                "SELECT 1 FROM adjudication_claims WHERE sample_id=? AND annotator=?",
                (sample_id, annotator),
            ).fetchone()
            if claimed is None:
                raise ValueError("annotator must claim the sample before submitting an annotation")
            labels = validate_annotation_labels(str(row["scenario_id"]), labels)
            try:
                connection.execute(
                    """INSERT INTO adjudication_annotations
                       (sample_id, annotator, labels_json, annotation_version, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (sample_id, annotator, labels_json, annotation_version, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("annotator already submitted an annotation for this sample") from exc
            count = connection.execute(
                "SELECT COUNT(*) FROM adjudication_annotations WHERE sample_id=?", (sample_id,)
            ).fetchone()[0]
            annotation_status = "reviewed" if count < 2 else "conflict"
            if count >= 2:
                rows = connection.execute(
                    "SELECT labels_json FROM adjudication_annotations WHERE sample_id=?",
                    (sample_id,),
                ).fetchall()
                if len({str(item["labels_json"]) for item in rows}) == 1:
                    annotation_status = "reviewed"
            connection.execute(
                "UPDATE adjudication_queue SET annotation_status=?, updated_at=? WHERE sample_id=?",
                (annotation_status, now, sample_id),
            )
        result = self.get_item(sample_id)
        assert result is not None
        return result

    def claim(self, sample_id: str, *, annotator: str) -> dict[str, Any]:
        annotator = annotator.strip()
        if not annotator:
            raise ValueError("annotator is required")
        self.initialize()
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM adjudication_queue WHERE sample_id=?", (sample_id,)).fetchone()
            if row is None:
                raise KeyError(sample_id)
            if row["annotation_status"] == "adjudicated":
                raise ValueError("adjudicated samples cannot be claimed")
            existing_claim = connection.execute(
                "SELECT 1 FROM adjudication_claims WHERE sample_id=? AND annotator=?",
                (sample_id, annotator),
            ).fetchone()
            if existing_claim is None:
                claim_count = connection.execute(
                    "SELECT COUNT(*) FROM adjudication_claims WHERE sample_id=?", (sample_id,)
                ).fetchone()[0]
                if claim_count >= 2:
                    raise ValueError("two independent annotator slots are already claimed")
                connection.execute(
                    "INSERT INTO adjudication_claims (sample_id, annotator, claimed_at) VALUES (?, ?, ?)",
                    (sample_id, annotator, now),
                )
            if not row["annotator"]:
                connection.execute(
                    "UPDATE adjudication_queue SET annotation_status='reviewed', annotator=?, claimed_at=?, updated_at=? WHERE sample_id=?",
                    (annotator, now, now, sample_id),
                )
            else:
                connection.execute(
                    "UPDATE adjudication_queue SET updated_at=? WHERE sample_id=?",
                    (now, sample_id),
                )
        result = self.get_item(sample_id)
        assert result is not None
        return result

    def adjudicate(
        self,
        sample_id: str,
        *,
        labels: dict[str, Any],
        annotation_version: str,
        annotator: str | None = None,
        adjudicator: str | None = None,
    ) -> dict[str, Any]:
        if not labels:
            raise ValueError("labels must be a non-empty object")
        _reject_private(labels)
        annotation_version = annotation_version.strip()
        actor = (adjudicator or annotator or "").strip()
        if not annotation_version or not actor:
            raise ValueError("annotation_version and adjudicator are required")
        self.initialize()
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT scenario_id FROM adjudication_queue WHERE sample_id=?", (sample_id,)
            ).fetchone()
            if row is None:
                raise KeyError(sample_id)
            annotations = connection.execute(
                "SELECT annotator FROM adjudication_annotations WHERE sample_id=?", (sample_id,)
            ).fetchall()
            annotators = {str(row["annotator"]) for row in annotations}
            if len(annotators) < 2:
                raise ValueError("adjudication requires two independent annotators")
            if actor in annotators:
                raise ValueError("adjudicator must be independent from annotators")
            labels = validate_annotation_labels(str(row["scenario_id"]), labels)
            connection.execute(
                """UPDATE adjudication_queue
                   SET annotation_status='adjudicated', labels_json=?, annotation_version=?, annotator=?, adjudicator=?, updated_at=?
                   WHERE sample_id=?""",
                (
                    json.dumps(labels, ensure_ascii=False, sort_keys=True),
                    annotation_version,
                    actor,
                    actor,
                    now,
                    sample_id,
                ),
            )
        result = self.get_item(sample_id)
        assert result is not None
        return result

    def adjudicated_items(self, *, limit: int = 10000) -> list[dict[str, Any]]:
        return self.list_items(status="adjudicated", limit=limit)
