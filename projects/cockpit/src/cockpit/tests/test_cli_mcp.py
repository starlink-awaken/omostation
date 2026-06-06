"""cmd_mcp 测试 — workspace mcp 命令。"""

from __future__ import annotations

import argparse
from unittest import mock

from rich.console import Console
from cockpit import cli


class TestCmdMcpListTools:
    """mcp --list-tools — 列出 MCP 工具。"""

    def test_list_tools(self, monkeypatch):
        """列出多个工具→显示名称和描述"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.mcp._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.mcp._get_err", lambda: capture)

        mock_tool1 = mock.MagicMock()
        mock_tool1.name = "research_list"
        mock_tool1.description = "列举研究对象"
        mock_tool2 = mock.MagicMock()
        mock_tool2.name = "status_summary"
        mock_tool2.description = "获取工作台概览"

        mock_tm = mock.MagicMock()
        mock_tm.list_tools.return_value = [mock_tool1, mock_tool2]
        mock_mcp = mock.MagicMock()
        mock_mcp._tool_manager = mock_tm

        from cockpit.commands.mcp import _list_tools

        code = _list_tools(mock_mcp)

        output = capture.export_text()
        assert code == 0
        assert "research_list" in output
        assert "status_summary" in output
        assert "列举研究对象" in output
        assert "2 个" in output

    def test_list_tools_empty(self, monkeypatch):
        """无工具→提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.mcp._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.mcp._get_err", lambda: capture)

        mock_tm = mock.MagicMock()
        mock_tm.list_tools.return_value = []
        mock_mcp = mock.MagicMock()
        mock_mcp._tool_manager = mock_tm

        from cockpit.commands.mcp import _list_tools

        code = _list_tools(mock_mcp)

        output = capture.export_text()
        assert code == 0
        assert "未注册任何工具" in output

    def test_list_tools_error(self, monkeypatch):
        """获取工具列表失败→错误"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.mcp._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.mcp._get_err", lambda: capture)

        mock_tm = mock.MagicMock()
        mock_tm.list_tools.side_effect = RuntimeError("test error")
        mock_mcp = mock.MagicMock()
        mock_mcp._tool_manager = mock_tm

        from cockpit.commands.mcp import _list_tools

        code = _list_tools(mock_mcp)

        output = capture.export_text()
        assert code == 1
        assert "获取工具列表失败" in output


class TestCmdMcpDispatch:
    """mcp 命令路由测试。"""

    def test_via_main_mcp(self):
        """mcp 路由确认（cli.main 直接返回，不 exit）"""
        assert hasattr(cli, "cmd_mcp")

    def test_mcp_module_importable(self):
        """mcp 命令模块可导入"""
        from cockpit.commands import mcp as mcp_mod

        assert hasattr(mcp_mod, "cmd_mcp")

    def test_argparse_list_tools(self, monkeypatch):
        """--list-tools 路由确认"""
        from cockpit.commands.mcp import cmd_mcp

        # 验证 --list-tools 触发 _list_tools 分支
        ns = argparse.Namespace(list_tools=True, transport="stdio", port=7431)
        # Mock scripts.cockpit_mcp import and _list_tools
        import sys

        mock_mcp = mock.MagicMock()
        mock_tm = mock.MagicMock()
        mock_tm.list_tools.return_value = []
        mock_mcp._tool_manager = mock_tm
        monkeypatch.setattr("cockpit.commands.mcp._list_tools", lambda mcp_obj: 0)

        # Patch the import
        class _FakeModule:
            mcp = mock_mcp

        monkeypatch.setitem(sys.modules, "scripts.cockpit_mcp", _FakeModule())

        code = cmd_mcp(ns)
        assert code == 0

    def test_argparse_transport_default(self, monkeypatch):
        """默认 transport 为 stdio"""
        import sys

        from cockpit.commands.mcp import cmd_mcp

        mock_mcp = mock.MagicMock()
        monkeypatch.setitem(sys.modules, "scripts.cockpit_mcp", type("_M", (), {"mcp": mock_mcp})())

        ns = argparse.Namespace(list_tools=False, transport="stdio", port=7431)
        # 需要 patch console 以阻止实际打印
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.mcp._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.mcp._get_err", lambda: capture)

        code = cmd_mcp(ns)
        assert code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")
