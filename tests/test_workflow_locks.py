"""Tests for BET-Y1Q1-T1-00: lock heartbeat, stale detection, prune."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

import omo.workflow.lifecycle as lifecycle_mod
from omo.workflow.core import WorkflowError
from omo.workflow.lifecycle import (
    _HEARTBEAT_STALE_SECONDS,
    _classify_existing_lock,
    acquire_locks,
    claim_run,
    closeout_run,
    heartbeat_lock,
    heartbeat_run,
    prune_stale_locks,
    sanitize_lock_name,
    scan_locks,
)


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


# ---------------------------------------------------------------------------
# SR-01 heartbeat hardening: heartbeat_run + CLI + lifecycle wiring
# ---------------------------------------------------------------------------


def _run_dir(registry: dict) -> Path:
    return lifecycle_mod.WORKSPACE / registry.get("runner", {}).get(
        "run_state_dir", ".omo/_delivery/agent-workflows/runs"
    )


def _seed_run(
    registry: dict,
    run_id: str = "run-1",
    lock_scopes: list[str] | None = None,
    status: str = "active",
) -> Path:
    """Create a run YAML plus its lock files. Returns the run file path."""
    scopes = lock_scopes or ["path:foo.py"]
    lock_paths = acquire_locks(registry, scopes, run_id, "agent-a", False)
    rdir = _run_dir(registry)
    rdir.mkdir(parents=True, exist_ok=True)
    now_ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record: dict = {
        "run_id": run_id,
        "workflow_id": "test-wf",
        "status": status,
        "actor": "agent-a",
        "created_at": now_ts,
        "updated_at": now_ts,
        "locks": lock_paths,
    }
    run_path = rdir / f"{run_id}.yaml"
    run_path.write_text(
        yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return run_path


def _lock_file_for_scope(registry: dict, scope: str) -> Path:
    return _lock_dir(registry) / f"{sanitize_lock_name(scope)}.lock.yaml"


def test_heartbeat_run_multi_lock_success(registry: dict) -> None:
    """Multiple locks all renewed in a single heartbeat_run call."""
    scopes = ["path:alpha.py", "path:beta.py"]
    _seed_run(registry, "run-multi", lock_scopes=scopes)
    receipt = heartbeat_run(registry, "run-multi")
    assert receipt["run_id"] == "run-multi"
    assert receipt["count"] == 2
    assert len(receipt["renewed"]) == 2
    assert "heartbeat_at" in receipt
    for scope in scopes:
        data = yaml.safe_load(_lock_file_for_scope(registry, scope).read_text())
        assert data["last_heartbeat"] == receipt["heartbeat_at"]


def test_heartbeat_run_preserves_immutable_fields(registry: dict) -> None:
    """Only last_heartbeat changes; created_at, expires_at, run_id, actor, scope frozen."""
    _seed_run(registry, "run-preserve", lock_scopes=["path:keep.py"])
    lock_file = _lock_file_for_scope(registry, "path:keep.py")
    before = yaml.safe_load(lock_file.read_text())
    time.sleep(1.1)  # utc_now() is second-level precision
    heartbeat_run(registry, "run-preserve")
    after = yaml.safe_load(lock_file.read_text())
    assert after["last_heartbeat"] > before["last_heartbeat"]
    for key in ("created_at", "expires_at", "run_id", "actor", "scope"):
        assert after[key] == before[key]


def test_heartbeat_run_rejects_closed_run(registry: dict) -> None:
    """Closed run cannot heartbeat."""
    _seed_run(registry, "run-closed", status="ok")
    with pytest.raises(WorkflowError, match="active"):
        heartbeat_run(registry, "run-closed")


def test_heartbeat_run_missing_lock(registry: dict) -> None:
    """Lock file listed by run but absent on disk → WorkflowError."""
    _seed_run(registry, "run-missing", lock_scopes=["path:gone.py"])
    _lock_file_for_scope(registry, "path:gone.py").unlink()
    with pytest.raises(WorkflowError, match="missing"):
        heartbeat_run(registry, "run-missing")


def test_heartbeat_run_malformed_yaml(registry: dict) -> None:
    """Malformed lock (non-mapping YAML) → WorkflowError."""
    _seed_run(registry, "run-bad-yaml", lock_scopes=["path:bad.py"])
    _lock_file_for_scope(registry, "path:bad.py").write_text(
        "not-a-mapping-just-a-string\n", encoding="utf-8"
    )
    with pytest.raises(WorkflowError, match="malformed"):
        heartbeat_run(registry, "run-bad-yaml")


def test_heartbeat_run_mismatched_run_id(registry: dict) -> None:
    """Lock owned by different run_id → WorkflowError."""
    _seed_run(registry, "run-mismatch", lock_scopes=["path:wrong.py"])
    lock_file = _lock_file_for_scope(registry, "path:wrong.py")
    data = yaml.safe_load(lock_file.read_text())
    data["run_id"] = "somebody-else"
    lock_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="run_id"):
        heartbeat_run(registry, "run-mismatch")


def test_heartbeat_run_path_escape(registry: dict) -> None:
    """Lock path outside lock_state_dir → WorkflowError."""
    _seed_run(registry, "run-escape", lock_scopes=["path:ok.py"])
    run_path = _run_dir(registry) / "run-escape.yaml"
    data = yaml.safe_load(run_path.read_text())
    data["locks"] = ["../../etc/shadow.lock.yaml"]
    run_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="escape|outside"):
        heartbeat_run(registry, "run-escape")


def test_heartbeat_run_no_partial_mutation(registry: dict) -> None:
    """When one lock fails validation, all locks remain unchanged."""
    _seed_run(registry, "run-partial", lock_scopes=["path:good.py", "path:bad.py"])
    _lock_file_for_scope(registry, "path:bad.py").write_text(
        ":::not[yaml::", encoding="utf-8"
    )
    good_lock = _lock_file_for_scope(registry, "path:good.py")
    good_before = good_lock.read_text()
    with pytest.raises(WorkflowError):
        heartbeat_run(registry, "run-partial")
    assert good_lock.read_text() == good_before


def test_heartbeat_cli_success_json(
    registry: dict, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI heartbeat --json outputs receipt and rc=0."""
    _seed_run(registry, "run-cli-ok", lock_scopes=["path:cli.py"])
    import omo.workflow.cli as cli_mod

    monkeypatch.setattr(cli_mod, "load_registry", lambda _path: registry)
    monkeypatch.setattr(cli_mod, "is_default_registry_path", lambda _path: False)
    rc = cli_mod.main(["heartbeat", "run-cli-ok", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run_id"] == "run-cli-ok"
    assert out["count"] == 1


def test_heartbeat_cli_failure_rc2(
    registry: dict, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI heartbeat on non-existent run → rc=2."""
    import omo.workflow.cli as cli_mod

    monkeypatch.setattr(cli_mod, "load_registry", lambda _path: registry)
    monkeypatch.setattr(cli_mod, "is_default_registry_path", lambda _path: False)
    rc = cli_mod.main(["heartbeat", "no-such-run", "--json"])
    assert rc == 2


def test_heartbeat_wired_into_claim(
    registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """claim_run renews heartbeat before acquiring new locks."""
    _seed_run(registry, "run-claim", lock_scopes=["path:init.py"])

    heartbeat_called: list[str] = []
    original = lifecycle_mod.heartbeat_run

    def spy(reg: dict, rid: str) -> dict:
        heartbeat_called.append(rid)
        return original(reg, rid)

    monkeypatch.setattr(lifecycle_mod, "heartbeat_run", spy)

    claim_run(
        registry,
        "run-claim",
        "agent-a",
        paths=["path:new.py"],
        surfaces=[],
        force_lock=False,
        affected_hash="dummy",
    )
    assert "run-claim" in heartbeat_called


def test_heartbeat_wired_into_closeout_ok(
    registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """closeout status=ok calls heartbeat before verify/observe."""
    _seed_run(registry, "run-co", lock_scopes=["path:co.py"])

    heartbeat_called: list[str] = []
    original = lifecycle_mod.heartbeat_run

    def spy(reg: dict, rid: str) -> dict:
        heartbeat_called.append(rid)
        return original(reg, rid)

    monkeypatch.setattr(lifecycle_mod, "heartbeat_run", spy)

    from omo.workflow import diagnostics as diag_mod

    monkeypatch.setattr(
        diag_mod,
        "build_verify_report",
        lambda *a, **kw: {"ok": False, "check_count": 0, "checks": []},
    )

    with pytest.raises(WorkflowError, match="closeout blocked"):
        closeout_run(registry, "run-co", "ok", [], [], False, False, False, False)

    assert "run-co" in heartbeat_called


# ---------------------------------------------------------------------------
# SR-01 fix-only: atomic writes + CLI verify renewal + symlink escape
# ---------------------------------------------------------------------------


def test_heartbeat_run_uses_atomic_write(
    registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """heartbeat_run must use write_yaml_atomic, not raw Path.write_text."""
    _seed_run(registry, "run-atomic", lock_scopes=["path:atomic.py"])

    import omo.omo_io as omo_io_mod

    atomic_calls: list[Path] = []
    original = omo_io_mod.write_yaml_atomic

    def spy(path: Path, data: dict) -> None:
        atomic_calls.append(path)
        original(path, data)

    monkeypatch.setattr(lifecycle_mod, "write_yaml_atomic", spy, raising=False)

    receipt = heartbeat_run(registry, "run-atomic")
    assert receipt["count"] == 1
    assert len(atomic_calls) == 1
    assert atomic_calls[0].name == "path_atomic.py.lock.yaml"


def test_heartbeat_run_symlink_escape(registry: dict) -> None:
    """Symlink inside lock_dir pointing outside → WorkflowError."""
    _seed_run(registry, "run-symlink", lock_scopes=["path:symlinked.py"])
    lock_file = _lock_file_for_scope(registry, "path:symlinked.py")
    # File outside the lock directory
    outside = _lock_dir(registry).parent / "outside_target.yaml"
    outside.write_text("hijacked: true\n", encoding="utf-8")
    # Replace the real lock with a symlink pointing outside
    lock_file.unlink()
    os.symlink(outside, lock_file)
    with pytest.raises(WorkflowError, match="escape|outside"):
        heartbeat_run(registry, "run-symlink")


def test_cli_verify_explicit_run_id_renews_heartbeat(
    registry: dict, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI verify with explicit run_id renews heartbeat before verify."""
    _seed_run(registry, "run-verify", lock_scopes=["path:verify.py"])
    import omo.workflow.cli as cli_mod

    heartbeat_called: list[str] = []
    original_hb = lifecycle_mod.heartbeat_run

    def hb_spy(reg: dict, rid: str) -> dict:
        heartbeat_called.append(rid)
        return original_hb(reg, rid)

    monkeypatch.setattr(cli_mod, "heartbeat_run", hb_spy)
    monkeypatch.setattr(cli_mod, "load_registry", lambda _p: registry)
    monkeypatch.setattr(cli_mod, "is_default_registry_path", lambda _p: False)
    monkeypatch.setattr(
        cli_mod,
        "build_verify_report",
        lambda *a, **kw: {"ok": True, "check_count": 0, "checks": []},
    )

    rc = cli_mod.main(["verify", "run-verify", "--all", "--json"])
    assert rc == 0
    assert "run-verify" in heartbeat_called


def test_cli_verify_no_run_id_skips_heartbeat(
    registry: dict, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI verify without run_id does NOT call heartbeat_run."""
    import omo.workflow.cli as cli_mod

    heartbeat_called: list[str] = []

    def hb_spy(reg: dict, rid: str) -> dict:
        heartbeat_called.append(rid)
        return {
            "run_id": rid,
            "heartbeat_at": "",
            "renewed": [],
            "count": 0,
        }

    monkeypatch.setattr(cli_mod, "heartbeat_run", hb_spy)
    monkeypatch.setattr(cli_mod, "load_registry", lambda _p: registry)
    monkeypatch.setattr(cli_mod, "is_default_registry_path", lambda _p: False)
    monkeypatch.setattr(
        cli_mod,
        "build_verify_report",
        lambda *a, **kw: {"ok": True, "check_count": 0, "checks": []},
    )

    rc = cli_mod.main(["verify", "--all", "--json"])
    assert rc == 0
    assert heartbeat_called == []


# ---------------------------------------------------------------------------
# Final review blockers: payload locks type validation + read-failure wrapping
# ---------------------------------------------------------------------------


def test_heartbeat_run_integer_locks_raises(registry: dict) -> None:
    """Run payload with integer locks field → WorkflowError before any mutation."""
    _seed_run(registry, "run-int", lock_scopes=["path:foo.py"])
    run_path = _run_dir(registry) / "run-int.yaml"
    data = yaml.safe_load(run_path.read_text())
    data["locks"] = 42
    run_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="locks must be a list"):
        heartbeat_run(registry, "run-int")


def test_heartbeat_run_mapping_locks_raises(registry: dict) -> None:
    """Run payload with mapping locks field → WorkflowError."""
    _seed_run(registry, "run-map", lock_scopes=["path:foo.py"])
    run_path = _run_dir(registry) / "run-map.yaml"
    data = yaml.safe_load(run_path.read_text())
    data["locks"] = {"path": "bad"}
    run_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="locks must be a list"):
        heartbeat_run(registry, "run-map")


def test_heartbeat_run_scalar_string_locks_raises(registry: dict) -> None:
    """Run payload with scalar string locks field → WorkflowError."""
    _seed_run(registry, "run-scalar", lock_scopes=["path:foo.py"])
    run_path = _run_dir(registry) / "run-scalar.yaml"
    data = yaml.safe_load(run_path.read_text())
    data["locks"] = "not-a-list"
    run_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="locks must be a list"):
        heartbeat_run(registry, "run-scalar")


def test_heartbeat_run_mixed_list_member_raises(registry: dict) -> None:
    """Locks list containing a non-string entry → WorkflowError."""
    _seed_run(registry, "run-mixed", lock_scopes=["path:good.py"])
    run_path = _run_dir(registry) / "run-mixed.yaml"
    data = yaml.safe_load(run_path.read_text())
    data["locks"] = ["locks/path_good.py.lock.yaml", 42]
    run_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="invalid"):
        heartbeat_run(registry, "run-mixed")


def test_heartbeat_run_empty_string_entry_raises(registry: dict) -> None:
    """Locks list containing an empty string → WorkflowError."""
    _seed_run(registry, "run-empty-str", lock_scopes=["path:good.py"])
    run_path = _run_dir(registry) / "run-empty-str.yaml"
    data = yaml.safe_load(run_path.read_text())
    data["locks"] = ["locks/path_good.py.lock.yaml", ""]
    run_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(WorkflowError, match="invalid"):
        heartbeat_run(registry, "run-empty-str")


def test_heartbeat_run_oserror_on_read(
    registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OSError during lock read → WorkflowError, not bare OSError."""
    _seed_run(registry, "run-oserr", lock_scopes=["path:target.py"])
    lock_file = _lock_file_for_scope(registry, "path:target.py")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == lock_file:
            raise OSError("simulated IO failure")
        return original_read_text(self, *args, **kwargs)  # type: ignore[call-arg]

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    with pytest.raises(WorkflowError, match="unreadable"):
        heartbeat_run(registry, "run-oserr")


def test_heartbeat_run_unicodeerror_on_read(
    registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UnicodeDecodeError during lock read → WorkflowError."""
    _seed_run(registry, "run-unicode", lock_scopes=["path:target.py"])
    lock_file = _lock_file_for_scope(registry, "path:target.py")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == lock_file:
            raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid start byte")
        return original_read_text(self, *args, **kwargs)  # type: ignore[call-arg]

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    with pytest.raises(WorkflowError, match="malformed|encoding"):
        heartbeat_run(registry, "run-unicode")


def test_heartbeat_run_no_partial_mutation_on_oserror(
    registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When second lock read raises OSError, first lock remains unchanged."""
    _seed_run(
        registry,
        "run-no-partial-oserr",
        lock_scopes=["path:first.py", "path:second.py"],
    )
    second_lock = _lock_file_for_scope(registry, "path:second.py")
    first_lock = _lock_file_for_scope(registry, "path:first.py")
    first_before = first_lock.read_text()

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == second_lock:
            raise OSError("simulated IO failure on second lock")
        return original_read_text(self, *args, **kwargs)  # type: ignore[call-arg]

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    with pytest.raises(WorkflowError):
        heartbeat_run(registry, "run-no-partial-oserr")
    assert first_lock.read_text() == first_before
