"""Agent Cell smoke 的 launchd 登记与 plist 载荷一致性。

根从 plist 自身派生（R = WorkingDirectory，D = 部署脚本的父目录），registry 与
plist 之间用跨源字符串逐字相等连接；不写 host 绝对路径字面量。
"""

import plistlib
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".omo/cron/registry.yaml"
PLIST = ROOT / "runtime/cron/com.omostation.agent-cell-pool-live-smoke.plist"

STATE_FILE_REL = ".omo/state/agent-cell/cell_states.json"


def _job() -> dict:
    jobs = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["jobs"]
    return next(job for job in jobs if job["name"] == "agent-cell-pool-live-smoke")


def _payload() -> dict:
    return plistlib.loads(PLIST.read_bytes())


def _script(payload: dict) -> str:
    candidates = [
        arg for arg in payload["ProgramArguments"] if Path(arg).name.endswith(".py")
    ]
    assert len(candidates) == 1, candidates
    return candidates[0]


def check_agent_cell_payload(payload: dict, job: dict) -> None:
    repo_root = payload["WorkingDirectory"]
    script = _script(payload)
    deployed_root = str(Path(script).parent)
    env = payload["EnvironmentVariables"]

    assert repo_root != deployed_root
    assert not deployed_root.startswith(repo_root + "/")
    assert not repo_root.startswith(deployed_root + "/")

    assert not script.startswith(repo_root + "/")
    assert script in job["command"]

    state_file = payload["ProgramArguments"][-1]
    assert state_file == f"{repo_root}/{STATE_FILE_REL}"
    assert state_file in job["command"]

    assert env["PYTHONPATH"] == f"{repo_root}/projects/omo/src"
    for key in ("StandardOutPath", "StandardErrorPath"):
        assert payload[key].startswith(repo_root + "/")


def test_agent_cell_smoke_is_declared_as_controlled_launchd_observation() -> None:
    job = _job()
    assert job["schedule"] == "*/4 * * * *"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert job["reality"] == "installed"
    assert "external_side_effects" not in job["command"]


def test_agent_cell_smoke_plist_matches_registry_and_freshness_window() -> None:
    job = _job()
    payload = _payload()
    assert payload["Label"] == "com.omostation.agent-cell-pool-live-smoke"
    assert payload["StartInterval"] == 240
    assert payload["RunAtLoad"] is False
    assert payload["ProgramArguments"][-2] == "--state-file"
    check_agent_cell_payload(payload, job)


def test_agent_cell_plist_interval_matches_registry_cron() -> None:
    payload = _payload()
    minutes = payload["StartInterval"] // 60
    assert payload["StartInterval"] % 60 == 0
    assert _job()["schedule"] == f"*/{minutes} * * * *"


def test_derived_root_check_fails_when_working_directory_is_repointed_alone() -> None:
    """混合根变异对照：只挪 WorkingDirectory，状态文件与 PYTHONPATH 必须当场跟不上。"""
    payload = _payload()
    job = _job()

    check_agent_cell_payload(payload, job)

    mutated = deepcopy(payload)
    mutated["WorkingDirectory"] = payload["WorkingDirectory"] + "-moved"
    with pytest.raises(AssertionError):
        check_agent_cell_payload(mutated, job)


def test_agent_cell_scheduler_test_source_lock_has_no_host_literal() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    needle = "/Use" + "rs/"
    assert needle not in source
