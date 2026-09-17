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
