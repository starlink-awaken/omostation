import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_ci_health_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_ci(monkeypatch, runs):
    module = _module()
    seen = {}

    def fake_run(command, timeout=120):
        seen["command"] = command
        return 0, json.dumps(runs)

    monkeypatch.setattr(
        module,
        "run",
        fake_run,
    )
    payload = module.collect_ci()
    assert "gh" in seen["command"]
    assert "--branch" in seen["command"]
    assert seen["command"][seen["command"].index("--branch") + 1] == "main"
    return payload


def test_ci_health_separates_concurrency_cancel_from_failure(monkeypatch) -> None:
    runs = [
        {"workflowName": "repo-health-daily", "conclusion": "success", "createdAt": "2026-09-18T00:01:00Z"},
        {"workflowName": "repo-health-daily", "conclusion": "success", "createdAt": "2026-09-18T00:02:00Z"},
        {"workflowName": "repo-health-daily", "conclusion": "cancelled", "createdAt": "2026-09-18T00:03:00Z"},
        {"workflowName": "repo-health-daily", "conclusion": "skipped", "createdAt": "2026-09-18T00:04:00Z"},
    ]

    payload = _run_ci(monkeypatch, runs)

    assert payload["red_workflows"] == []
    summary = payload["all"][0]
    assert summary == {
        "workflow": "repo-health-daily",
        "total": 4,
        "pass": 2,
        "fail": 0,
        "failure_rate": 0.0,
        "health": "green",
        "latest": "pass",
    }


def test_ci_health_marks_real_failures_and_timeouts(monkeypatch) -> None:
    runs = [
        {"workflowName": "check", "conclusion": "failure", "createdAt": "2026-09-18T00:01:00Z"},
        {"workflowName": "check", "conclusion": "timed_out", "createdAt": "2026-09-18T00:02:00Z"},
        {"workflowName": "check", "conclusion": "startup_failure", "createdAt": "2026-09-18T00:03:00Z"},
        {"workflowName": "check", "conclusion": "success", "createdAt": "2026-09-18T00:04:00Z"},
    ]

    payload = _run_ci(monkeypatch, runs)

    assert payload["red_workflows"] == []
    summary = payload["all"][0]
    assert summary == {
        "workflow": "check",
        "total": 4,
        "pass": 1,
        "fail": 3,
        "failure_rate": 0.75,
        "latest": "pass",
        "health": "green",
    }


def test_ci_health_keeps_latest_failure_red_after_prior_success(monkeypatch) -> None:
    runs = [
        {"workflowName": "check", "conclusion": "success", "createdAt": "2026-09-18T00:01:00Z"},
        {"workflowName": "check", "conclusion": "cancelled", "createdAt": "2026-09-18T00:02:00Z"},
        {"workflowName": "check", "conclusion": "failure", "createdAt": "2026-09-18T00:03:00Z"},
    ]

    payload = _run_ci(monkeypatch, runs)

    assert payload["red_workflows"] == [{
        "workflow": "check",
        "total": 3,
        "pass": 1,
        "fail": 1,
        "failure_rate": 0.33,
        "latest": "fail",
        "health": "red",
    }]
