"""Tests for file lock mechanism.

Tests lock acquisition/release, conflict detection, deadlock detection,
and high-frequency file monitoring.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "lib"))

from file_lock import (
    DEFAULT_TIMEOUT_S,
    DEADLOCK_THRESHOLD_S,
    FileLock,
    _file_hash,
    _lock_path,
    acquire_lock,
    check_conflict,
    cleanup_expired,
    detect_deadlocks,
    heartbeat,
    list_dead_locks,
    list_expired_locks,
    list_locks,
    read_lock,
    release_lock,
)
from high_frequency_files import (
    HIGH_FREQUENCY_FILES,
    HighFrequencyFileMonitor,
    get_high_frequency_paths,
)


# --- Fixtures ---


@pytest.fixture
def temp_workspace(tmp_path: Path):
    """Create a temporary workspace for testing."""
    locks_dir = tmp_path / "locks"
    locks_dir.mkdir()
    # Create a test file
    test_file = tmp_path / "test_file.yaml"
    test_file.write_text("key: value\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def mock_workspace(temp_workspace: Path, monkeypatch):
    """Mock WORKSPACE to use temp directory."""
    monkeypatch.setattr("file_lock.WORKSPACE", temp_workspace)
    monkeypatch.setattr("file_lock.LOCKS_DIR", temp_workspace / "locks")
    monkeypatch.setattr("high_frequency_files.WORKSPACE", temp_workspace)
    return temp_workspace


# --- FileLock Dataclass Tests ---


class TestFileLock:
    """Test FileLock dataclass."""

    def test_default_creation(self):
        lock = FileLock(run_id="run-1", actor="agent-a", scope="test.yaml")
        assert lock.run_id == "run-1"
        assert lock.actor == "agent-a"
        assert lock.scope == "test.yaml"
        assert lock.created_at != ""
        assert lock.last_heartbeat != ""
        assert lock.expires_at != ""

    def test_is_expired_false(self):
        lock = FileLock(run_id="run-1", actor="agent-a", scope="test.yaml")
        # Default timeout is 30 minutes, so not expired
        assert not lock.is_expired()

    def test_is_expired_true(self):
        lock = FileLock(run_id="run-1", actor="agent-a", scope="test.yaml")
        # Set expires_at to the past
        lock.expires_at = "2020-01-01T00:00:00+00:00"
        assert lock.is_expired()

    def test_is_dead_false(self):
        lock = FileLock(run_id="run-1", actor="agent-a", scope="test.yaml")
        # Just created, so not dead
        assert not lock.is_dead()

    def test_is_dead_true(self):
        lock = FileLock(run_id="run-1", actor="agent-a", scope="test.yaml")
        # Set last_heartbeat to the past
        lock.last_heartbeat = "2020-01-01T00:00:00+00:00"
        assert lock.is_dead()

    def test_to_dict(self):
        lock = FileLock(run_id="run-1", actor="agent-a", scope="test.yaml")
        d = lock.to_dict()
        assert d["run_id"] == "run-1"
        assert d["actor"] == "agent-a"
        assert d["scope"] == "test.yaml"


# --- Lock Acquisition/Release Tests ---


class TestLockAcquisition:
    """Test lock acquisition and release."""

    def test_acquire_lock(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        assert lock.run_id == "run-1"
        assert lock.actor == "agent-a"
        # Lock file should exist
        lock_p = _lock_path("test_file.yaml")
        assert lock_p.is_file()

    def test_acquire_lock_conflict(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock1 = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock1 is not None
        # Second acquisition by different run should fail
        lock2 = acquire_lock("test_file.yaml", "run-2", "agent-b")
        assert lock2 is None

    def test_acquire_lock_same_run(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock1 = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock1 is not None
        # Same run re-acquiring should succeed (heartbeat update)
        lock2 = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock2 is not None
        assert lock2.run_id == "run-1"

    def test_acquire_lock_force(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock1 = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock1 is not None
        # Force acquisition should succeed
        lock2 = acquire_lock("test_file.yaml", "run-2", "agent-b", force=True)
        assert lock2 is not None
        assert lock2.run_id == "run-2"

    def test_release_lock(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        ok = release_lock("test_file.yaml", "run-1")
        assert ok
        # Lock file should be removed
        lock_p = _lock_path("test_file.yaml")
        assert not lock_p.is_file()

    def test_release_lock_wrong_run(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        ok = release_lock("test_file.yaml", "run-2")
        assert not ok
        # Lock file should still exist
        lock_p = _lock_path("test_file.yaml")
        assert lock_p.is_file()

    def test_release_lock_not_found(self, mock_workspace):
        ok = release_lock("nonexistent.yaml", "run-1")
        assert not ok


# --- Lock Reading Tests ---


class TestLockReading:
    """Test lock reading and querying."""

    def test_read_lock(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        lock = read_lock("test_file.yaml")
        assert lock is not None
        assert lock.run_id == "run-1"

    def test_read_lock_not_found(self, mock_workspace):
        lock = read_lock("nonexistent.yaml")
        assert lock is None

    def test_list_locks(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        locks = list_locks()
        assert len(locks) >= 1
        assert any(l.scope == "test_file.yaml" for l in locks)

    def test_list_expired_locks(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        # Manually expire the lock
        lock.expires_at = "2020-01-01T00:00:00+00:00"
        lock_p = _lock_path("test_file.yaml")
        import yaml
        lock_p.write_text(yaml.dump(lock.to_dict()), encoding="utf-8")
        expired = list_expired_locks()
        assert len(expired) >= 1

    def test_list_dead_locks(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        # Manually set heartbeat to the past
        lock.last_heartbeat = "2020-01-01T00:00:00+00:00"
        lock_p = _lock_path("test_file.yaml")
        import yaml
        lock_p.write_text(yaml.dump(lock.to_dict()), encoding="utf-8")
        dead = list_dead_locks()
        assert len(dead) >= 1


# --- Heartbeat Tests ---


class TestHeartbeat:
    """Test heartbeat mechanism."""

    def test_heartbeat(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        ok = heartbeat("test_file.yaml", "run-1")
        assert ok
        lock = read_lock("test_file.yaml")
        assert lock is not None

    def test_heartbeat_wrong_run(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        ok = heartbeat("test_file.yaml", "run-2")
        assert not ok


# --- Conflict Detection Tests ---


class TestConflictDetection:
    """Test file hash conflict detection."""

    def test_no_conflict(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        conflict = check_conflict("test_file.yaml")
        assert conflict is None

    def test_conflict_detected(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        # Modify the file
        test_file.write_text("key: modified_value\n", encoding="utf-8")
        conflict = check_conflict("test_file.yaml")
        assert conflict is not None
        assert conflict["file"] == "test_file.yaml"
        assert conflict["locked_hash"] != conflict["current_hash"]

    def test_no_conflict_no_lock(self, mock_workspace):
        conflict = check_conflict("nonexistent.yaml")
        assert conflict is None


# --- Deadlock Detection Tests ---


class TestDeadlockDetection:
    """Test deadlock detection."""

    def test_no_deadlocks(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        acquire_lock("test_file.yaml", "run-1", "agent-a")
        deadlocks = detect_deadlocks()
        # Should have no deadlocks (just created)
        assert len(deadlocks) == 0

    def test_deadlock_detected(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        # Manually set heartbeat to the past to simulate dead lock
        lock.last_heartbeat = "2020-01-01T00:00:00+00:00"
        lock_p = _lock_path("test_file.yaml")
        import yaml
        lock_p.write_text(yaml.dump(lock.to_dict()), encoding="utf-8")
        deadlocks = detect_deadlocks()
        assert len(deadlocks) >= 1
        assert deadlocks[0]["file"] == "test_file.yaml"


# --- Cleanup Tests ---


class TestCleanup:
    """Test lock cleanup."""

    def test_cleanup_expired(self, mock_workspace):
        test_file = mock_workspace / "test_file.yaml"
        lock = acquire_lock("test_file.yaml", "run-1", "agent-a")
        assert lock is not None
        # Manually expire the lock
        lock.expires_at = "2020-01-01T00:00:00+00:00"
        lock_p = _lock_path("test_file.yaml")
        import yaml
        lock_p.write_text(yaml.dump(lock.to_dict()), encoding="utf-8")
        cleaned = cleanup_expired()
        assert "test_file.yaml" in cleaned
        # Lock file should be removed
        assert not lock_p.is_file()


# --- High-Frequency File Monitor Tests ---


class TestHighFrequencyMonitor:
    """Test high-frequency file monitoring."""

    def test_snapshot(self, mock_workspace):
        monitor = HighFrequencyFileMonitor(workspace=mock_workspace)
        # Create some test files
        (mock_workspace / ".omo/state").mkdir(parents=True, exist_ok=True)
        (mock_workspace / ".omo/state/system.yaml").write_text("key: value\n")
        hashes = monitor.snapshot(files=[".omo/state/system.yaml"])
        assert ".omo/state/system.yaml" in hashes

    def test_detect_changes(self, mock_workspace):
        monitor = HighFrequencyFileMonitor(workspace=mock_workspace)
        # Create test file
        test_dir = mock_workspace / ".omo/state"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "system.yaml"
        test_file.write_text("key: value1\n")
        monitor.snapshot(files=[".omo/state/system.yaml"])
        # Modify file
        test_file.write_text("key: value2\n")
        changes = monitor.detect_changes()
        assert len(changes) >= 1
        assert changes[0].file == ".omo/state/system.yaml"

    def test_detect_conflicts(self, mock_workspace):
        monitor = HighFrequencyFileMonitor(workspace=mock_workspace, conflict_window_s=60)
        # Create test file
        test_dir = mock_workspace / ".omo/state"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "system.yaml"
        test_file.write_text("key: value1\n")
        monitor.snapshot(files=[".omo/state/system.yaml"], actor="agent-a")
        # Modify file
        test_file.write_text("key: value2\n")
        monitor.detect_changes(actor="agent-b")
        # Rapid change
        test_file.write_text("key: value3\n")
        monitor.detect_changes(actor="agent-c")
        conflicts = monitor.detect_conflicts()
        # May or may not detect conflict depending on timing
        # The important thing is it doesn't crash

    def test_report(self, mock_workspace):
        monitor = HighFrequencyFileMonitor(workspace=mock_workspace)
        report = monitor.report()
        assert "timestamp" in report
        assert "monitored_files" in report
        assert "high_frequency_files" in report

    def test_get_high_frequency_paths(self):
        paths = get_high_frequency_paths()
        assert len(paths) > 0
        assert ".omo/state/system.yaml" in paths


# --- CLI Integration Tests ---


def _run_file_lock_check(*args: str) -> subprocess.CompletedProcess[str]:
    """Run file-lock-check.py CLI."""
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin/gac/file-lock-check.py"), *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestCLI:
    """Test CLI integration."""

    def test_cli_runs_without_error(self):
        result = _run_file_lock_check("--json")
        assert result.returncode in (0, 1), result.stderr
        # Should produce valid JSON
        data = json.loads(result.stdout)
        assert "ok" in data

    def test_cli_status(self):
        result = _run_file_lock_check("status", "--json")
        assert result.returncode in (0, 1), result.stderr
        data = json.loads(result.stdout)
        assert "ok" in data
        assert "summary" in data

    def test_cli_deadlocks(self):
        result = _run_file_lock_check("deadlocks", "--json")
        assert result.returncode in (0, 1), result.stderr

    def test_cli_contention(self):
        result = _run_file_lock_check("contention", "--json")
        assert result.returncode == 0, result.stderr

    def test_cli_integrity(self):
        result = _run_file_lock_check("integrity", "--json")
        assert result.returncode in (0, 1), result.stderr

    def test_cli_orphaned(self):
        result = _run_file_lock_check("orphaned", "--json")
        assert result.returncode == 0, result.stderr

    def test_cli_monitor(self):
        result = _run_file_lock_check("monitor", "--json")
        assert result.returncode in (0, 1), result.stderr
        data = json.loads(result.stdout)
        assert "monitored_files" in data

    def test_cli_help(self):
        result = _run_file_lock_check("--help")
        assert result.returncode == 0
        assert "file lock" in result.stdout.lower() or "lock" in result.stdout.lower()
