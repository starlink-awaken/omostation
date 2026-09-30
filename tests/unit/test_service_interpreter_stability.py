"""服务解释器解析不得被调用方的 uv 临时环境劫持 (2026-09-30).

`make gac-local-gate` 展开为::

    uv run --with pyyaml python bin/gac/gac-local-gate.py

`uv run` 会把临时 venv 提到 `PATH` 最前, 而 `resolve_interpreter` 的**裸名分支**
原先用裸 `shutil.which(spec)` 解析, 于是 `interpreter: python3` (services.yaml 里
`omostation.morning-brief` 正是这么写的) 被解析成::

    /Users/xiamingxing/.cache/uv/builds-v0/.tmpXXXXXX/bin/python3

随即被本模块自己的守卫判为违规。级联后果: `service-config-validate` 与
`service-config-drift` 双双 FAIL, 而 `service-config-drift` 是
`governance-semantic` 的子检查, 于是**整个治理门禁被翻转**。

即: 门禁用自身临时运行时污染了它要校验的产物, 再因产物失败 —— 一个不代表任何
配置问题的环境伪影阻断全部交付。

本测试用真实 PATH 注入复现, 不 mock `shutil.which` 之外的东西。
"""

from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "gen_service_configs", WORKSPACE / "bin" / "mof" / "gen-service-configs.py"
)
assert _spec and _spec.loader
gsc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gsc)


def _fake_uv_venv() -> str:
    """造一个形如 uv 临时 builds 目录的可执行目录, 返回它的绝对路径。"""
    root = Path(tempfile.mkdtemp(prefix="uv-builds-v0-")) / ".tmpFAKE" / "bin"
    root.mkdir(parents=True)
    for name in ("python3", "uv"):
        exe = root / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(root)


def test_uv_temp_path_is_recognised():
    for bad in (
        "/Users/x/.cache/uv/builds-v0/.tmpAAA/bin/python3",
        "/tmp/.tmpZZZ/bin/python3",
        "/repo/.venv/bin/python",
        "/repo/.venv/python",
    ):
        assert gsc._is_transient_uv_path(bad), bad
    for good in ("/opt/homebrew/bin/python3", "/usr/bin/python3", "/opt/homebrew/bin/uv"):
        assert not gsc._is_transient_uv_path(good), good


def test_bare_name_does_not_resolve_into_uv_temp_venv(monkeypatch):
    """核心契约: 裸名分支在 uv 临时 venv 前置时, 必须解析到稳定解释器。"""
    fake = _fake_uv_venv()
    monkeypatch.setenv(
        "PATH", f"{fake}" + os.pathsep + os.environ.get("PATH", "/opt/homebrew/bin:/usr/bin")
    )
    resolved = gsc.resolve_interpreter("python3")
    assert not gsc._is_transient_uv_path(resolved), (
        f"裸名分支解析到了 uv 临时路径 {resolved} —— 这正是门禁失败的根因"
    )
    assert resolved.startswith("/") and resolved.endswith("python3")


def test_which_stable_skips_transient_path_entries(monkeypatch):
    fake = _fake_uv_venv()
    monkeypatch.setenv(
        "PATH", f"{fake}" + os.pathsep + os.environ.get("PATH", "/opt/homebrew/bin:/usr/bin")
    )
    for name in ("python3", "uv"):
        found = gsc._which_stable(name)
        assert found is not None, name
        assert not gsc._is_transient_uv_path(found), f"{name} -> {found}"


def test_which_stable_returns_none_when_only_transient_available(monkeypatch):
    """只有 uv 临时环境可用时必须诚实返回 None, 而不是回落到临时路径。"""
    fake = _fake_uv_venv()
    monkeypatch.setenv("PATH", fake)
    assert gsc._which_stable("python3") is None


def test_unknown_alias_still_raises_clear_error(monkeypatch):
    """放行过滤不能把「真不存在的程序名」也变成静默通过。"""
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")
    try:
        gsc.resolve_interpreter("definitely-not-a-real-binary-xyz")
    except ValueError as exc:
        assert "未知 interpreter" in str(exc)
    else:
        raise AssertionError("不存在的程序名必须在生成期炸, 不能写进 plist")


def test_stable_python3_never_returns_transient_path(monkeypatch):
    fake = _fake_uv_venv()
    monkeypatch.setenv(
        "PATH", f"{fake}" + os.pathsep + os.environ.get("PATH", "/opt/homebrew/bin:/usr/bin")
    )
    assert not gsc._is_transient_uv_path(gsc._stable_python3())


def test_existing_uv_guard_still_present():
    """原有守卫不得被本次修复顺带删掉。"""
    src = (WORKSPACE / "bin" / "mof" / "gen-service-configs.py").read_text()
    assert "interpreter 含 uv 临时路径" in src, "resolve_interpreter 的最终守卫必须保留"
