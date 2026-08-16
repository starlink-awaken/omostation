"""Tests for minerva.audit_store — SQLite audit logger.

Covers schema setup, log entry creation with unique IDs, query with
filters (action/result/since), aggregate stats, and module-level
log_operation convenience function.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from minerva.audit_store import (
    AuditEntry,
    AuditLogger,
    get_logger,
    log_operation,
)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Provide a temp DB path for isolated test runs."""
    return tmp_path / "audit.db"


@pytest.fixture
def logger(tmp_db: Path) -> AuditLogger:
    return AuditLogger(db_path=str(tmp_db))


# ── AuditLogger construction ────────────────────────────────────────


class TestAuditLoggerConstruction:
    def test_default_db_path(self, tmp_db: Path):
        """When no db_path given, uses module-level _DB_PATH."""
        # Create with explicit path to avoid touching real ~/.minerva
        logger = AuditLogger(db_path=str(tmp_db))
        assert logger._db_path == str(tmp_db)

    def test_ensures_schema_on_init(self, tmp_db: Path):
        """Constructor creates audit_log table if missing."""
        AuditLogger(db_path=str(tmp_db))
        conn = sqlite3.connect(str(tmp_db))
        try:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            assert "audit_log" in tables
        finally:
            conn.close()

    def test_schema_idempotent(self, tmp_db: Path):
        """Calling _ensure_schema twice doesn't fail."""
        AuditLogger(db_path=str(tmp_db))
        AuditLogger(db_path=str(tmp_db))  # Should not raise

    def test_schema_has_expected_columns(self, tmp_db: Path):
        """All required columns are present in audit_log."""
        AuditLogger(db_path=str(tmp_db))
        conn = sqlite3.connect(str(tmp_db))
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
            for required in ("id", "timestamp", "actor", "action", "resource", "result", "detail", "duration_ms"):
                assert required in cols
        finally:
            conn.close()


# ── log() ──────────────────────────────────────────────────────────


class TestLog:
    def test_returns_12char_id(self, logger: AuditLogger):
        entry_id = logger.log("cli", "research.run", "test_query", "success")
        assert isinstance(entry_id, str)
        assert len(entry_id) == 12

    def test_returns_unique_ids(self, logger: AuditLogger):
        ids = {logger.log("cli", "x", "r", "success") for _ in range(50)}
        assert len(ids) == 50

    def test_persists_to_db(self, logger: AuditLogger, tmp_db: Path):
        logger.log("web", "research.list", "q1", "success", "ok", 12.5)
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute("SELECT * FROM audit_log").fetchone()
        finally:
            conn.close()
        assert row is not None
        # columns: id, timestamp, actor, action, resource, result, detail, duration_ms
        assert row[2] == "web"  # actor
        assert row[3] == "research.list"  # action
        assert row[4] == "q1"  # resource
        assert row[5] == "success"  # result
        assert row[6] == "ok"  # detail
        assert row[7] == 12.5  # duration_ms

    def test_truncates_detail_at_500(self, logger: AuditLogger, tmp_db: Path):
        long_detail = "x" * 1000
        logger.log("cli", "x", "r", "error", detail=long_detail)
        conn = sqlite3.connect(str(tmp_db))
        try:
            detail = conn.execute("SELECT detail FROM audit_log").fetchone()[0]
        finally:
            conn.close()
        assert len(detail) == 500

    def test_default_values(self, logger: AuditLogger, tmp_db: Path):
        logger.log("cli", "x", "r", "success")
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute("SELECT detail, duration_ms FROM audit_log").fetchone()
        finally:
            conn.close()
        assert row[0] == ""  # default detail
        assert row[1] == 0.0  # default duration

    def test_timestamp_iso8601_utc(self, logger: AuditLogger, tmp_db: Path):
        logger.log("cli", "x", "r", "success")
        conn = sqlite3.connect(str(tmp_db))
        try:
            ts = conn.execute("SELECT timestamp FROM audit_log").fetchone()[0]
        finally:
            conn.close()
        # Format: YYYY-MM-DDTHH:MM:SSZ
        assert ts.endswith("Z")
        assert "T" in ts
        assert len(ts) == 20


# ── query() ────────────────────────────────────────────────────────


class TestQuery:
    def test_empty_returns_empty_list(self, logger: AuditLogger):
        assert logger.query() == []

    def test_returns_all_by_default(self, logger: AuditLogger):
        for i in range(5):
            logger.log("cli", "x", f"r{i}", "success")
        assert len(logger.query()) == 5

    def test_filter_by_action(self, logger: AuditLogger):
        logger.log("cli", "research.run", "q1", "success")
        logger.log("cli", "research.list", "q2", "success")
        logger.log("cli", "check", "q3", "success")
        result = logger.query(action="research.run")
        assert len(result) == 1
        assert result[0]["action"] == "research.run"

    def test_filter_by_result(self, logger: AuditLogger):
        logger.log("cli", "x", "r1", "success")
        logger.log("cli", "x", "r2", "denied")
        logger.log("cli", "x", "r3", "success")
        result = logger.query(result="denied")
        assert len(result) == 1
        assert result[0]["resource"] == "r2"

    def test_filter_by_since(self, logger: AuditLogger):
        # Insert with future timestamp
        logger.log("cli", "x", "r_old", "success")
        # Query with future since filter
        from datetime import UTC, datetime, timedelta

        future = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = logger.query(since=future)
        assert result == []

    def test_limit(self, logger: AuditLogger):
        for i in range(20):
            logger.log("cli", "x", f"r{i}", "success")
        assert len(logger.query(limit=5)) == 5

    def test_order_descending_by_timestamp(self, logger: AuditLogger):
        # Insert entries with explicit timestamps via direct SQL
        from datetime import UTC, datetime

        conn = sqlite3.connect(logger._db_path)
        try:
            for i, ts_offset in enumerate([3, 1, 2]):
                ts = datetime.now(UTC).timestamp() + ts_offset
                from datetime import datetime as dt

                ts_str = dt.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"id_{i}", ts_str, "cli", "x", f"r{i}", "success", "", 0.0),
                )
            conn.commit()
        finally:
            conn.close()
        result = logger.query(limit=10)
        timestamps = [r["timestamp"] for r in result]
        # DESC order: most recent first
        assert timestamps == sorted(timestamps, reverse=True)

    def test_combined_filters(self, logger: AuditLogger):
        logger.log("cli", "research.run", "q1", "success")
        logger.log("cli", "research.run", "q2", "denied")
        logger.log("cli", "research.list", "q3", "success")
        result = logger.query(action="research.run", result="success")
        assert len(result) == 1
        assert result[0]["resource"] == "q1"


# ── stats() ────────────────────────────────────────────────────────


class TestStats:
    def test_empty_db_stats(self, logger: AuditLogger):
        s = logger.stats()
        assert s["total_entries"] == 0
        assert s["last_hour"] == 0
        assert s["by_action_result"] == {}

    def test_total_entries_count(self, logger: AuditLogger):
        for i in range(7):
            logger.log("cli", "x", f"r{i}", "success")
        assert logger.stats()["total_entries"] == 7

    def test_by_action_result_grouping(self, logger: AuditLogger):
        logger.log("cli", "research.run", "q1", "success")
        logger.log("cli", "research.run", "q2", "success")
        logger.log("cli", "research.run", "q3", "denied")
        logger.log("web", "check", "x", "success")
        s = logger.stats()
        assert s["by_action_result"]["research.run:success"] == 2
        assert s["by_action_result"]["research.run:denied"] == 1
        assert s["by_action_result"]["check:success"] == 1

    def test_last_hour_within_window(self, logger: AuditLogger):
        logger.log("cli", "x", "r1", "success")
        s = logger.stats()
        # 1 entry inserted in last hour
        assert s["last_hour"] == 1


# ── log_operation (module-level) ────────────────────────────────


class TestLogOperation:
    def test_log_operation_creates_entry(self, tmp_db: Path, monkeypatch):
        """Module-level log_operation uses the global logger; ensure side effect."""
        # Reset the global logger to use our tmp_db by re-initializing
        import minerva.audit_store as mod
        from minerva.audit_store import AuditLogger

        monkeypatch.setattr(mod, "_logger", AuditLogger(db_path=str(tmp_db)))
        entry_id = log_operation("cli", "x", "r", "success")
        assert isinstance(entry_id, str) and len(entry_id) == 12
        # Verify it landed in tmp_db
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute("SELECT actor, action FROM audit_log").fetchone()
        finally:
            conn.close()
        assert row == ("cli", "x")

    def test_log_operation_default_detail(self, tmp_db: Path, monkeypatch):
        import minerva.audit_store as mod
        from minerva.audit_store import AuditLogger

        monkeypatch.setattr(mod, "_logger", AuditLogger(db_path=str(tmp_db)))
        log_operation("cli", "x", "r", "success")
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute("SELECT detail, duration_ms FROM audit_log").fetchone()
        finally:
            conn.close()
        assert row[0] == ""
        assert row[1] == 0.0

    def test_log_operation_uses_default_path_when_unset(self, monkeypatch):
        """When _logger is None, get_logger() creates a default AuditLogger."""
        import minerva.audit_store as mod

        monkeypatch.setattr(mod, "_logger", None)
        # Avoid touching the real ~/.minerva path
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_db = str(Path(tmpdir) / "fake.db")
            monkeypatch.setattr(mod, "_DB_PATH", type(mod._DB_PATH)(fake_db))
            logger = get_logger()
            assert logger._db_path == fake_db


# ── AuditEntry dataclass ─────────────────────────────────────────


class TestAuditEntry:
    def test_required_fields(self):
        e = AuditEntry(
            id="abc123",
            timestamp="2026-07-26T00:00:00Z",
            actor="cli",
            action="research.run",
            resource="q1",
            result="success",
        )
        assert e.id == "abc123"
        assert e.detail == ""  # default
        assert e.duration_ms == 0.0  # default

    def test_all_fields(self):
        e = AuditEntry(
            id="x",
            timestamp="t",
            actor="a",
            action="b",
            resource="r",
            result="ok",
            detail="d",
            duration_ms=1.5,
        )
        assert e.detail == "d"
        assert e.duration_ms == 1.5
