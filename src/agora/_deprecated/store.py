"""Simple key-value store backed by sqlite3.

Adapted from agentmesh gateway core/store.ts (TaskStore).
Provides basic CRUD for task persistence.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

_LOCAL = threading.local()


def _get_conn(db_path: str) -> sqlite3.Connection:
    """Get thread-local connection."""
    if not hasattr(_LOCAL, "conn") or _LOCAL.conn is None:
        _LOCAL.conn = sqlite3.connect(db_path)
        _LOCAL.conn.row_factory = sqlite3.Row
        _LOCAL.conn.execute("PRAGMA journal_mode=WAL")
        _LOCAL.conn.execute("PRAGMA busy_timeout=3000")
    return _LOCAL.conn


class TaskStore:
    """SQLite-backed task store for gateway task persistence."""

    def __init__(self, db_path: str = "./data/tasks.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._migrate()

    def _conn(self) -> sqlite3.Connection:
        return _get_conn(self._db_path)

    def _migrate(self) -> None:
        conn = self._conn()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                request_json TEXT NOT NULL,
                assigned_agents TEXT NOT NULL DEFAULT '[]',
                result_json TEXT,
                error_json TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)"
        )
        conn.commit()

    def load_all(self) -> list[dict[str, Any]]:
        """Load all tasks, ordered by most recent first."""
        rows = (
            self._conn()
            .execute("SELECT * FROM tasks ORDER BY created_at DESC")
            .fetchall()
        )
        return [self._row_to_dict(r) for r in rows]

    def save(self, task: dict[str, Any]) -> None:
        """Upsert a single task."""
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO tasks
               (id, status, request_json, assigned_agents, result_json, error_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task["id"],
                task.get("status", "pending"),
                json.dumps(task.get("request", {}), default=str),
                json.dumps(task.get("assigned_agents", []), default=str),
                json.dumps(task.get("result")) if task.get("result") else None,
                json.dumps(task.get("error")) if task.get("error") else None,
                task.get("created_at", 0),
                task.get("updated_at", 0),
            ),
        )
        conn.commit()

    def purge_completed(self, older_than_days: int = 7) -> list[str]:
        """Delete completed/failed tasks older than N days. Returns removed IDs."""
        cutoff = int(__import__("time").time() * 1000) - older_than_days * 86400_000
        conn = self._conn()
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status IN ('completed', 'failed') AND updated_at < ?",
            (cutoff,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM tasks WHERE id IN ({placeholders})", ids)
            conn.commit()
        return ids

    def close(self) -> None:
        conn = self._conn()
        conn.close()
        _LOCAL.conn = None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "status": row["status"],
            "request": json.loads(row["request_json"]),
            "assigned_agents": json.loads(row["assigned_agents"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
