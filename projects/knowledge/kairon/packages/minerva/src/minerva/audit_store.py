"""Audit Logger — records all Minerva operations for governance and monitoring.

Persists to SQLite at ~/.minerva/minerva.db. Thread-safe.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DB_PATH = Path.home() / ".minerva" / "minerva.db"


@dataclass
class AuditEntry:
    """A single audit log entry."""

    id: str
    timestamp: str  # ISO8601
    actor: str  # "cli" / "web" / "mcp" / "system"
    action: str  # "research.run" / "research.list" / "check" / "init"
    resource: str  # query / command / target
    result: str  # "success" / "denied" / "error"
    detail: str = ""
    duration_ms: float = 0.0


class AuditLogger:
    """Write and query audit logs."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or str(_DB_PATH)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    result TEXT NOT NULL,
                    detail TEXT DEFAULT '',
                    duration_ms REAL DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def log(
        self,
        actor: str,
        action: str,
        resource: str,
        result: str,
        detail: str = "",
        duration_ms: float = 0.0,
    ) -> str:
        """Record an audit entry. Returns the entry ID."""
        entry_id = str(uuid.uuid4())[:12]
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO audit_log (id, timestamp, actor, action, resource, result, detail, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (entry_id, ts, actor, action, resource, result, detail[:500], duration_ms),
            )
            conn.commit()
        finally:
            conn.close()
        return entry_id

    def query(
        self,
        limit: int = 50,
        action: str | None = None,
        result: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query audit log entries."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            where = []
            params: list[Any] = []
            if action:
                where.append("action = ?")
                params.append(action)
            if result:
                where.append("result = ?")
                params.append(result)
            if since:
                where.append("timestamp >= ?")
                params.append(since)

            sql = "SELECT * FROM audit_log"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        conn = sqlite3.connect(self._db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            by_action = {}
            for row in conn.execute(
                "SELECT action, result, COUNT(*) as cnt FROM audit_log GROUP BY action, result"
            ).fetchall():
                key = f"{row[0]}:{row[1]}"
                by_action[key] = row[2]
            last_hour = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE timestamp >= datetime('now', '-1 hour')"
            ).fetchone()[0]
            return {
                "total_entries": total,
                "last_hour": last_hour,
                "by_action_result": by_action,
            }
        finally:
            conn.close()


# Global logger instance
_logger: AuditLogger | None = None


def get_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger


def log_operation(
    actor: str,
    action: str,
    resource: str,
    result: str,
    detail: str = "",
    duration_ms: float = 0.0,
) -> str:
    """Convenience function: log and return entry ID."""
    return get_logger().log(actor, action, resource, result, detail, duration_ms)
