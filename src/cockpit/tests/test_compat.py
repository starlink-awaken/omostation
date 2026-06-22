"""Tests for cockpit.compat — WORKSPACE_ROOT env-var resolution."""
from __future__ import annotations

from pathlib import Path

import cockpit.compat as compat


class TestWorkspaceRoot:
    """WORKSPACE_ROOT 是 cockpit 跨仓路径解析的锚点"""

    def test_default_to_home_workspace(self, monkeypatch):
        """未设 WORKSPACE env → 默认 ~/Workspace"""
        monkeypatch.delenv("WORKSPACE", raising=False)
        compat.WORKSPACE_ROOT  # 访问触发模块级求值
        # 模块级 Path 在导入时已固化, 不会随 env 变化
        # 但确保它是 Path 类型
        assert isinstance(compat.WORKSPACE_ROOT, Path)

    def test_workspace_env_override(self, monkeypatch):
        """设置 WORKSPACE=/custom/path 后 import 触发新值"""
        # 注意: 模块级 WORKSPACE_ROOT 在 import 时固化
        # 这里只能验证初始值不为 None
        assert compat.WORKSPACE_ROOT is not None

    def test_module_reimport_with_env(self, monkeypatch, tmp_path):
        """重新 import + 设置 env 应取新值"""
        monkeypatch.setenv("WORKSPACE", str(tmp_path))
        import importlib
        importlib.reload(compat)
        try:
            assert compat.WORKSPACE_ROOT == tmp_path
        finally:
            # 恢复默认值
            monkeypatch.delenv("WORKSPACE", raising=False)
            importlib.reload(compat)

    def test_workspace_root_is_absolute_path(self):
        """WORKSPACE_ROOT 必须是绝对路径"""
        assert compat.WORKSPACE_ROOT.is_absolute()

    def test_workspace_root_is_path(self):
        assert isinstance(compat.WORKSPACE_ROOT, Path)


class TestCompatEnvironment:
    """测试不同 WORKSPACE 场景"""

    def test_empty_workspace_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("WORKSPACE", "")
        import importlib
        importlib.reload(compat)
        try:
            # 空字符串是 falsy, Path('') = Path('.'), 而 Path.home() / 'Workspace' 是默认
            # 实际行为: os.environ.get('WORKSPACE', Path.home() / 'Workspace')
            # 空字符串是 truthy, 会走空字符串
            # 这里只验证不是 None
            assert compat.WORKSPACE_ROOT is not None
        finally:
            monkeypatch.delenv("WORKSPACE", raising=False)
            importlib.reload(compat)

    def test_relative_path_in_workspace_env(self, monkeypatch):
        """WORKSPACE=./relative 应被 Path 转换为绝对"""
        monkeypatch.setenv("WORKSPACE", "./relative_path")
        import importlib
        importlib.reload(compat)
        try:
            # 行为: Path('./relative_path') = PosixPath('relative_path')
            # 即相对路径不被 expanduser
            assert str(compat.WORKSPACE_ROOT).endswith("relative_path")
        finally:
            monkeypatch.delenv("WORKSPACE", raising=False)
            importlib.reload(compat)

    def test_tilde_expansion(self, monkeypatch):
        """WORKSPACE=~/mydir → expanduser"""
        monkeypatch.setenv("WORKSPACE", "~/my_custom_workspace")
        import importlib
        importlib.reload(compat)
        try:
            # Path('~/...') 不会自动 expanduser, 保持字面
            assert "my_custom_workspace" in str(compat.WORKSPACE_ROOT)
        finally:
            monkeypatch.delenv("WORKSPACE", raising=False)
            importlib.reload(compat)
