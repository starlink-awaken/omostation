"""Tests for BET-Y1Q1-T1-00: lock heartbeat, stale detection, prune."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

import omo.workflow.lifecycle as lifecycle_mod
from omo.workflow.lifecycle import (
    _classify_existing_lock,
    _HEARTBEAT_STALE_SECONDS,
    acquire_locks,
    heartbeat_lock,
    prune_stale_locks,
    scan_locks,
)
from omo.workflow.core import WorkflowError


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    import omo.workflow.core as core_mod

    monkeypatch.setattr(core_mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(lifecycle_mod, "WORKSPACE", tmp_path)
    return {"runner": {"lock_state_dir": "locks"}}


def _make_lock(lock_dir: Path, name: str, payload: dict) -> Path:
    path = lock_dir / name
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def _lock_dir(registry: dict) -> Path:
    return lifecycle_mod.WORKSPACE / registry["runner"]["lock_state_dir"]


def test_acquire_adds_heartbeat(registry: dict) -> None:
    locks = acquire_locks(registry, ["path:foo.py"], "run-1", "agent-a", False)
    assert len(locks) == 1
    lock_file = _lock_dir(registry) / "path_foo.py.lock.yaml"
    data = yaml.safe_load(lock_file.read_text())
    assert "last_heartbeat" in data
    assert data["run_id"] == "run-1"


def test_classify_live_lock(registry: dict) -> None:
    ldir = _lock_dir(registry)
    now = datetime.now(UTC).isoformat()
    _make_lock(
        ldir,
        "test.lock.yaml",
        {
            "run_id": "r1",
            "actor": "a",
            "scope": "s",
            "created_at": now,
            "last_heartbeat": now,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    result = _classify_existing_lock(ldir / "test.lock.yaml")
    assert result["kind"] == "live"


def test_classify_expired_lock(registry: dict) -> None:
    ldir = _lock_dir(registry)
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    _make_lock(
        ldir,
        "test.lock.yaml",
        {
            "run_id": "r1",
            "actor": "a",
            "scope": "s",
            "created_at": past,
            "last_heartbeat": past,
            "expires_at": past,
        },
    )
    result = _classify_existing_lock(ldir / "test.lock.yaml")
    assert result["kind"] == "zombie_expired"


def test_classify_stale_heartbeat(registry: dict) -> None:
    ldir = _lock_dir(registry)
    now = datetime.now(UTC)
    stale_hb = (now - timedelta(seconds=_HEARTBEAT_STALE_SECONDS + 100)).isoformat()
    _make_lock(
        ldir,
        "test.lock.yaml",
        {
            "run_id": "r1",
            "actor": "a",
            "scope": "s",
            "created_at": stale_hb,
            "last_heartbeat": stale_hb,
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        },
    )
    result = _classify_existing_lock(ldir / "test.lock.yaml")
    assert result["kind"] == "zombie_stale_heartbeat"


def test_acquire_replaces_zombie_lock(registry: dict) -> None:
    ldir = _lock_dir(registry)
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    _make_lock(
        ldir,
        "path_foo.py.lock.yaml",
        {
            "run_id": "old-run",
            "actor": "old-agent",
            "scope": "path:foo.py",
            "created_at": past,
            "last_heartbeat": past,
            "expires_at": past,
        },
    )
    locks = acquire_locks(registry, ["path:foo.py"], "new-run", "agent-b", False)
    assert len(locks) == 1
    data = yaml.safe_load((ldir / "path_foo.py.lock.yaml").read_text())
    assert data["run_id"] == "new-run"


def test_acquire_blocks_on_live_lock(registry: dict) -> None:
    ldir = _lock_dir(registry)
    now = datetime.now(UTC).isoformat()
    _make_lock(
        ldir,
        "path_foo.py.lock.yaml",
        {
            "run_id": "live-run",
            "actor": "agent-a",
            "scope": "path:foo.py",
            "created_at": now,
            "last_heartbeat": now,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    with pytest.raises(WorkflowError, match="lock HELD.*live"):
        acquire_locks(registry, ["path:foo.py"], "new-run", "agent-b", False)


def test_heartbeat_updates_timestamp(registry: dict) -> None:
    acquire_locks(registry, ["path:foo.py"], "run-1", "agent-a", False)
    lock_file = _lock_dir(registry) / "path_foo.py.lock.yaml"
    old_data = yaml.safe_load(lock_file.read_text())
    time.sleep(0.01)
    heartbeat_lock(lock_file)
    new_data = yaml.safe_load(lock_file.read_text())
    assert new_data["last_heartbeat"] >= old_data["last_heartbeat"]


def test_scan_locks_report(registry: dict) -> None:
    acquire_locks(registry, ["path:a.py"], "run-1", "agent-a", False)
    ldir = _lock_dir(registry)
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    _make_lock(
        ldir,
        "path_b.py.lock.yaml",
        {
            "run_id": "old-run",
            "actor": "old",
            "scope": "path:b.py",
            "created_at": past,
            "last_heartbeat": past,
            "expires_at": past,
        },
    )
    report = scan_locks(registry)
    assert len(report) == 2
    kinds = {e["kind"] for e in report}
    assert "live" in kinds
    assert "zombie_expired" in kinds


def test_prune_stale_locks(registry: dict) -> None:
    acquire_locks(registry, ["path:a.py"], "run-1", "agent-a", False)
    ldir = _lock_dir(registry)
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    _make_lock(
        ldir,
        "path_b.py.lock.yaml",
        {
            "run_id": "old-run",
            "actor": "old",
            "scope": "path:b.py",
            "created_at": past,
            "last_heartbeat": past,
            "expires_at": past,
        },
    )
    pruned = prune_stale_locks(registry)
    assert len(pruned) == 1
    assert pruned[0]["kind"] == "zombie_expired"
    remaining = scan_locks(registry)
    assert len(remaining) == 1
    assert remaining[0]["kind"] == "live"
