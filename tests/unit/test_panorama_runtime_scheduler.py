"""Panorama 的两个 launchd 面：registry 登记与 plist 载荷必须同源同根。

断言一律从 plist 自身的 `WorkingDirectory` 派生仓库根 R、从 `ProgramArguments`
派生部署数据域 D，再做跨源字符串相等。绝不复述 host 绝对路径 —— 那种用例
只因为逐字抄了 plist 里的根才是绿的（green-by-literal），换根当天准时变红。
"""

import importlib.util
import os
import plistlib
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".omo/cron/registry.yaml"
SERVE_PLIST = ROOT / "runtime/cron/com.omostation.panorama-dashboard.plist"
REFRESH_PLIST = ROOT / "runtime/cron/com.omostation.panorama-dashboard-refresh.plist"

DEPLOYED_SCRIPTS = {"panorama-serve.py", "panorama-collect.py"}


def _jobs() -> list[dict]:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["jobs"]


def _job(name: str) -> dict:
    return next(job for job in _jobs() if job["name"] == name)


def _payload(path: Path) -> dict:
    return plistlib.loads(path.read_bytes())


def _repo_root(payload: dict) -> str:
    """R：plist 自己声明的工作目录，不是测试文件的位置（worktree 下两者不等）。"""
    return payload["WorkingDirectory"]


def _deployed_script(payload: dict) -> str:
    candidates = [
        arg for arg in payload["ProgramArguments"] if Path(arg).name in DEPLOYED_SCRIPTS
    ]
    assert len(candidates) == 1, candidates
    return candidates[0]


def _deployed_root(payload: dict) -> str:
    """D：部署数据域，由脚本路径自身推出。"""
    return str(Path(_deployed_script(payload)).parent)


def check_panorama_payload(payload: dict, job: dict) -> None:
    """两个 panorama plist 共用的派生 + 跨源一致性判据。"""
    repo_root = _repo_root(payload)
    deployed_root = _deployed_root(payload)
    script = _deployed_script(payload)
    env = payload["EnvironmentVariables"]

    assert repo_root != deployed_root
    assert not deployed_root.startswith(repo_root + "/")
    assert not repo_root.startswith(deployed_root + "/")

    assert env["PANORAMA_ROOT"] == repo_root
    assert payload["StandardOutPath"].startswith(repo_root + "/")
    assert payload["StandardErrorPath"] == payload["StandardOutPath"]

    assert not script.startswith(repo_root + "/")
    assert script in job["command"]

    if "PYTHONPATH" in env:
        assert env["PYTHONPATH"] == f"{repo_root}/projects/omo/src"
    if "PANORAMA_CODE_ROOT" in env:
        assert env["PANORAMA_CODE_ROOT"] == f"{deployed_root}/code-main"
        assert env["PANORAMA_CODE_ROOT"] in job["command"]


def test_panorama_server_is_keepalive_only_and_cannot_overwrite_projection() -> None:
    job = _job("panorama-dashboard")
    assert job["schedule"] == "always"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "proposed"
    assert job["reality"] == "declared_only"
    assert "--no-refresh" in job["command"]

    payload = _payload(SERVE_PLIST)
    assert payload["KeepAlive"] is True
    assert payload["ProgramArguments"][-1] == "--no-refresh"
    check_panorama_payload(payload, job)


def test_panorama_refresh_uses_deployed_collector_bound_to_canonical_root() -> None:
    job = _job("panorama-dashboard-refresh")
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert job["reality"] == "installed"

    payload = _payload(REFRESH_PLIST)
    assert payload["RunAtLoad"] is False
    assert payload["Label"] == "com.omostation.panorama-dashboard-refresh"
    check_panorama_payload(payload, job)


def test_panorama_refresh_plist_interval_matches_registry_cron() -> None:
    job = _job("panorama-dashboard")
    refresh = _job("panorama-dashboard-refresh")
    payload = _payload(REFRESH_PLIST)

    minutes = payload["StartInterval"] // 60
    assert payload["StartInterval"] % 60 == 0
    assert refresh["schedule"] == f"*/{minutes} * * * *"
    assert job["schedule"] == "always"


def test_panorama_refresh_launchd_path_includes_multica_user_local_bin() -> None:
    payload = _payload(REFRESH_PLIST)
    user_local_bin = str(Path.home() / ".local" / "bin")
    path = payload["EnvironmentVariables"]["PATH"].split(":")
    assert user_local_bin in path
    assert "/opt/homebrew/bin" in path


def test_derived_root_check_fails_when_one_value_is_repointed_to_another_root() -> None:
    """混合根变异对照：只把 PANORAMA_ROOT 挪走，派生判据必须当场报不一致。"""
    payload = _payload(REFRESH_PLIST)
    job = _job("panorama-dashboard-refresh")

    check_panorama_payload(payload, job)

    mutated = deepcopy(payload)
    mutated["EnvironmentVariables"]["PANORAMA_ROOT"] = _repo_root(payload) + "-moved"
    with pytest.raises(AssertionError):
        check_panorama_payload(mutated, job)


def test_cross_source_check_fails_when_registry_command_disagrees_with_plist() -> None:
    """跨源变异对照：把 plist 脚本换到另一个部署根下，registry 必须对不上。"""
    payload = _payload(REFRESH_PLIST)
    job = _job("panorama-dashboard-refresh")
    script = _deployed_script(payload)

    mutated = deepcopy(payload)
    mutated["ProgramArguments"] = [
        script if arg != script else str(Path(_deployed_root(payload)).parent / "drift" / Path(script).name)
        for arg in payload["ProgramArguments"]
    ]
    with pytest.raises(AssertionError):
        check_panorama_payload(mutated, job)


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


def test_panorama_scheduler_test_source_lock_has_no_host_literal() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    needle = "/Use" + "rs/"
    assert needle not in source
