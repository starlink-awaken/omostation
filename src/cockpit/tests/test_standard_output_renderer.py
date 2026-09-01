"""cockpit 标准·优雅命令行输出引擎单元测试 (StandardOutputRenderer)."""

import json
from unittest.mock import patch

from cockpit.commands.base import OutputFormat, render_command_header, render_command_result


def test_output_format_constants():
    """验证 OutputFormat 常量准确定义."""
    assert OutputFormat.TTY == "tty"
    assert OutputFormat.JSON == "json"
    assert OutputFormat.MARKDOWN == "markdown"
    assert OutputFormat.TUI == "tui"


def test_render_command_header_runs_without_error():
    """验证 render_command_header 正常输出."""
    with patch("cockpit.commands.base._get_console") as mock_get_console:
        mock_console = mock_get_console.return_value
        render_command_header("核心服务监测", subtitle="本地系统网关状态", category="STATUS")
        mock_console.print.assert_called_once()


def test_render_command_result_json_format(capsys):
    """验证 JSON 格式输出能生成合法的 JSON payload."""
    test_data = [{"name": "agora", "status": "active"}, {"name": "kos", "status": "ok"}]
    render_command_result("测试服务", test_data, output_format=OutputFormat.JSON)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert len(payload) == 2
    assert payload[0]["name"] == "agora"


def test_render_command_result_markdown_format():
    """验证 Markdown 格式能渲染标准的 Markdown Table."""
    test_data = [{"name": "agora", "status": "active"}]
    with patch("cockpit.commands.base._get_console") as mock_get_console:
        mock_console = mock_get_console.return_value
        render_command_result("测试服务", test_data, output_format=OutputFormat.MARKDOWN)
        mock_console.print.assert_called_once()


def test_render_command_result_tty_list_dict():
    """验证 TTY 交互模式能针对 list[dict] 构建 Rich Table."""
    test_data = [
        {"id": 1, "topic": "Attention Mechanism", "status": "active"},
        {"id": 2, "topic": "Textual TUI Engine", "status": "ok"},
    ]
    with patch("cockpit.commands.base._get_console") as mock_get_console:
        mock_console = mock_get_console.return_value
        render_command_result("研究列表", test_data, output_format=OutputFormat.TTY)
        mock_console.print.assert_called_once()


def test_status_command_with_global_output_json(capsys):
    """验证 cmd_status 支持 global_output=json 标准结构化输出."""
    import argparse

    from cockpit.commands.status import cmd_status

    args = argparse.Namespace(global_output="json", json=False)
    ret = cmd_status(args)
    assert ret == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] == "ok"
    assert "services" in data


def test_status_command_with_global_output_markdown():
    """验证 cmd_status 支持 global_output=markdown 标准 Markdown 大纲渲染."""
    import argparse

    from cockpit.commands.status import cmd_status

    args = argparse.Namespace(global_output="markdown", json=False)
    with patch("cockpit.commands.base._get_console") as mock_get_console:
        mock_console = mock_get_console.return_value
        ret = cmd_status(args)
        assert ret == 0
        mock_console.print.assert_called()


def test_cards_list_with_global_output_json(capsys):
    """验证 cockpit cards list 支持 --output json 标准渲染."""
    import argparse

    from cockpit.commands.cards import cmd_cards

    args = argparse.Namespace(cards_command="list", global_output="json")
    ret = cmd_cards(args)
    assert ret == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "data" in data or isinstance(data, list)


def test_cards_list_with_global_output_markdown():
    """验证 cockpit cards list 支持 --output markdown 标准渲染."""
    import argparse

    from cockpit.commands.cards import cmd_cards

    args = argparse.Namespace(cards_command="list", global_output="markdown")
    with patch("cockpit.commands.base._get_console") as mock_get_console:
        mock_console = mock_get_console.return_value
        ret = cmd_cards(args)
        assert ret == 0
        mock_console.print.assert_called()


def test_all_catalog_commands_registered_in_parser():
    """验证所有在 COMMAND_CATALOG 声明的命令都已经在 CLI Parser 及 handlers 注册.

    Phase B 起, 薄委派命令经 cockpit.commands.delegation 注册:
    handler 载体 = cli.py 源码 regex 键集 ∪ DELEGATED_COMMANDS 运行时键集;
    不变量意图不变 (catalog ⊆ handlers), 仅适配新注册载体。
    """
    import inspect
    import re

    import cockpit.cli as cli
    from cockpit.commands.delegation import DELEGATED_COMMANDS, ensure_delegated_catalog
    from cockpit.commands.registry import COMMAND_CATALOG

    with open(inspect.getfile(cli), encoding="utf-8") as f:
        code = f.read()

    handler_keys = set(re.findall(r"\"([a-z0-9\-]+)\":\s*(?:cmd_|dispatch_|_c_|lambda|_cmd_)", code))
    handler_keys |= set(DELEGATED_COMMANDS.keys())  # 薄委派组运行时 handlers
    # 委派组模块若尚未构建 parser (DELEGATED_COMMANDS 未填充),
    # 从组模块派生键集合兜底 —— 与 register_all 注册的 handlers 同源同集。
    delegated_catalog = ensure_delegated_catalog()  # 并入委派组 catalog 条目 (幂等)
    handler_keys |= set(delegated_catalog.keys())
    catalog_keys = set(COMMAND_CATALOG.keys())
    missing_in_handlers = catalog_keys - handler_keys - {"tui"}  # tui 独立判断
    assert not missing_in_handlers, f"发现 COMMAND_CATALOG 声明但未注册 Handler 的子命令: {missing_in_handlers}"


def test_bos_capability_list_rendering_json(capsys):
    """测试 bos-capability list 支持 --output json."""
    import argparse
    import json

    from cockpit.commands.bos import cmd_bos_capability

    args = argparse.Namespace(capability_command="list", global_output="json")
    ret = cmd_bos_capability(args)
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    if data:
        assert "uri" in data[0]


def test_bos_capability_list_rendering_markdown():
    """测试 bos-capability list 支持 --output markdown."""
    import argparse

    from cockpit.commands.bos import cmd_bos_capability

    args = argparse.Namespace(capability_command="list", global_output="markdown")
    with patch("cockpit.commands.base._get_console") as mock_console:
        ret = cmd_bos_capability(args)
        assert ret == 0
        mock_console.return_value.print.assert_called()


def test_bos_inbox_status_rendering_json(capsys):
    """测试 bos-inbox status 支持 --output json."""
    import argparse
    import json

    from cockpit.commands.bos_inbox import _cmd_inbox_status

    ret = _cmd_inbox_status(output_format="json")
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert any(row["source"] == "vector_store.json (嵌入向量库)" for row in data)


def test_quickstart_check_rendering_json(capsys):
    """测试 quickstart-check 支持 JSON 输出."""
    import argparse
    import json

    from cockpit.commands.quickstart import _cmd_quickstart_check

    args = argparse.Namespace(json=True)
    ret = _cmd_quickstart_check(args, output_format="json")
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert any("Python" in row["item"] for row in data)
