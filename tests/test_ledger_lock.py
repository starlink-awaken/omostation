#!/usr/bin/env python3
"""Tests for lib/ledger_lock.py — file-based lock mechanism."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

# Ensure lib is importable
WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from lib.ledger_lock import (
    DEADLOCK_WARNING_S,
    STALE_LOCK_S,
    LedgerLock,
    LockAcquisitionError,
    LockInfo,
    break_stale_lock,
    read_lock_status,
)


@pytest.fixture
def tmp_lock_path(tmp_path: Path) -> Path:
    """Provide a temporary lock file path."""
    return tmp_path / "test.lock"


class TestLockInfo:
    """Tests for LockInfo dataclass."""

    def test_to_json_roundtrip(self) -> None:
        info = LockInfo(
            pid=12345,
            hostname="test-host",
            acquired_at=1000.0,
            renewed_at=1000.0,
            operation="test-op",
            metadata={"key": "value"},
        )
        text = info.to_json()
        restored = LockInfo.from_json(text)
        assert restored is not None
        assert restored.pid == 12345
        assert restored.hostname == "test-host"
        assert restored.operation == "test-op"
        assert restored.metadata == {"key": "value"}

    def test_from_json_invalid(self) -> None:
        assert LockInfo.from_json("not json") is None
        assert LockInfo.from_json("{}") is None
        assert LockInfo.from_json('{"pid": "not-a-number"}') is None

    def test_age_seconds(self) -> None:
        info = LockInfo(
            pid=1,
            hostname="h",
            acquired_at=time.time() - 10,
            renewed_at=time.time(),
        )
        assert info.age_seconds() >= 9.9
        assert info.age_seconds() < 11

    def test_is_process_alive_self(self) -> None:
        info = LockInfo(
            pid=os.getpid(),
            hostname="h",
            acquired_at=time.time(),
            renewed_at=time.time(),
        )
        assert info.is_process_alive() is True

    def test_is_process_alive_dead(self) -> None:
        info = LockInfo(
            pid=999999999,  # Very unlikely to be a real PID
            hostname="h",
            acquired_at=time.time(),
            renewed_at=time.time(),
        )
        assert info.is_process_alive() is False


class TestLedgerLock:
    """Tests for LedgerLock acquire/release."""

    def test_acquire_release(self, tmp_lock_path: Path) -> None:
        lock = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        info = lock.acquire()
        assert lock.is_held
        assert info.pid == os.getpid()
        assert tmp_lock_path.exists()
        lock.release()
        assert not lock.is_held
        assert not tmp_lock_path.exists()

    def test_context_manager(self, tmp_lock_path: Path) -> None:
        with LedgerLock(lock_path=tmp_lock_path, timeout=5) as lock:
            assert lock.is_held
            assert tmp_lock_path.exists()
        assert not tmp_lock_path.exists()

    def test_double_acquire_idempotent(self, tmp_lock_path: Path) -> None:
        lock = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        info1 = lock.acquire()
        info2 = lock.acquire()
        assert info1 is info2
        lock.release()

    def test_release_when_not_held(self, tmp_lock_path: Path) -> None:
        lock = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        lock.release()  # Should not raise

    def test_timeout_on_contention(self, tmp_lock_path: Path) -> None:
        """Two locks on the same path — second should timeout."""
        lock1 = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        lock1.acquire()

        lock2 = LedgerLock(lock_path=tmp_lock_path, timeout=0.5)
        with pytest.raises(LockAcquisitionError, match="Could not acquire"):
            lock2.acquire()

        lock1.release()

    def test_acquire_after_release(self, tmp_lock_path: Path) -> None:
        """Lock can be re-acquired after release."""
        lock1 = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        lock1.acquire()
        lock1.release()

        lock2 = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        lock2.acquire()
        assert lock2.is_held
        lock2.release()

    def test_operation_recorded(self, tmp_lock_path: Path) -> None:
        lock = LedgerLock(lock_path=tmp_lock_path, timeout=5, operation="cmd_complete")
        info = lock.acquire()
        assert info.operation == "cmd_complete"
        lock.release()

    def test_metadata_recorded(self, tmp_lock_path: Path) -> None:
        lock = LedgerLock(
            lock_path=tmp_lock_path,
            timeout=5,
            metadata={"bet_id": "BET-Y1Q1-T1-01"},
        )
        info = lock.acquire()
        assert info.metadata["bet_id"] == "BET-Y1Q1-T1-01"
        lock.release()


class TestReadLockStatus:
    """Tests for read_lock_status function."""

    def test_no_lock_file(self, tmp_lock_path: Path) -> None:
        status = read_lock_status(tmp_lock_path)
        assert status["locked"] is False
        assert status["info"] is None

    def test_valid_lock(self, tmp_lock_path: Path) -> None:
        lock = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        lock.acquire()

        status = read_lock_status(tmp_lock_path)
        assert status["locked"] is True
        assert status["info"] is not None
        assert status["info"]["pid"] == os.getpid()
        assert status["age_seconds"] is not None
        assert status["deadlock_warning"] is False

        lock.release()

    def test_stale_lock_detection(self, tmp_lock_path: Path) -> None:
        """Lock with dead PID and old age should be detected as stale."""
        info = LockInfo(
            pid=999999999,
            hostname="dead-host",
            acquired_at=time.time() - STALE_LOCK_S - 10,
            renewed_at=time.time() - STALE_LOCK_S - 10,
        )
        tmp_lock_path.write_text(info.to_json(), encoding="utf-8")

        status = read_lock_status(tmp_lock_path)
        assert status["locked"] is True
        assert status["stale"] is True

    def test_deadlock_warning(self, tmp_lock_path: Path) -> None:
        """Lock held >60s should trigger deadlock warning."""
        info = LockInfo(
            pid=os.getpid(),  # alive process
            hostname="test",
            acquired_at=time.time() - DEADLOCK_WARNING_S - 10,
            renewed_at=time.time() - DEADLOCK_WARNING_S - 10,
        )
        tmp_lock_path.write_text(info.to_json(), encoding="utf-8")

        status = read_lock_status(tmp_lock_path)
        assert status["locked"] is True
        assert status["deadlock_warning"] is True
        assert status["stale"] is False  # Process is alive


class TestBreakStaleLock:
    """Tests for break_stale_lock function."""

    def test_break_stale(self, tmp_lock_path: Path) -> None:
        info = LockInfo(
            pid=999999999,
            hostname="dead-host",
            acquired_at=time.time() - STALE_LOCK_S - 10,
            renewed_at=time.time() - STALE_LOCK_S - 10,
        )
        tmp_lock_path.write_text(info.to_json(), encoding="utf-8")

        assert break_stale_lock(tmp_lock_path) is True
        assert not tmp_lock_path.exists()

    def test_no_break_active_lock(self, tmp_lock_path: Path) -> None:
        """Should not break a lock held by a live process."""
        info = LockInfo(
            pid=os.getpid(),
            hostname="test",
            acquired_at=time.time(),
            renewed_at=time.time(),
        )
        tmp_lock_path.write_text(info.to_json(), encoding="utf-8")

        assert break_stale_lock(tmp_lock_path) is False
        assert tmp_lock_path.exists()

    def test_no_lock_to_break(self, tmp_lock_path: Path) -> None:
        assert break_stale_lock(tmp_lock_path) is False


class TestConcurrentAccess:
    """Tests simulating concurrent access patterns."""

    def test_sequential_access(self, tmp_lock_path: Path) -> None:
        """Multiple sequential lock acquisitions should work."""
        for i in range(5):
            lock = LedgerLock(lock_path=tmp_lock_path, timeout=5, operation=f"op-{i}")
            lock.acquire()
            assert lock.is_held
            lock.release()

    def test_lock_file_cleanup_on_release(self, tmp_lock_path: Path) -> None:
        """Lock file should be removed after release."""
        lock = LedgerLock(lock_path=tmp_lock_path, timeout=5)
        lock.acquire()
        assert tmp_lock_path.exists()
        lock.release()
        assert not tmp_lock_path.exists()


class TestCLI:
    """Tests for ledger-lock-check.py CLI."""

    def test_check_no_lock(self, tmp_path: Path) -> None:
        """CLI should report no lock when lock file doesn't exist."""
        import subprocess

        result = subprocess.run(
            [sys.executable, "bin/gac/ledger-lock-check.py", "--json"],
            cwd=str(WS),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["locked"] is False

    def test_check_with_lock(self, tmp_path: Path) -> None:
        """CLI should report lock status when lock exists."""
        import subprocess

        # Create a lock
        lock = LedgerLock(timeout=5, operation="test-cli")
        lock.acquire()

        try:
            result = subprocess.run(
                [sys.executable, "bin/gac/ledger-lock-check.py", "--json"],
                cwd=str(WS),
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["locked"] is True
            assert data["info"]["operation"] == "test-cli"
        finally:
            lock.release()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
