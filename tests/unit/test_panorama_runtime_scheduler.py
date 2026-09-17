import importlib.util
import os
import plistlib
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _jobs() -> list[dict]:
    return yaml.safe_load((ROOT / ".omo/cron/registry.yaml").read_text(encoding="utf-8"))["jobs"]


def _job(name: str) -> dict:
    return next(job for job in _jobs() if job["name"] == name)


def test_panorama_server_is_keepalive_only_and_cannot_overwrite_projection() -> None:
    job = _job("panorama-dashboard")
    assert job["schedule"] == "always"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert "--no-refresh" in job["command"]
    assert "/Users/xiamingxing/.local/share/zhixing-dashboard/panorama-serve.py" in job["command"]

    payload = plistlib.loads(
        (ROOT / "runtime/cron/com.omostation.panorama-dashboard.plist").read_bytes()
    )
    assert payload["KeepAlive"] is True
    assert payload["ProgramArguments"][-1] == "--no-refresh"
    assert payload["ProgramArguments"][-4].endswith("/.local/share/zhixing-dashboard/panorama-serve.py")
    assert payload["EnvironmentVariables"]["PANORAMA_ROOT"] == "/Users/xiamingxing/Workspace"


def test_panorama_refresh_uses_deployed_collector_bound_to_canonical_root() -> None:
    job = _job("panorama-dashboard-refresh")
    assert job["schedule"] == "*/4 * * * *"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert "/Users/xiamingxing/.local/share/zhixing-dashboard/panorama-collect.py" in job["command"]

    payload = plistlib.loads(
        (ROOT / "runtime/cron/com.omostation.panorama-dashboard-refresh.plist").read_bytes()
    )
    assert payload["StartInterval"] == 240
    assert payload["RunAtLoad"] is False
    assert payload["EnvironmentVariables"]["PANORAMA_ROOT"] == "/Users/xiamingxing/Workspace"
    assert payload["EnvironmentVariables"]["PYTHONPATH"] == "/Users/xiamingxing/Workspace/projects/omo/src"
    assert payload["ProgramArguments"][-1] == "/Users/xiamingxing/.local/share/zhixing-dashboard/panorama-collect.py"


def test_collector_honors_panorama_root_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PANORAMA_ROOT", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "panorama_collect_root_test",
        ROOT / "bin/panorama/panorama-collect.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ROOT == tmp_path.resolve()
    assert os.environ["PANORAMA_ROOT"] == str(tmp_path)


def test_collector_can_use_deployed_receipt_verifier_fallback(tmp_path, monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "panorama_collect_deployed_test",
        ROOT / "bin/panorama/panorama-collect.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    deployed_dir = tmp_path / "deployed"
    deployed_dir.mkdir()
    shutil.copy(
        ROOT / "bin/ssot/agent-cell-pool-live-smoke.py",
        deployed_dir / "agent-cell-pool-live-smoke.py",
    )
    monkeypatch.setattr(
        module, "__file__", str(deployed_dir / "panorama-collect.py")
    )
    monkeypatch.setattr(module, "ROOT", tmp_path / "missing-root")
    report = module._verify_agent_cell_receipts(tmp_path / "missing.json")
    assert report["verdict"] == "EMPTY"
    assert report["ok"] is True
