"""Ontology storage layer — Entity/Relation CRUD against KOS SQLite database.

Adapted from SPEC-v0.1.md §4.3 to use existing KOS workspace_config
instead of the (not-yet-created) starlink-types package.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.ontology._types import (  # type: ignore[import-not-found]
    Entity,
    EntityType,
    Relation,
    RelationType,
    infer_entity_type,
    validate_entity_id,
)


def _get_db_path() -> str:
    """Resolve KOS retrieval database path via workspace_config fallback."""
    try:
        from kos._default_workspace_config import get_artifact_path  # type: ignore[import-not-found]

        return get_artifact_path("retrievalDatabase")
    except Exception:
        # Ultimate fallback
        kos_home = os.environ.get("KOS_HOME", str(Path.home() / ".kos_home"))
        return str(Path(kos_home) / "kos-index.sqlite")


def _get_conn() -> sqlite3.Connection:
    path = _get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure ontology tables exist (idempotent)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kos_entities (
            entity_id   TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            label       TEXT NOT NULL,
            aliases     TEXT,
            description TEXT,
            zone        TEXT,
            source      TEXT,
            status      TEXT DEFAULT 'active',
            version     INTEGER DEFAULT 1,
            confidence  REAL DEFAULT 1.0,
            created_at  TEXT,
            updated_at  TEXT,
            metadata    TEXT
        );
        CREATE TABLE IF NOT EXISTS kos_relations (
            source_id   TEXT,
            relation_type TEXT NOT NULL,
            target_id   TEXT NOT NULL,
            confidence  REAL DEFAULT 1.0,
            source      TEXT DEFAULT 'manual',
            updated_at  TEXT,
            PRIMARY KEY (source_id, relation_type, target_id)
        );
        CREATE TABLE IF NOT EXISTS kos_entity_docs (
            entity_id TEXT,
            doc_id    TEXT,
            relevance REAL DEFAULT 0.5,
            PRIMARY KEY (entity_id, doc_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rel_source ON kos_relations(source_id);
        CREATE INDEX IF NOT EXISTS idx_rel_target ON kos_relations(target_id);
        CREATE INDEX IF NOT EXISTS idx_entity_type ON kos_entities(entity_type);
    """)
    # Graceful migration: add zone column if it doesn't exist (legacy DB compat)
    try:
        conn.execute("ALTER TABLE kos_entities ADD COLUMN zone TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_zone ON kos_entities(zone)")
    except sqlite3.OperationalError:
        pass  # zone column doesn't exist (shouldn't happen after ALTER above)


# ── Entity CRUD ──


def put_entity(entity: Entity) -> dict[str, Any]:
    """Create or update an entity."""
    conn = _get_conn()
    _ensure_schema(conn)

    if not entity.entity_type or entity.entity_type == EntityType.CONCEPT:
        inferred = infer_entity_type(entity.entity_id)
        if inferred:
            entity.entity_type = inferred

    if not validate_entity_id(entity.entity_id):
        conn.close()
        return {"error": f"Invalid entity ID: {entity.entity_id}"}

    now = entity.updated_at or datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO kos_entities
        (entity_id, entity_type, label, aliases, description, zone,
         source, status, version, confidence, created_at, updated_at, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entity.entity_id,
            entity.entity_type.value,
            entity.label,
            json.dumps(entity.aliases, ensure_ascii=False) if entity.aliases else None,
            entity.description,
            entity.zone,
            entity.source,
            entity.status,
            entity.version,
            entity.confidence,
            entity.created_at or now,
            now,
            json.dumps(entity.metadata, ensure_ascii=False) if entity.metadata else None,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "entity_id": entity.entity_id}


def get_entity(entity_id: str) -> Entity | None:
    """Retrieve an entity by ID."""
    conn = _get_conn()
    _ensure_schema(conn)
    row = conn.execute("SELECT * FROM kos_entities WHERE entity_id = ?", (entity_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return Entity(
        entity_id=row["entity_id"],
        entity_type=EntityType(row["entity_type"]),
        label=row["label"],
        aliases=json.loads(row["aliases"]) if row["aliases"] else [],
        description=row["description"] or "",
        zone=row["zone"] or "",
        source=row["source"] or "",
        confidence=row["confidence"] or 1.0,
        status=row["status"] or "active",
        version=row["version"] or 1,
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )


def search_entities(
    query: str,
    entity_type: str | None = None,
    zone: str | None = None,
    limit: int = 20,
) -> list[Entity]:
    """Search entities by label/aliases."""
    conn = _get_conn()
    _ensure_schema(conn)
    sql = "SELECT * FROM kos_entities WHERE (label LIKE ? OR aliases LIKE ?)"
    params: list[str] = [f"%{query}%", f"%{query}%"]

    if entity_type:
        sql += " AND entity_type = ?"
        params.append(entity_type)
    if zone:
        sql += " AND zone = ?"
        params.append(zone)

    sql += " ORDER BY label LIMIT ?"
    params.append(str(limit))
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return [
        Entity(
            entity_id=r["entity_id"],
            entity_type=EntityType(r["entity_type"]),
            label=r["label"],
            aliases=json.loads(r["aliases"]) if r["aliases"] else [],
            description=r["description"] or "",
            zone=r["zone"] or "",
        )
        for r in rows
    ]


def delete_entity(entity_id: str) -> dict[str, Any]:
    """Delete an entity and all its relations."""
    conn = _get_conn()
    _ensure_schema(conn)
    conn.execute("DELETE FROM kos_entities WHERE entity_id = ?", (entity_id,))
    conn.execute(
        "DELETE FROM kos_relations WHERE source_id = ? OR target_id = ?",
        (entity_id, entity_id),
    )
    conn.execute("DELETE FROM kos_entity_docs WHERE entity_id = ?", (entity_id,))
    conn.commit()
    deleted = conn.total_changes > 0
    conn.close()
    return {"status": "ok", "deleted": deleted}


# ── Relation CRUD ──


def put_relation(relation: Relation) -> dict[str, Any]:
    """Create or update a relation."""
    conn = _get_conn()
    _ensure_schema(conn)
    conn.execute(
        """INSERT OR REPLACE INTO kos_relations
        (source_id, relation_type, target_id, confidence, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            relation.source_id,
            relation.relation_type.value,
            relation.target_id,
            relation.confidence,
            relation.source,
            relation.updated_at or datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


def get_relations(entity_id: str, direction: str = "outgoing") -> list[Relation]:
    """Get all relations for an entity (outgoing/incoming)."""
    conn = _get_conn()
    _ensure_schema(conn)
    if direction == "outgoing":
        rows = conn.execute("SELECT * FROM kos_relations WHERE source_id = ?", (entity_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM kos_relations WHERE target_id = ?", (entity_id,)).fetchall()
    conn.close()
    return [
        Relation(
            source_id=r["source_id"],
            relation_type=RelationType(r["relation_type"]),
            target_id=r["target_id"],
            confidence=r["confidence"] or 1.0,
        )
        for r in rows
    ]


# ── Bulk import ──


def import_entities(entities: list[Entity]) -> dict[str, Any]:
    """Batch import entities."""
    added = 0
    errors: list[dict[str, str]] = []
    for e in entities:
        result = put_entity(e)
        if "error" in result:
            errors.append({"entity_id": e.entity_id, "error": result["error"]})
        else:
            added += 1
    return {"added": added, "errors": errors}
