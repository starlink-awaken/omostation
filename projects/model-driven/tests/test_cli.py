"""
Tests for model_driven.cli — CLI 集成测试

验证 CLI 命令的基本输出格式和错误处理。
注意: main() 不接受参数，通过 monkeypatch sys.argv 注入参数。
"""

import sys

import pytest

from model_driven.cli import main


class TestCLI:
    @pytest.fixture(autouse=True)
    def _reset_sys_argv(self):
        """保存并恢复 sys.argv"""
        original = sys.argv[:]
        yield
        sys.argv = original

    def _run(self, args: list[str], capsys) -> str:
        """模拟 CLI 调用并返回 stdout"""
        sys.argv = ["model-driven"] + args
        try:
            main()
        except SystemExit:
            pass
        return capsys.readouterr().out

    def test_no_args(self, capsys):
        """测试无参数时的帮助信息"""
        out = self._run([], capsys)
        assert "全生命周期" in out

    def test_lifecycle_no_args(self, capsys):
        """测试 lifecycle 无子命令"""
        out = self._run(["lifecycle"], capsys)
        assert "用法" in out

    def test_lifecycle_create(self, capsys):
        """测试 lifecycle create"""
        out = self._run(["lifecycle", "create", "test-entity", "project"], capsys)
        assert "已创建" in out

    def test_lifecycle_status(self, capsys):
        """测试 lifecycle status — 无实体时显示仪表板"""
        out = self._run(["lifecycle", "status"], capsys)
        assert "实体总数" in out

    def test_spec_no_args(self, capsys):
        """测试 spec 无子命令"""
        out = self._run(["spec"], capsys)
        assert "用法" in out

    def test_spec_create(self, capsys):
        """测试 spec create"""
        out = self._run(["spec", "create", "SPEC-1", "测试Spec"], capsys)
        assert "已创建" in out

    def test_spec_list(self, capsys):
        """测试 spec list — 无 Spec 时显示提示"""
        out = self._run(["spec", "list"], capsys)
        assert "无 Spec" in out

    def test_adr_no_args(self, capsys):
        """测试 adr 无子命令"""
        out = self._run(["adr"], capsys)
        assert "用法" in out

    def test_adr_create(self, capsys):
        """测试 adr create"""
        out = self._run(["adr", "create", "ADR-1", "测试ADR"], capsys)
        assert "已创建" in out

    def test_okr_no_args(self, capsys):
        """测试 okr 无子命令"""
        out = self._run(["okr"], capsys)
        assert "用法" in out

    def test_okr_create(self, capsys):
        """测试 okr create"""
        out = self._run(["okr", "create", "OKR-1", "测试目标"], capsys)
        assert "已创建" in out

    def test_trigger_dashboard(self, capsys):
        """测试 trigger dashboard"""
        out = self._run(["trigger", "dashboard"], capsys)
        assert "Trigger" in out
        assert "总数" in out

    def test_unknown_command(self, capsys):
        """测试未知命令"""
        out = self._run(["unknown_cmd"], capsys)
        assert "未知命令" in out
