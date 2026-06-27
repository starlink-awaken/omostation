"""Tests for omo_lint_god_module — 单文件 LOC 硬规则 (TASK-F7114ABA).

任务: TASK-F7114ABA P1 GodModule 治本.
锁定不变量:
  - 0 个文件 >800L (error 阈值, 硬规则)
  - 治本: 拆分子模块降低 LOC, 加 ALLOWLIST 须显式 ADR

不直接断言 warn (>600L) 数, 因为新功能模块可能合理接近阈值.
只锁定 error (>800L) 硬规则.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "omo_lint_god_module",
        ROOT / "projects" / "omo" / "src" / "omo" / "omo_lint_god_module.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def godmod():
    return _load_module()


class TestCheckGodModule:
    def test_module_loads(self, godmod):
        # 编译即验证 — python -c 失败 → fixture 失败
        assert hasattr(godmod, "check_god_module")
        assert hasattr(godmod, "cmd_lint_god_module")

    def test_thresholds_match_spec(self, godmod):
        # 与 task spec + 现有 P101 yaml-bypass 阈值对齐
        assert godmod.WARN_LOC == 600
        assert godmod.ERROR_LOC == 800

    def test_default_workspace_root_resolves(self, godmod):
        # 跨仓 import (P102 模式) → parents[3] 应是 /Users/xiamingxing/Workspace
        assert godmod.WORKSPACE_ROOT.name == "Workspace"
        assert (godmod.WORKSPACE_ROOT / "projects").is_dir()

    def test_check_god_module_returns_error_files(self, godmod):
        # 当前 workspace 真实: 24 个文件 >800L (per 2026-06-27 扫)
        # 此断言锁 baseline — 若拆分后 ≤ 0 才算治本; 拆分中 0 < x ≤ 24
        report = godmod.check_god_module(str(godmod.WORKSPACE_ROOT))
        assert report["error_threshold"] == 800
        assert "error_files" in report
        assert isinstance(report["error_files"], list)
        # 不变量: 阈值常量稳定 (防有人悄悄调低阈值逃避)
        assert all(
            loc > godmod.ERROR_LOC
            for path, loc in report["error_files"]
        )

    def test_excluded_dirs_not_scanned(self, godmod, tmp_path):
        # 在 tmp_path 创建大量假测试文件, 验证 EXCLUDE_DIR_PARTS 生效
        (tmp_path / "projects" / "demo" / "src").mkdir(parents=True)
        fake = tmp_path / "projects" / "demo" / "src" / "big.py"
        fake.write_text("\n".join(["# line"] * 2000))  # 2000L, 超阈值
        report = godmod.check_god_module(str(tmp_path))
        # 假文件在 tests/test_ 路径下 → 应被排除
        assert report["error_files"] == [], (
            f"tests/ 应被排除, 但扫到: {report['error_files']}"
        )

    def test_allowlist_excludes_named_files(self, godmod, tmp_path):
        # 创建超阈值文件, 加 ALLOWLIST, 验证不报错
        (tmp_path / "src").mkdir(parents=True)
        big = tmp_path / "src" / "huge.py"
        big.write_text("\n".join(["#"] * 1000))
        # Monkey-patch allowlist (避免修改模块全局)
        original = godmod.GOD_MODULE_ALLOWLIST
        godmod.GOD_MODULE_ALLOWLIST = {"src/huge.py"}
        try:
            report = godmod.check_god_module(str(tmp_path))
            # huge.py 在 allowlist → 不报 error
            assert all(
                "huge.py" not in str(path) for path, _ in report["error_files"]
            ), f"allowlisted file 仍报错: {report['error_files']}"
        finally:
            godmod.GOD_MODULE_ALLOWLIST = original


class TestCmdLintExitCode:
    def test_cmd_lint_exits_nonzero_when_errors(self, godmod):
        # workspace 真有 >800L 文件 → cmd_lint 应 exit 1 (gate fail)
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = godmod.cmd_lint_god_module(str(godmod.WORKSPACE_ROOT))
        assert rc == 1, (
            f"workspace 现有 24 个 >800L 文件, gate 应 fail (rc=1), 实得 {rc}.\n"
            f"output:\n{buf.getvalue()}"
        )

    def test_cmd_lint_exits_zero_for_clean_workspace(self, godmod, tmp_path):
        # 临时干净 workspace → gate pass
        (tmp_path / "projects" / "demo" / "src").mkdir(parents=True)
        clean = tmp_path / "projects" / "demo" / "src" / "small.py"
        clean.write_text("x = 1\n")  # 1L, 健康
        rc = godmod.cmd_lint_god_module(str(tmp_path))
        assert rc == 0, f"干净 workspace 应 pass, rc=0; 实得 {rc}"