import importlib.util
import plistlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _jobs():
    return yaml.safe_load((ROOT / ".omo/cron/registry.yaml").read_text(encoding="utf-8"))["jobs"]


def test_reference_cell_smoke_is_registered_twelve_hour_launchd_job() -> None:
    job = next(job for job in _jobs() if job["name"] == "reference-cell-direct-local-smoke")
    assert job["schedule"] == "0 */12 * * *"
    assert job["planes"] == ["launchd"]
    assert job["reality"] == "installed"
    assert job["status"] == "active"
    assert job["sfop_slot"] == "S"
    assert "/Users/xiamingxing/.local/share/zhixing-dashboard/reference-cell-direct-local-smoke.py" in job["command"]


def test_reference_cell_smoke_plist_uses_fresh_main_and_attempt_evidence() -> None:
    payload = plistlib.loads((ROOT / "runtime/cron/com.omostation.reference-cell-direct-local-smoke.plist").read_bytes())
    arguments = payload["ProgramArguments"]
    variables = payload["EnvironmentVariables"]
    assert payload["StartInterval"] == 43200
    assert payload["RunAtLoad"] is False
    assert payload["WorkingDirectory"] == "/Users/xiamingxing/.local/share/zhixing-dashboard/code-main"
    assert arguments[-1] == "--json"
    assert arguments[arguments.index("--code-root") + 1] == "/Users/xiamingxing/.local/share/zhixing-dashboard/code-main"
    assert arguments[arguments.index("--attempts-root") + 1] == "/Users/xiamingxing/agents/codex-agent-os-reference-cell/attempts"
    assert arguments[arguments.index("--omo-src") + 1] == "/Users/xiamingxing/Workspace/projects/omo/src"
    assert "/Users/xiamingxing/.local/bin" in variables["PATH"].split(":")


def test_smoke_module_exposes_safe_schema() -> None:
    spec = importlib.util.spec_from_file_location(
        "reference_cell_direct_local_smoke_test",
        ROOT / "bin/ssot/reference-cell-direct-local-smoke.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SCHEMA == "direct-local-reference-cell-r0-canary/v1"
    assert "attempt-local" in module.__doc__
