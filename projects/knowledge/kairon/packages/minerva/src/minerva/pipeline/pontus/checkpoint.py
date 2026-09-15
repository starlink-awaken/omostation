"""Checkpoint/Resume — SQLite-backed pipeline state persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


class CheckpointManager:
    """Save and restore pipeline run state using SQLite.

    Usage:
        mgr = CheckpointManager()
        mgr.save("run-001", {"step": "fetch", "progress": 50})
        state = mgr.resume("run-001")  # -> dict or None
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = str(Path.home() / ".pontus" / "checkpoints.sqlite")
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def save(self, run_id: str, state: dict[str, Any]) -> None:
        """Save (insert or update) a checkpoint for the given run_id."""
        now = datetime.now(UTC).isoformat()
        state_json = json.dumps(state, default=str)
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (run_id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (run_id, state_json, now, now),
            )
            conn.commit()

    def resume(self, run_id: str) -> dict[str, Any] | None:
        """Return the saved state dict, or None if not found."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT state_json FROM checkpoints WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return cast("dict[str, Any] | None", json.loads(row["state_json"]))

    def delete(self, run_id: str) -> bool:
        """Delete a checkpoint. Returns True if a row was deleted."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM checkpoints WHERE run_id = ?", (run_id,))
            conn.commit()
            return cur.rowcount > 0

    def list_runs(self) -> list[dict[str, str]]:
        """List all saved run IDs with timestamps."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT run_id, created_at, updated_at FROM checkpoints ORDER BY updated_at DESC"
            ).fetchall()
        return [{"run_id": r["run_id"], "created_at": r["created_at"], "updated_at": r["updated_at"]} for r in rows]
