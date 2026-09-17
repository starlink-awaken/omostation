import plistlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".omo/cron/registry.yaml"
PLIST = ROOT / "runtime/cron/com.omostation.agent-cell-pool-live-smoke.plist"


def _job() -> dict:
    jobs = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["jobs"]
    return next(job for job in jobs if job["name"] == "agent-cell-pool-live-smoke")


def test_agent_cell_smoke_is_declared_as_controlled_launchd_observation() -> None:
    job = _job()
    assert job["schedule"] == "*/4 * * * *"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert job["reality"] == "installed"
    assert "/Users/xiamingxing/.local/share/zhixing-dashboard/agent-cell-pool-live-smoke.py" in job["command"]
    assert "/Users/xiamingxing/Workspace/.omo/state/agent-cell/cell_states.json" in job["command"]
    assert "external_side_effects" not in job["command"]


def test_agent_cell_smoke_plist_matches_registry_and_freshness_window() -> None:
    job = _job()
    payload = plistlib.loads(PLIST.read_bytes())
    assert payload["Label"] == "com.omostation.agent-cell-pool-live-smoke"
    assert payload["StartInterval"] == 240
    assert payload["RunAtLoad"] is False
    assert payload["EnvironmentVariables"]["PYTHONPATH"] == "/Users/xiamingxing/Workspace/projects/omo/src"
    assert payload["WorkingDirectory"] == "/Users/xiamingxing/Workspace"
    arguments = payload["ProgramArguments"]
    assert arguments[-3].endswith("/.local/share/zhixing-dashboard/agent-cell-pool-live-smoke.py")
    assert arguments[-2] == "--state-file"
    assert arguments[-1] == "/Users/xiamingxing/Workspace/.omo/state/agent-cell/cell_states.json"
