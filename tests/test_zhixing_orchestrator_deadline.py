"""Real owned workers, blocking calls, descendants, and retained source clocks."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def orchestrator(monkeypatch, tmp_path):
    # Existing fixture supplies external registry/revision interfaces, while
    # loading the whole delivered orchestrator asset and actual merge policy.
    helper_path = Path(__file__).with_name("test_zhixing_source_health_mirror.py")
    spec = importlib.util.spec_from_file_location("deadline_external_fixture", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    module, _, _, _ = helper._task_orchestrator(monkeypatch, tmp_path)
    return module


def collector(name, action, timeout=48):
    return SimpleNamespace(name=name, timeout=timeout, run=action)


def run(module, collectors, *, budget=0.4, workers=2):
    registry = SimpleNamespace(all=lambda: collectors)
    started = time.monotonic()
    result = module.RefreshOrchestrator(
        registry, max_workers=workers, collection_timeout=budget
    ).run_collectors()
    elapsed = time.monotonic() - started
    assert elapsed < budget + 1.5
    assert len(result) == len(collectors)
    assert {r[0] for r in result} == {c.name for c in collectors}
    return {name: (value, error) for name, value, error in result}


def forever():
    while True:
        time.sleep(60)


def test_real_nonreturning_worker_is_bounded_and_reaped(orchestrator, tmp_path):
    marker = tmp_path / "worker.pid"
    def blocked():
        marker.write_text(str(os.getpid()))
        forever()
    result = run(orchestrator, [collector("blocked", blocked)], budget=0.3)
    assert result["blocked"] == (None, "Collector deadline exceeded")
    pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


def test_successes_survive_hung_peer_and_queue(orchestrator):
    value = {"observed_at": "real-source-clock", "payload": ["unchanged", {"unicode": "周报"}]}
    jobs = [collector("blocked", forever)] + [
        collector(str(i), lambda i=i: (str(i), value, None)) for i in range(6)
    ]
    result = run(orchestrator, jobs)
    assert result["blocked"][0] is None and "deadline" in result["blocked"][1]
    for i in range(6):
        assert result[str(i)] == (value, None)


def test_capacity_and_cohort_deadline_report_unstarted_jobs(orchestrator):
    result = run(orchestrator, [collector("blocked", forever),
        collector("queued", lambda: ("queued", {"value": "must not run"}, None))],
        workers=1, budget=0.2)
    assert result["blocked"] == (None, "Collector deadline exceeded")
    assert result["queued"] == (None, "Collection deadline exceeded before start")


def test_per_worker_limit_releases_slot_before_cohort_deadline(orchestrator):
    # Existing collector contract includes a two-second finishing allowance.
    result = run(orchestrator, [collector("blocked", forever, timeout=0),
        collector("queued", lambda: ("queued", {"value": "real success"}, None))],
        workers=1, budget=3)
    assert result["blocked"] == (None, "Collector deadline exceeded")
    assert result["queued"] == ({"value": "real success"}, None)


@pytest.mark.parametrize("returns", [False, True])
def test_descendant_processes_do_not_survive_worker_completion(orchestrator, tmp_path, returns):
    child_pid = tmp_path / "child.pid"
    grandchild_pid = tmp_path / "grandchild.pid"
    grandchild = "import os,time,pathlib; pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(60)" % str(grandchild_pid)
    child = "import os,time,pathlib,subprocess,sys; pathlib.Path(%r).write_text(str(os.getpid())); subprocess.Popen([sys.executable,'-c',%r]); time.sleep(60)" % (str(child_pid), grandchild)
    def spawns():
        subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.monotonic() + 0.6
        while not grandchild_pid.exists() and time.monotonic() < end:
            time.sleep(0.005)
        if returns:
            return "spawner", {"status": "OBSERVED"}, None
        forever()
    result = run(orchestrator, [collector("spawner", spawns)], budget=0.9)
    assert result["spawner"] == (({"status": "OBSERVED"}, None) if returns else (None, "Collector deadline exceeded"))
    assert child_pid.exists() and grandchild_pid.exists()
    # launchd may briefly retain a killed, non-running orphan zombie before
    # reaping it. Check actual process state, not kill(pid, 0) alone.
    for path in (child_pid, grandchild_pid):
        pid = path.read_text()
        end = time.monotonic() + 0.5
        while True:
            observed = subprocess.run(["ps", "-p", pid, "-o", "stat="], capture_output=True, text=True)
            if not observed.stdout.strip() or observed.stdout.strip().startswith("Z"):
                break
            assert time.monotonic() < end, f"live descendant {pid}: {observed.stdout}"
            time.sleep(0.01)


@pytest.mark.parametrize("action, error", [
    (lambda: (_ for _ in ()).throw(ValueError("actual collector exception")), "ValueError"),
    (lambda: ("malformed", [1], None), "invalid collector result"),
    (lambda: ("different", {}, None), "invalid collector result"),
    (lambda: ("malformed", {"bad": object()}, None), "TypeError"),
    (lambda: os._exit(2), "deadline"),
])
def test_failures_are_explicit_without_losing_success(orchestrator, action, error):
    result = run(orchestrator, [collector("malformed", action),
        collector("ok", lambda: ("ok", {"observed_at": "source-clock"}, None))], budget=0.25)
    assert result["malformed"][0] is None and error in result["malformed"][1]
    assert result["ok"] == ({"observed_at": "source-clock"}, None)


def test_timeout_retains_original_value_and_source_clock(orchestrator):
    prior = {"observed_at": "older-source-clock", "state": "OBSERVED", "counts": {"done": 3}}
    previous = {"portfolio": prior, "live_sources": {"portfolio": prior},
        "source_states": {"portfolio": {"status": "OK", "observed_at": prior["observed_at"],
        "last_success_at": prior["observed_at"]}}}
    result = run(orchestrator, [collector("portfolio", forever)], budget=0.2)
    merged = orchestrator.RefreshOrchestrator().merge_results(previous,
        [(name, value, error) for name, (value, error) in result.items()])
    assert merged["portfolio"] == prior and merged["live_sources"]["portfolio"] == prior
    state = merged["source_states"]["portfolio"]
    assert state["status"] == "STALE_UNAVAILABLE"
    assert state["observed_at"] == state["last_success_at"] == "older-source-clock"
    assert state["last_attempt_at"] == merged["generated_at"] != state["observed_at"]
    assert state["error"] == "Collector deadline exceeded"
    assert previous["source_states"]["portfolio"]["status"] == "OK"


def test_missing_cache_is_unavailable_then_real_recovery(orchestrator):
    instance = orchestrator.RefreshOrchestrator()
    failed = instance.merge_results({}, [("workflow", None, "Collector deadline exceeded")])
    assert failed["source_states"]["workflow"]["status"] == "UNAVAILABLE"
    assert failed["source_states"]["workflow"]["observed_at"] is None
    assert "workflow" not in failed
    value = {"state": "OBSERVED", "observed_at": "recovered-source-clock", "runs": 2}
    successful = run(orchestrator, [collector("workflow", lambda: ("workflow", value, None))])
    recovered = instance.merge_results(failed, [(name, data, error) for name, (data, error) in successful.items()])
    assert recovered["workflow"] == value
    assert recovered["source_states"]["workflow"]["status"] == "OK"
    assert recovered["source_states"]["workflow"]["last_success_at"] == value["observed_at"]


@pytest.mark.parametrize("budget, workers", [(0, 1), (float("inf"), 1), (1, 0)])
def test_invalid_bounds_are_rejected(orchestrator, budget, workers):
    with pytest.raises(ValueError):
        orchestrator.RefreshOrchestrator(collection_timeout=budget, max_workers=workers)
