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
    monkeypatch.setattr(
        module,
        "run",
        lambda command, timeout=120: (0, json.dumps(runs)),
    )
    return module.collect_ci()


def test_ci_health_separates_concurrency_cancel_from_failure(monkeypatch) -> None:
    runs = [
        {"workflowName": "repo-health-daily", "conclusion": "success"},
        {"workflowName": "repo-health-daily", "conclusion": "success"},
        {"workflowName": "repo-health-daily", "conclusion": "cancelled"},
        {"workflowName": "repo-health-daily", "conclusion": "skipped"},
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
    }


def test_ci_health_marks_real_failures_and_timeouts(monkeypatch) -> None:
    runs = [
        {"workflowName": "check", "conclusion": "failure"},
        {"workflowName": "check", "conclusion": "timed_out"},
        {"workflowName": "check", "conclusion": "startup_failure"},
        {"workflowName": "check", "conclusion": "success"},
    ]

    payload = _run_ci(monkeypatch, runs)

    assert payload["red_workflows"] == [{
        "workflow": "check",
        "total": 4,
        "pass": 1,
        "fail": 3,
        "failure_rate": 0.75,
        "health": "red",
    }]
