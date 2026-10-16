"""Canonical base cohorts must reach the wrapper without renewing old truth."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def lane(monkeypatch, tmp_path):
    path = Path(__file__).with_name("test_zhixing_source_health_mirror.py")
    spec = importlib.util.spec_from_file_location("wrapper_base_fixture", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    module, revision, tasks, calls = helper._task_orchestrator(monkeypatch, tmp_path)
    root = tmp_path / "canonical"
    source = root / "runtime/dashboard/data.json"
    source.parent.mkdir(parents=True)
    roots = types.ModuleType("repo_root")
    roots.state_root = lambda: root
    monkeypatch.setitem(sys.modules, "repo_root", roots)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(root))
    clock = datetime.now(timezone.utc)
    monkeypatch.setattr(module, "now", lambda: clock.isoformat())
    body = {
        "generated_at": clock.isoformat(),
        "bets": {"total": 549, "counts": {"done": 541, "pending": 8}},
        "gates": [{"id": "A4", "verdict": "PASS", "live": True}],
        "runtime": {"scheduler": {"ok": True, "drift_count": 0}},
        "code_root_health": {"verdict": "PASS", "checked_at": clock.isoformat()},
        "tasks": {"forbidden": "unbound task authority"},
        "portfolio": {"forbidden": "unbound collector override"},
        "strategic": {"forbidden": "unbound strategy"},
    }
    previous = {"bets": {"total": 483}, "gates": [{"id": "A4", "verdict": "PASS"}],
                "runtime": {"scheduler": {"ok": False}}, "code_root_health": {"checked_at": "old"}}
    return module, source, body, previous, tasks, clock


def write(source, body):
    raw = json.dumps(body, ensure_ascii=False).encode()
    source.write_bytes(raw)
    return raw


def test_fresh_cohort_replaces_only_owned_base_and_reaches_strategy(lane, monkeypatch):
    module, source, body, previous, tasks, clock = lane
    raw = write(source, body)
    prior = copy.deepcopy(previous)
    observed = []
    monkeypatch.setattr(sys.modules["refresh"], "integrate_strategy",
                        lambda data, old: observed.append(copy.deepcopy(data["gates"])))
    value = {"observed_at": clock.isoformat(), "available": True, "owned": "collector"}
    result = module.RefreshOrchestrator().merge_results(previous, [("portfolio", value, None)])
    for key in ("bets", "gates", "runtime", "code_root_health"):
        assert result[key] == body[key]
    assert result["portfolio"] == value
    assert result["tasks"] == tasks
    assert observed == [body["gates"]]
    assert "strategic" not in result
    assert previous == prior
    state = result["source_states"]["panorama_base"]
    assert state["status"] == "OK"
    assert state["observed_at"] == body["generated_at"]
    assert state["data_sha256"] == hashlib.sha256(raw).hexdigest()
    assert state["source"] == str(source)


@pytest.mark.parametrize("age,status", [(300, "OK"), (300.001, "STALE_PARTIAL"), (900, "STALE_PARTIAL")])
def test_source_age_boundary_does_not_use_wrapper_clock(lane, age, status):
    module, source, body, previous, tasks, clock = lane
    body["generated_at"] = (clock - timedelta(seconds=age)).isoformat()
    write(source, body)
    result = module.RefreshOrchestrator().merge_results(previous, [])
    state = result["source_states"]["panorama_base"]
    assert state["status"] == status
    assert state["observed_at"] == body["generated_at"]
    assert result["code_root_health"]["checked_at"] == body["code_root_health"]["checked_at"]
    if age > 300:
        assert result["gates"][0]["verdict"] == "UNKNOWN"
        assert result["gates"][0]["source_verdict"] == "PASS"
        assert state["last_success_at"] is None


@pytest.mark.parametrize("bad", ["missing", "malformed", "future", "naive", "shape", "oversize"])
def test_bad_base_cannot_promote_unbound_seed_pass(lane, bad):
    module, source, body, previous, tasks, clock = lane
    if bad == "future": body["generated_at"] = (clock + timedelta(seconds=1)).isoformat()
    if bad == "naive": body["generated_at"] = clock.replace(tzinfo=None).isoformat()
    if bad == "shape": body["runtime"] = []
    if bad != "missing": write(source, body)
    if bad == "malformed": source.write_text("{")
    if bad == "oversize": source.write_bytes(b" " * (32 * 1024 * 1024 + 1))
    result = module.RefreshOrchestrator().merge_results(previous, [])
    state = result["source_states"]["panorama_base"]
    assert state["status"] == "UNAVAILABLE"
    assert state["observed_at"] is None
    assert result["gates"][0]["verdict"] == "UNKNOWN"
    assert result["gates"][0]["source_verdict"] == "PASS"
    assert result["tasks"] == tasks


def test_failure_retains_genuine_bound_clock_and_collector_cache(lane):
    module, source, body, previous, tasks, clock = lane
    write(source, body)
    module_instance = module.RefreshOrchestrator()
    value = {"observed_at": "original-collector-clock", "owned": "collector"}
    first = module_instance.merge_results(previous, [("portfolio", value, None)])
    source.unlink()
    result = module_instance.merge_results(first, [("portfolio", None, "bounded failure")])
    state = result["source_states"]["panorama_base"]
    assert state["status"] == "STALE_UNAVAILABLE"
    assert state["observed_at"] == state["last_success_at"] == body["generated_at"]
    assert result["gates"][0]["verdict"] == "UNKNOWN"
    assert result["bets"] == body["bets"]
    assert result["portfolio"] == value
    assert result["source_states"]["portfolio"]["status"] == "STALE_UNAVAILABLE"
    assert result["tasks"] == tasks


def test_state_root_is_resolved_at_each_call(lane, monkeypatch, tmp_path):
    module, source, body, previous, tasks, clock = lane
    write(source, body)
    new_root = tmp_path / "another-profile"
    alternate = new_root / "runtime/dashboard/data.json"
    alternate.parent.mkdir(parents=True)
    body["bets"]["total"] = 17
    write(alternate, body)
    monkeypatch.setattr(sys.modules["repo_root"], "state_root", lambda: new_root)
    result = module.RefreshOrchestrator().merge_results(previous, [])
    assert result["bets"]["total"] == 17
    assert result["source_states"]["panorama_base"]["source"] == str(alternate)


def test_repeated_missing_cache_is_safe_and_never_gains_success(lane):
    module, source, body, previous, tasks, clock = lane
    instance = module.RefreshOrchestrator()
    first = instance.merge_results(previous, [])
    second = instance.merge_results(first, [])
    assert second["source_states"]["panorama_base"]["status"] == "UNAVAILABLE"
    assert second["source_states"]["panorama_base"]["observed_at"] is None
    assert second["gates"][0]["source_verdict"] == "PASS"
    assert second["gates"][0]["verdict"] == "UNKNOWN"


def test_changed_file_is_rejected_before_base_overlay(lane, monkeypatch):
    module, source, body, previous, tasks, clock = lane
    write(source, body)
    original = module.os
    calls = []
    def observed_stat(fd):
        value = original.fstat(fd)
        calls.append(fd)
        return types.SimpleNamespace(st_dev=value.st_dev, st_ino=value.st_ino,
            st_size=value.st_size, st_mode=value.st_mode,
            st_mtime_ns=value.st_mtime_ns + (1 if len(calls) > 1 else 0))
    proxy = types.SimpleNamespace(**{name: getattr(original, name) for name in dir(original)})
    proxy.fstat = observed_stat
    monkeypatch.setattr(module, "os", proxy)
    result = module.RefreshOrchestrator().merge_results(previous, [])
    assert result["bets"] == previous["bets"]
    assert result["source_states"]["panorama_base"]["error"] == "panorama_base_changed_during_read"
    assert result["gates"][0]["verdict"] == "UNKNOWN"


def test_overflow_number_is_rejected_before_any_owned_field_is_changed(lane):
    module, source, body, previous, tasks, clock = lane
    raw = json.dumps(body).replace('"total": 549', '"total": 1e999')
    source.write_text(raw)
    result = module.RefreshOrchestrator().merge_results(previous, [])
    assert result["source_states"]["panorama_base"]["status"] == "UNAVAILABLE"
    assert result["bets"] == previous["bets"]
    assert result["runtime"] == previous["runtime"]
    assert result["code_root_health"] == previous["code_root_health"]
    assert result["gates"][0]["verdict"] == "UNKNOWN"
    assert result["gates"][0]["source_verdict"] == "PASS"
    assert result["tasks"] == tasks
    assert previous["gates"][0]["verdict"] == "PASS"
