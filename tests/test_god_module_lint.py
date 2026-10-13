"""Tests for omo_lint god-module 检查 — 单文件 LOC 硬规则 (TASK-F7114ABA).

任务: TASK-F7114ABA P1 GodModule 治本.
锁定不变量:
  - 0 个文件 >1500L (error 阈值, 硬规则; ADR-0155 从 800 统一到 1500)
  - 治本: 拆分子模块降低 LOC, 加 ALLOWLIST 须显式 ADR

不直接断言 warn (>600L) 数, 因为新功能模块可能合理接近阈值.
只锁定 error (>1500L) 硬规则.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    # omo 子仓 9e96196 "merge 7 families (26→7)" 将 omo_lint_god_module.py
    # 并入 omo_lint.py; 合并后含相对导入 (from .omo_paths import ...),
    # 裸 spec_from_file_location 无 package 上下文会 ImportError, 走正经包导入。
    src = str(ROOT / "projects" / "omo" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import omo.omo_lint as mod

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
        # ADR-0155 (fafc005): error 阈值 800→1500 统一 + allowlist api_system_map
        assert godmod.WARN_LOC == 600
        assert godmod.ERROR_LOC == 1500

    def test_default_workspace_root_resolves(self, godmod):
        # 跨仓 import (P102 模式) → parents[3] 应是 /Users/xiamingxing/Workspace
        assert godmod.WORKSPACE_ROOT.name == "Workspace"
        assert (godmod.WORKSPACE_ROOT / "projects").is_dir()

    def test_check_god_module_returns_error_files(self, godmod, tmp_path):
        # 真实 workspace 现存超标文件已被 ADR-0155 allowlist 豁免 (实扫 error=0),
        # 本测试锁报告结构; 用 tmp_path 超标文件验证 error_files 真会装东西
        # _collect_python_files 只扫 projects/*/src/**; 必须按该形状构造
        (tmp_path / "projects" / "sample" / "src").mkdir(parents=True)
        big = tmp_path / "projects" / "sample" / "src" / "big.py"
        big.write_text("\n".join(["#"] * 1600))
        report = godmod.check_god_module(str(tmp_path))
        assert report["error_threshold"] == 1500
        assert "error_files" in report
        assert isinstance(report["error_files"], list)
        # 不变量: 阈值常量稳定 (防有人悄悄调低阈值逃避)
        assert all(loc > godmod.ERROR_LOC for path, loc in report["error_files"])

    def test_excluded_dirs_not_scanned(self, godmod, tmp_path):
        # 故意用被排除的目录名构造超标文件, 验证 EXCLUDE_DIR_PARTS 生效。
        # 注: "demo" 在 EXCLUDE_DIR_PARTS 里(排除靠它, 而非旧注释所说的 tests/)
        (tmp_path / "projects" / "demo" / "src").mkdir(parents=True)
        fake = tmp_path / "projects" / "demo" / "src" / "big.py"
        fake.write_text("\n".join(["# line"] * 2000))  # 2000L, 超阈值
        report = godmod.check_god_module(str(tmp_path))
        # demo/ 目录 → 应被排除
        assert report["error_files"] == [], f"demo/ 应被排除, 但扫到: {report['error_files']}"

    def test_allowlist_excludes_named_files(self, godmod, tmp_path):
        # 创建超阈值文件, 加 ALLOWLIST, 验证不报错。
        # 必须用 projects/*/src 形状 — _collect_python_files 只扫该形状,
        # 旧用例的 tmp_path/src/... 根本扫不到, all() 空转成假阳性。
        (tmp_path / "projects" / "sample" / "src").mkdir(parents=True)
        big = tmp_path / "projects" / "sample" / "src" / "huge.py"
        big.write_text("\n".join(["#"] * 2000))  # 2000L, 超 1500 阈值
        # 前置咬合: 不加 allowlist 时该文件必须真被扫进 error (防空转)
        pre = godmod.check_god_module(str(tmp_path))
        assert any("huge.py" in str(path) for path, _ in pre["error_files"]), (
            f"构造的超标文件未被扫到, 测试空转: {pre['error_files']}"
        )
        # Monkey-patch allowlist (避免修改模块全局)
        original = godmod.GOD_MODULE_ALLOWLIST
        godmod.GOD_MODULE_ALLOWLIST = {"projects/sample/src/huge.py"}
        try:
            report = godmod.check_god_module(str(tmp_path))
            # huge.py 在 allowlist → 不报 error
            assert all("huge.py" not in str(path) for path, _ in report["error_files"]), (
                f"allowlisted file 仍报错: {report['error_files']}"
            )
        finally:
            godmod.GOD_MODULE_ALLOWLIST = original


class TestCmdLintExitCode:
    def test_cmd_lint_exits_nonzero_when_errors(self, godmod, tmp_path):
        # 构造超标文件 → cmd_lint 应 exit 1 (gate fail)。
        # 不依赖真实 workspace 现状: ADR-0155 后现存 >1500L 文件全部走
        # allowlist 豁免, 实扫 error=0 / rc=0, "真 workspace 必 fail" 前提已失效。
        import contextlib
        import io

        (tmp_path / "projects" / "sample" / "src").mkdir(parents=True)
        big = tmp_path / "projects" / "sample" / "src" / "big.py"
        big.write_text("\n".join(["#"] * 1600))  # 1600L, 超 1500 阈值
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = godmod.cmd_lint_god_module(str(tmp_path))
        assert rc == 1, f"1600L 超标文件应 fail (rc=1), 实得 {rc}.\noutput:\n{buf.getvalue()}"

    def test_cmd_lint_exits_zero_for_clean_workspace(self, godmod, tmp_path):
        # 临时干净 workspace → gate pass
        (tmp_path / "projects" / "sample" / "src").mkdir(parents=True)
        clean = tmp_path / "projects" / "sample" / "src" / "small.py"
        clean.write_text("x = 1\n")  # 1L, 健康
        rc = godmod.cmd_lint_god_module(str(tmp_path))
        assert rc == 0, f"干净 workspace 应 pass, rc=0; 实得 {rc}"
