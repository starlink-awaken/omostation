import plistlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".omo/cron/registry.yaml"
PLIST = ROOT / "runtime/cron/com.omostation.agent-cell-semantic-smoke.plist"


def _job() -> dict:
    jobs = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["jobs"]
    return next(job for job in jobs if job["name"] == "agent-cell-semantic-smoke")


def test_semantic_canary_is_registered_as_low_frequency_launchd_job() -> None:
    job = _job()
    assert job["schedule"] == "17 */6 * * *"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert job["reality"] == "installed"
    assert "/Users/xiamingxing/.local/share/zhixing-dashboard/agent-cell-semantic-smoke.py" in job["command"]
    assert "--state-dir" in job["command"]
    assert "claims_authority" not in job["command"]


def test_semantic_canary_plist_targets_canonical_runtime_without_external_effects() -> None:
    payload = plistlib.loads(PLIST.read_bytes())
    assert payload["Label"] == "com.omostation.agent-cell-semantic-smoke"
    assert payload["StartInterval"] == 21600
    assert payload["RunAtLoad"] is False
    assert payload["WorkingDirectory"] == "/Users/xiamingxing/Workspace"
    assert payload["EnvironmentVariables"]["AGENT_CELL_ROOT"] == "/Users/xiamingxing/Workspace"
    assert payload["EnvironmentVariables"]["AGENT_CELL_STATE_DIR"] == "/Users/xiamingxing/Workspace/.omo/state/agent-cell/semantic"
    assert payload["ProgramArguments"][1:3] == ["-B", "/Users/xiamingxing/.local/share/zhixing-dashboard/agent-cell-semantic-smoke.py"]
    assert payload["ProgramArguments"][-2:] == ["--state-dir", "/Users/xiamingxing/Workspace/.omo/state/agent-cell/semantic"]
