"""Test DLQ — first 5 of 15 cases covering WAL, busy_timeout, GC, rotate."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bus_foundation.dlq import DLQ


class TestDLQBasics:
    def test_init_creates_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        assert db_path.exists()
        dlq.close()

    def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        dlq.close()
        assert mode.lower() == "wal"

    def test_busy_timeout_5000(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()
        dlq.close()
        assert timeout >= 5000

    def test_enqueue_records_failure(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        dlq.enqueue(
            event_id="evt-1",
            backend="eventbus",
            envelope_json='{"type":"test","source":"x"}',
            error="connection refused",
        )
        rows = dlq.list_all()
        assert len(rows) == 1
        assert rows[0]["event_id"] == "evt-1"
        assert rows[0]["status"] == "PENDING"
        assert rows[0]["retries"] == 0
        dlq.close()

    def test_enqueue_increments_retries_on_retry(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        dlq.enqueue(event_id="evt-2", backend="eventbus", envelope_json="{}", error="x")
        dlq.requeue(event_id="evt-2", error="still failing")
        rows = dlq.list_all()
        assert rows[0]["retries"] == 1
        assert rows[0]["status"] == "PENDING"
        dlq.close()
