import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_launchd_health", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_launchctl_print_extracts_bounded_health_facts() -> None:
    module = _module()
    output = """gui/501/com.omostation.demo = {
\tpath = /Library/LaunchAgents/demo.plist
\tstate = not running
\tprogram = /opt/homebrew/bin/python3
\truns = 7
\tlast exit code = 0
\trun interval = 240 seconds
}
"""
    parsed = module._parse_launchctl_print(output)
    assert parsed == {
        "loaded": True,
        "state": "not running",
        "pid": None,
        "last_exit_code": "0",
        "runs": "7",
        "run_interval": "240 seconds",
        "program": "/opt/homebrew/bin/python3",
        "plist_path": "/Library/LaunchAgents/demo.plist",
    }


def test_launchd_health_marks_nonzero_exit_as_failed(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / ".omo/cron").mkdir(parents=True)
    (tmp_path / ".omo/cron/registry.yaml").write_text(
        """
jobs:
  - name: demo
    schedule: "*/4 * * * *"
    planes: [launchd]
    status: active
    reality: installed
""",
        encoding="utf-8",
    )

    calls = []
    def fake_run(command, timeout=120):
        calls.append(command)
        return 0, """state = running
last exit code = 3
run interval = 240 seconds
runs = 9
program = /bin/demo
"""

    monkeypatch.setattr(module, "run", fake_run)
    report = module.collect_launchd_health()
    assert report["available"] is True
    assert report["verdict"] == "FAILED"
    assert report["failed"] == 1
    assert report["jobs"][0]["loaded"] is True
    assert report["jobs"][0]["last_exit_code"] == "3"
    assert report["jobs"][0]["last_exit_ok"] is False
    assert calls and calls[0][:2] == ["/bin/launchctl", "print"]


def test_launchd_observation_requires_exact_exit_113_missing_service_evidence(tmp_path) -> None:
    module = _module()
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "jobs:\n  - name: demo\n    schedule: every-4m\n    planes: [launchd]\n    status: active\n    reality: installed\n",
        encoding="utf-8",
    )
    exact = lambda label, _uid: (113, "", f"Could not find service \"{label}\" in domain for user gui")
    observed = module.collect_launchd_health_observation(registry_path=registry, uid=501, runner=exact)
    assert observed["facet_state"] == "LIVE"
    assert observed["verdict"] == "FAILED"
    assert observed["jobs"][0]["command_result_class"] == "confirmed_unloaded"
    assert observed["jobs"][0]["stdout"] == ""
    assert "Could not find service" in observed["jobs"][0]["stderr"]

    wrong_error = lambda label, _uid: (1, "", f"permission denied for {label}")
    assert module.collect_launchd_health_observation(
        registry_path=registry, uid=501, runner=wrong_error,
    ) == {"error": "all_jobs_unknown"}


def test_launchd_observation_marks_mixed_results_partial_and_preserves_registry_digest(tmp_path) -> None:
    module = _module()
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "jobs:\n  - name: demo\n    schedule: every-4m\n    planes: [launchd]\n    status: active\n    reality: installed\n  - name: second\n    schedule: every-4m\n    planes: [launchd]\n    status: active\n    reality: installed\n",
        encoding="utf-8",
    )
    def runner(label, _uid):
        if label.endswith(".demo"):
            return 0, "state = running\nlast exit code = 0\n", ""
        return 1, "", "permission denied"

    observed = module.collect_launchd_health_observation(registry_path=registry, uid=501, runner=runner)
    assert observed["facet_state"] == "PARTIAL"
    assert observed["verdict"] == "DEGRADED"
    assert len(observed["registry_sha256"]) == 64
    assert [job["command_result_class"] for job in observed["jobs"]] == ["loaded", "unknown"]
