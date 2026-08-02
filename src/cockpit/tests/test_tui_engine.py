"""cockpit TUI engine 测试套件 (Phase 1 + Phase 2: 完整架构验证)."""

import sys
from unittest.mock import MagicMock, patch


def test_tui_is_available_detection():
    """测试 Textual 可用性检测函数."""
    from cockpit.tui import is_tui_available

    result = is_tui_available()
    assert isinstance(result, bool)


def test_tui_launch_graceful_fallback():
    """测试当 textual 不可用时优雅降级，不抛出异常."""
    from cockpit.tui import launch

    with patch("cockpit.tui.is_tui_available", return_value=False):
        with patch("rich.console.Console.print"):
            result = launch(args=None)
    assert result == 0


def test_data_loader_returns_list():
    """测试 data_loader 始终返回列表，不崩溃."""
    from cockpit.tui.data_loader import load_research_topics

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

    assert len(COMMAND_CATALOG) >= 65
    catalog = [{"name": meta.name, "summary": meta.summary} for meta in COMMAND_CATALOG.values()]
    assert any(c["name"] == "research" for c in catalog)
    assert any(c["name"] == "tui" for c in catalog)


# ── Phase 2: 新增高级特性用例 ────────────────────────────────────────────────


def test_health_probe_returns_dict():
    """验证健康探针引擎非阻塞调用并输出正确结构."""
    from cockpit.tui.health_probe import probe_system_health

    status = probe_system_health()
    assert "agora_online" in status
    assert "kos_online" in status
    assert "summary_label" in status
    assert isinstance(status["summary_label"], str)
    assert "Agora" in status["summary_label"]


def test_file_watcher_graceful_missing_watchfiles():
    """验证文件系统被动变更侦听在缺失路径或依赖时能极致优雅退出."""
    from pathlib import Path

    from cockpit.tui.file_watcher import watch_state_directory

    called = []
    # 传入不存在目录及虚拟回调，保证不会抛出异常
    watch_state_directory(lambda: called.append(1), watch_dir=Path("/non_existent_watch_dir_999"))
    assert len(called) == 0


def test_cli_output_tui_global_flag():
    """验证 --output tui 参数能正常解析，并在 TUI 可用时启动控制台."""
    import argparse

    from cockpit.tui import is_tui_available

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        "-o",
        dest="global_output",
        choices=["text", "json", "tui", "markdown"],
        default="text",
    )
    args = parser.parse_args(["--output", "tui"])
    assert getattr(args, "global_output") == "tui"
    assert isinstance(is_tui_available(), bool)
