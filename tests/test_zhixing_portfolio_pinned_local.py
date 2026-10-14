"""Exercise the delivered reader against real Git objects and both public probes."""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_zhixing_source_health_mirror import ASSETS, _portfolio, _refresh


RAW = (b"meta: {total_bets: 1}\r\nbets:\r\n"
       b"  - {id: pinned-bet, status: pending, title: original}\r\n  \r\n")
CHANGED = RAW.replace(b"pinned-bet", b"newer-bet").replace(b"original", b"changed")


def git(root, *args):
    result = subprocess.run([shutil.which("git"), "-C", str(root), *args],
                            capture_output=True, check=True)
    return result.stdout


def repository(tmp_path, raw=RAW):
    root = tmp_path / "producer"
    root.mkdir(parents=True)
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Portfolio Test")
    git(root, "config", "user.email", "portfolio-test@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "remote", "add", "origin", "https://github.com/starlink-awaken/omostation.git")
    ledger = root / "docs/plans/3y-bet-ledger.yaml"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(raw)
    git(root, "add", "docs")
    git(root, "commit", "-m", "original pinned ledger")
    return root, git(root, "rev-parse", "HEAD").decode().strip()


def snapshot(root):
    # Cover content, membership and mtimes of objects, refs, index and dirty files.
    return {p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(),
                                            p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def remote_object(tmp_path, local_root):
    raw = RAW + b"# independently committed remote object\r\n"
    remote, oid = repository(tmp_path / "remote", raw)
    assert git(remote, "show", f"{oid}:docs/plans/3y-bet-ledger.yaml") == raw
    missing = subprocess.run([shutil.which("git"), "-C", str(local_root), "cat-file", "-e", oid],
                             capture_output=True)
    assert missing.returncode != 0
    return oid, raw


def reader(monkeypatch, root, oid, remote_raw=RAW, main_error=False, blob_error=False):
    module = _portfolio(monkeypatch)
    monkeypatch.setattr(module, "GIT", shutil.which("git"))
    monkeypatch.setenv("PANORAMA_CODE_ROOT", str(root))
    original = module._read_cmd
    calls = []

    def command(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[0] != module.GH:
            return original(argv, **kwargs)
        if kwargs["phase"] == "remote_main_oid":
            if main_error:
                raise module._SourceFailure(kwargs["phase"], "main unavailable", timeout=True)
            return oid.encode()
        assert kwargs["phase"] == "remote_ledger_blob"
        assert argv[2] == f"repos/{module.REPOSITORY}/contents/{module.LEDGER_PATH}?ref={oid}"
        if blob_error:
            raise module._SourceFailure(kwargs["phase"], "remote blob unavailable", timeout=True)
        return remote_raw

    monkeypatch.setattr(module, "_read_cmd", command)
    return module, calls


def bound_interface(monkeypatch, tmp_path, oid, raw=RAW):
    # Only the external immutable revision-store interface is supplied here;
    # identity, exact Git reads, binding/hash/clock checks execute delivered code.
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=3)).isoformat()
    body = {"state": "OBSERVED", "source_lane": "REMOTE_MAIN", "sha": oid,
            "source": f"github://starlink-awaken/omostation@{oid}/docs/plans/3y-bet-ledger.yaml",
            "ledger_digest_kind": "raw_bytes", "ledger_sha256": hashlib.sha256(raw).hexdigest(),
            "observed_at": old}
    state = tmp_path / "state"
    state.mkdir()
    record = state / "immutable-revision.json"
    record.write_text(json.dumps({"producer_root_oid": oid,
        "artifact_bodies": {"data": json.dumps({"portfolio": body})},
        "generated_at": (now - timedelta(hours=2)).isoformat(),
        "fresh_until": (now + timedelta(minutes=5)).isoformat(),
        "revision_id": "bound-test-revision", "manifest_sha256": "d" * 64}))
    external = types.ModuleType("runtime_paths")

    class ProjectionRevisionStore:
        def __init__(self, root):
            assert root == state

        def load(self, require_fresh):
            assert require_fresh is False
            return types.SimpleNamespace(**json.loads(record.read_text()))

    external.ProjectionRevisionStore = ProjectionRevisionStore
    external.resolve_state_root = lambda: state
    monkeypatch.setitem(sys.modules, "runtime_paths", external)
    return state, old, record


def test_pinned_original_bytes_survive_newer_head_and_dirty_worktree(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    ledger = root / "docs/plans/3y-bet-ledger.yaml"
    ledger.write_bytes(CHANGED)
    git(root, "add", "docs")
    git(root, "commit", "-m", "newer main content")
    assert git(root, "rev-parse", "HEAD").decode().strip() != oid
    ledger.write_bytes(b"dirty uncommitted content")
    assert git(root, "status", "--porcelain")
    module, calls = reader(monkeypatch, root, oid)
    clocks = iter(["2026-10-14T00:00:00+00:00", "2026-10-14T00:00:01+00:00",
                   "2026-10-14T00:00:02+00:00"])
    monkeypatch.setattr(module, "_now", lambda: next(clocks))
    before = snapshot(root)
    raw, ledger, source = module.read_portfolio_source()
    assert raw == RAW and ledger["bets"][0]["id"] == "pinned-bet"
    assert source["sha"] == oid and source["ledger_sha256"] == hashlib.sha256(RAW).hexdigest()
    assert source["state"] == "OBSERVED" and source["source_lane"] == "REMOTE_MAIN"
    assert source["content_read_lane"] == "REMOTE_OID_LOCAL_OBJECT"
    assert source["remote_oid_observed_at"] == "2026-10-14T00:00:01+00:00"
    assert source["content_read_at"] == source["observed_at"] == "2026-10-14T00:00:02+00:00"
    assert [kwargs["phase"] for _, kwargs in calls] == [
        "remote_main_oid", "local_pinned_repository_identity",
        "local_pinned_repository_identity", "local_pinned_ledger_blob"]
    assert snapshot(root) == before


def test_real_replacement_cannot_substitute_authoritative_object(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    (root / "docs/plans/3y-bet-ledger.yaml").write_bytes(CHANGED)
    git(root, "add", "docs")
    git(root, "commit", "-m", "replacement ledger")
    replacement = git(root, "rev-parse", "HEAD").decode().strip()
    git(root, "replace", oid, replacement)
    assert git(root, "show", f"{oid}:docs/plans/3y-bet-ledger.yaml") == CHANGED
    module, calls = reader(monkeypatch, root, oid)
    before = snapshot(root)
    raw, _, source = module.read_portfolio_source()
    assert raw == RAW and source["ledger_sha256"] == hashlib.sha256(RAW).hexdigest()
    assert source["content_read_lane"] == "REMOTE_OID_LOCAL_OBJECT"
    assert all(argv[1] == "--no-replace-objects" for argv, _ in calls if argv[0] == module.GIT)
    assert snapshot(root) == before


@pytest.mark.parametrize("failure", ["missing-object", "wrong-origin", "wrong-top", "missing-root"])
def test_local_failure_uses_original_same_oid_remote_path(monkeypatch, tmp_path, failure):
    root, actual_oid = repository(tmp_path)
    oid, expected = remote_object(tmp_path, root) if failure == "missing-object" else (actual_oid, RAW)
    if failure == "wrong-origin":
        git(root, "remote", "set-url", "origin", "https://github.com/untrusted/producer.git")
    configured = root / "docs" if failure == "wrong-top" else root
    module, calls = reader(monkeypatch, configured, oid, remote_raw=expected)
    if failure == "missing-root":
        monkeypatch.delenv("PANORAMA_CODE_ROOT")
    before = snapshot(root)
    raw, _, source = module.read_portfolio_source()
    assert raw == expected and source["sha"] == oid
    assert source["state"] == "OBSERVED" and source["source_lane"] == "REMOTE_MAIN"
    assert source["content_read_lane"] == "REMOTE_OID_REMOTE_BLOB"
    assert source["local_error"]["phase"].startswith("local_pinned_")
    assert "remote_error" not in source
    remotes = [(argv, kw) for argv, kw in calls if kw["phase"] == "remote_ledger_blob"]
    assert len(remotes) == 1 and remotes[0][1]["timeout"] == 25
    assert remotes[0][1]["maximum"] == 8 * 1024 * 1024
    assert snapshot(root) == before


def test_failed_main_keeps_bound_original_clock_and_does_not_try_new_local_lane(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    (root / "docs/plans/3y-bet-ledger.yaml").write_bytes(CHANGED)
    git(root, "add", "docs")
    git(root, "commit", "-m", "newer local object while remote main unavailable")
    assert git(root, "rev-parse", "HEAD").decode().strip() != oid
    module, calls = reader(monkeypatch, root, oid, main_error=True)
    state, old, _ = bound_interface(monkeypatch, tmp_path, oid)
    before = (snapshot(root), snapshot(state))
    raw, _, source = module.read_portfolio_source()
    assert raw == RAW and source["sha"] == oid
    assert source["state"] == "PARTIAL" and source["source_lane"] == "BOUND_BASELINE"
    assert source["observed_at"] == old and source["fetched_at"] != old
    assert source["remote_error"]["phase"] == "remote_main_oid"
    assert "local_error" not in source and "remote_oid_observed_at" not in source
    assert not any(kwargs["phase"].startswith("local_pinned_") for _, kwargs in calls)
    assert (snapshot(root), snapshot(state)) == before


def test_local_and_remote_blob_failures_stay_separate_from_old_bound_clock(monkeypatch, tmp_path):
    root, bound_oid = repository(tmp_path)
    remote_oid, _ = remote_object(tmp_path, root)
    module, calls = reader(monkeypatch, root, remote_oid, blob_error=True)
    state, old, _ = bound_interface(monkeypatch, tmp_path, bound_oid)
    before = (snapshot(root), snapshot(state))
    raw, _, source = module.read_portfolio_source()
    assert raw == RAW and source["sha"] == bound_oid
    assert source["state"] == "PARTIAL" and source["observed_at"] == old
    assert source["local_error"]["phase"] == "local_pinned_ledger_blob"
    assert source["remote_error"]["phase"] == "remote_ledger_blob"
    assert (snapshot(root), snapshot(state)) == before


def test_failed_bound_digest_is_not_accepted_as_old_baseline(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    module, _ = reader(monkeypatch, root, oid, main_error=True)
    _, _, record = bound_interface(monkeypatch, tmp_path, oid, raw=CHANGED)
    before = record.read_bytes()
    with pytest.raises(module.CollectionError, match="bound portfolio digest/algorithm mismatch"):
        module.read_portfolio_source()
    assert record.read_bytes() == before


def test_local_lane_has_one_shared_small_deadline_and_preserves_remote_budget(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    module, calls = reader(monkeypatch, root, oid)
    module.read_portfolio_source()
    main_deadline = calls[0][1]["deadline"]
    local = [kw for _, kw in calls if kw["phase"].startswith("local_pinned_")]
    assert len(local) == 3 and len({kw["deadline"] for kw in local}) == 1
    assert 0 < main_deadline - local[0]["deadline"] <= 44
    assert local[0]["deadline"] - (main_deadline - 44) <= 5.5
    assert all(kw["timeout"] <= 5 for kw in local)


def test_local_real_oversized_object_does_not_escape_byte_budget(monkeypatch, tmp_path):
    oversized = RAW + b"#" * (8 * 1024 * 1024)
    root, oid = repository(tmp_path, oversized)
    module, _ = reader(monkeypatch, root, oid, remote_raw=RAW)
    before = snapshot(root)
    raw, _, source = module.read_portfolio_source()
    assert raw == RAW and source["content_read_lane"] == "REMOTE_OID_REMOTE_BLOB"
    assert source["local_error"]["phase"] == "local_pinned_ledger_blob"
    assert source["local_error"]["reason"] == "source byte budget exceeded"
    assert snapshot(root) == before


def test_actual_process_timeout_and_no_implicit_lazy_fetch_environment(monkeypatch):
    module = _portfolio(monkeypatch)
    deadline = time.monotonic() + 0.15
    with pytest.raises(module._SourceFailure) as caught:
        module._read_cmd([sys.executable, "-c", "import time; time.sleep(2)"],
                         phase="local_pinned_ledger_blob", deadline=deadline, timeout=5, maximum=256)
    assert caught.value.diagnostic["timeout"] is True
    assert time.monotonic() < deadline + 1
    # Read the child's actual environment, not an asserted Python mapping.
    raw = module._read_cmd([sys.executable, "-c",
        "import os; print(os.environ['GIT_NO_LAZY_FETCH'], os.environ['GIT_OPTIONAL_LOCKS'])"],
        phase="local_pinned_repository_identity", deadline=time.monotonic() + 2,
        timeout=1, maximum=256)
    assert raw.strip() == b"1 0"


def test_both_public_probes_and_gantt_strategy_keep_same_pinned_input(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    module, _ = reader(monkeypatch, root, oid)
    legacy = _refresh(monkeypatch)
    sys.modules["probe_utils"].redact_secrets = lambda value: value
    stamp = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(module, "_now", lambda: stamp)
    before = snapshot(root)
    actual = module.PortfolioCollector().collect()
    compat = legacy.probe_portfolio()
    assert actual == compat
    assert actual["sha"] == oid and actual["bet_records"][0]["id"] == "pinned-bet"
    assert actual["source_lane"] == "REMOTE_MAIN"
    assert actual["content_read_lane"] == "REMOTE_OID_LOCAL_OBJECT"
    for payload in (actual, compat):
        gantt = legacy.generate_dynamic_gantt(payload)
        assert {key: gantt[key] for key in ("sha", "ledger_sha256", "source", "observed_at")} == {
            key: payload[key] for key in ("sha", "ledger_sha256", "source", "observed_at")}
        assert gantt["current_as_of"] == stamp and gantt["total"] == payload["actual"] == 1
        rows = [row for lane in gantt["first_100_days"]["lanes"] for row in lane["items"]]
        assert [(row["key"], row["title"], row["status"]) for row in rows] == [
            (bet["id"], bet["title"], bet["status"]) for bet in payload["bet_records"]]
    ontology = types.ModuleType("ontology_model")
    ontology.get_entity_plane = lambda kind: "test-plane"
    ontology.check_axioms = lambda *args, **kwargs: {}
    ontology.build_cross_plane_mesh = lambda **kwargs: {}
    monkeypatch.setitem(sys.modules, "ontology_model", ontology)
    loader = importlib.machinery.SourceFileLoader("pinned_strategy", str(ASSETS / "strategy_projection.py.asset"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    strategy = importlib.util.module_from_spec(spec)
    loader.exec_module(strategy)
    result = strategy.build_strategy({"portfolio": actual}, {"documents": [], "records": {}, "source_states": []})
    provenance = result["provenance"]["remote_portfolio"]
    assert provenance == {key: actual[key] for key in ("sha", "ledger_sha256", "source", "observed_at")}
    source = next(row for row in result["source_states"] if row["id"] == "source:remote-portfolio")
    assert source["sha256"] == actual["ledger_sha256"] and source["observed_at"] == stamp
    bet = next(row for row in result["trace"]["nodes"] if row["id"] == "bet:pinned-bet")
    assert bet["source"] == {"path": actual["source"], "sha256": actual["ledger_sha256"],
                              "observed_at": stamp}
    assert snapshot(root) == before


def test_actual_partial_gantt_uses_bound_clock_not_new_computation(monkeypatch, tmp_path):
    root, oid = repository(tmp_path)
    module, _ = reader(monkeypatch, root, oid, main_error=True)
    state, old, _ = bound_interface(monkeypatch, tmp_path, oid)
    legacy = _refresh(monkeypatch)
    sys.modules["probe_utils"].redact_secrets = lambda value: value
    before = (snapshot(root), snapshot(state))
    portfolio = module.PortfolioCollector().collect()
    data = {"portfolio": portfolio, "source_states": {"portfolio": {"status": "PARTIAL"}}}
    legacy.integrate_gantt(data)
    assert data["gantt"]["state"] == "PARTIAL"
    assert data["gantt"]["observed_at"] == data["gantt"]["current_as_of"] == old
    assert data["gantt"]["computed_at"] != old
    assert data["gantt"]["sha"] == oid
    assert data["gantt"]["ledger_sha256"] == portfolio["ledger_sha256"]
    assert data["source_states"]["gantt"]["observed_at"] == old
    assert data["source_states"]["gantt"]["last_success_at"] is None
    assert (snapshot(root), snapshot(state)) == before
