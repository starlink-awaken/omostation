"""Audit Logger — records all operations for governance and compliance.

Persists to SQLite via persistence_db. Provides query and stats.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from agora.auth.identity import Identity, normalize_identity  # type: ignore[import-not-found]
from agora.mcp.mcp_bootstrap import get_data_dir  # type: ignore[import-not-found]
from agora.persistence_db import _get_db  # type: ignore[import-not-found]

_DB_PATH = get_data_dir() / "agora.db"


@dataclass
class AuditEntry:
    """A single audit log entry."""

    id: str
    timestamp: str  # ISO8601
    actor: str  # "api_key:ak_xxx" / "system" / "anonymous"
    action: str  # "service.register" / "route.call" / "key.create"
    resource: str  # target service name / key id
    result: str  # "success" / "denied" / "error"
    detail: str = ""
    ip: str = ""


class AuditLogger:
    """Write and query audit logs."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(_DB_PATH)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = _get_db(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                result TEXT NOT NULL,
                detail TEXT DEFAULT '',
                ip TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)"
        )
        conn.commit()

    def log(
        self,
        action: str,
        actor: str | Identity | dict = "anonymous",
        resource: str = "",
        result: str = "success",
        detail: str = "",
        ip: str = "",
    ) -> str:
        """Record an audit entry. Returns the entry ID."""
        eid = str(uuid.uuid4())[:8]
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        actor_value = (
            normalize_identity(actor).actor
            if not isinstance(actor, str) or actor != "anonymous"
            else "anonymous"
        )
        if isinstance(actor, str) and actor and actor != "anonymous":
            actor_value = normalize_identity(actor).actor
        conn = _get_db(self._db_path)
        conn.execute(
            "INSERT INTO audit_log (id, timestamp, actor, action, resource, result, detail, ip) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, ts, actor_value, action, resource, result, detail, ip),
        )
        conn.commit()
        return eid

    def query(
        self,
        actor: str = "",
        action: str = "",
        resource: str = "",
        since: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """Query audit entries with optional filters."""
        conditions = []
        params: list = []
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource:
            conditions.append("resource = ?")
            params.append(resource)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        conn = _get_db(self._db_path)
        rows = conn.execute(
            f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def stats(self, since: str = "") -> dict:
        """Get audit statistics: action counts, actor counts, error rate."""
        conn = _get_db(self._db_path)
        cond = "WHERE timestamp >= ?" if since else ""
        params = (since,) if since else ()

        actions = {}
        for row in conn.execute(
            f"SELECT action, COUNT(*) as cnt FROM audit_log {cond} GROUP BY action",
            params,
        ).fetchall():
            actions[row[0]] = row[1]

        actors = {}
        for row in conn.execute(
            f"SELECT actor, COUNT(*) as cnt FROM audit_log {cond} GROUP BY actor",
            params,
        ).fetchall():
            actors[row[0]] = row[1]

        total = sum(actions.values())
        errors = actions.get("error", 0)
        return {
            "total": total,
            "actions": actions,
            "actors": actors,
            "error_rate": round(errors / total, 4) if total else 0,
        }


def _row_to_dict(row: tuple) -> dict:
    cols = ["id", "timestamp", "actor", "action", "resource", "result", "detail", "ip"]
    return dict(zip(cols, row, strict=True))
