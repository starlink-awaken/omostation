"""SQLite DLQ — dead letter queue for failed bus events.

Phase B (R66): WAL mode + busy_timeout 5000 + 50MB rolling GC.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DLQ_MAX_SIZE_MB = 50
DLQ_MAX_RETRIES = 3
DEFAULT_DB_PATH = Path(
    os.environ.get("BUS_DLQ_PATH", str(Path.home() / ".runtime" / "bus_dlq.db"))
)


class DLQ:
    """Thread-safe SQLite DLQ with WAL + GC."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._open_conn()
        self._init_schema()
        self._maybe_rotate()

    def _open_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq (
                    event_id TEXT PRIMARY KEY,
                    backend TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    error TEXT,
                    retries INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS dlq_status_idx
                ON dlq(status)
            """)
            self._conn.commit()

    def _maybe_rotate(self) -> None:
        if not self.db_path.exists():
            return
        size_mb = self.db_path.stat().st_size / (1024 * 1024)
        if size_mb >= DLQ_MAX_SIZE_MB:
            old_path = self.db_path.with_suffix(".db.old")
            logger.warning("dlq_rotate", round(size_mb, 2), str(old_path))
            self._conn.close()
            old_path.unlink(missing_ok=True)
            self.db_path.rename(old_path)
            self._conn = self._open_conn()
            self._init_schema()

    def _now(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def enqueue(
        self,
        event_id: str,
        backend: str,
        envelope_json: str,
        error: str,
    ) -> None:
        now = self._now()
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO dlq
                    (event_id, backend, envelope_json, error, retries, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, 'PENDING', ?, ?)
                """,
                (event_id, backend, envelope_json, error, now, now),
            )
            self._conn.commit()

    def requeue(self, event_id: str, error: str) -> None:
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT retries FROM dlq WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                logger.warning("dlq_requeue_missing", event_id)
                return
            new_retries = row["retries"] + 1
            new_status = "DLQ" if new_retries >= DLQ_MAX_RETRIES else "PENDING"
            self._conn.execute(
                """
                UPDATE dlq
                SET retries = ?, status = ?, error = ?, updated_at = ?
                WHERE event_id = ?
                """,
                (new_retries, new_status, error, now, event_id),
            )
            self._conn.commit()

    def list_all(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dlq ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
