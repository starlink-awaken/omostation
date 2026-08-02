"""cockpit TUI engine 基础测试 (Phase 1: 核心钩子与优雅降级)"""

import sys
from unittest.mock import patch, MagicMock


def test_tui_is_available_detection():
    """测试 Textual 可用性检测函数."""
    from cockpit.tui import is_tui_available
    # 正常情况下（textual 已安装）应返回 True
    result = is_tui_available()
    assert isinstance(result, bool)


def test_tui_launch_graceful_fallback():
    """测试当 textual 不可用时优雅降级，不抛出异常."""
    from cockpit.tui import launch
    with patch("cockpit.tui.is_tui_available", return_value=False):
        with patch("rich.console.Console.print"):
            result = launch(args=None)
    assert result == 0  # 降级后返回 0 退出码


def test_data_loader_returns_list():
    """测试 data_loader 始终返回列表，不崩溃."""
    from cockpit.tui.data_loader import load_research_topics
    # 即使 Storage 不可用（测试环境），也应返回列表（mock 数据）
    result = load_research_topics()
    assert isinstance(result, list)


def test_data_loader_normalize_fields():
    """测试返回的每个主题包含 TUI 必须字段."""
    from cockpit.tui.data_loader import load_research_topics
    topics = load_research_topics()
    for t in topics:
        assert "id" in t
        assert "topic" in t
        assert "status" in t
        assert "ask_count" in t


def test_command_catalog_drives_palette():
    """测试 CommandPalette 可以从 COMMAND_CATALOG 加载命令."""
    from cockpit.commands.registry import COMMAND_CATALOG
    # 确保 catalog 非空，CommandPalette 有内容可展示
    # origin/main 基线 >= 50 命令；M4/M5 分支合并后 >= 65
    assert len(COMMAND_CATALOG) >= 50
    # 模拟 palette 的加载逻辑
    catalog = [
        {"name": meta.name, "summary": meta.summary}
        for meta in COMMAND_CATALOG.values()
    ]
    assert any(c["name"] == "research" for c in catalog)
    # tui 必须被注册（本分支已写入 registry.py）
    assert any(c["name"] == "tui" for c in catalog)
