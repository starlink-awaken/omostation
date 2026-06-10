"""cockpit.commands.mcp — workspace MCP server 命令。"""

from __future__ import annotations

import argparse
from typing import Any

from .base import _get_console, _get_err, _panel


def cmd_mcp(args: argparse.Namespace) -> int:
    """启动 workspace MCP server 或列出可用工具。"""
    try:
        from cockpit.scripts.cockpit_mcp import mcp
    except ImportError as e:
        _get_err().print(f"[red]❌ 无法加载 MCP server: {e}[/red]")
        return 1

    if args.list_tools:
        return _list_tools(mcp)

    transport = args.transport or "stdio"

    if transport == "sse":
        port = args.port or 7431
        _get_console().print(
            _panel(
                f"[bold green]🚀 Workspace MCP Server (SSE)[/bold green]\n"
                f"端口: {port}\n"
                f"URL: http://127.0.0.1:{port}/sse\n\n"
                f"[dim]按 Ctrl+C 停止[/dim]",
                "green",
            )
        )
        import uvicorn

        uvicorn.run(mcp.sse_app, host="127.0.0.1", port=port, log_level="warning")
    else:
        _get_console().print(
            _panel(
                "[bold green]🚀 Workspace MCP Server (stdio)[/bold green]\n"
                "[dim]通过标准输入/输出与 MCP 客户端通信[/dim]",
                "green",
            )
        )
        mcp.run(transport="stdio")

    return 0


def _list_tools(mcp: Any) -> int:
    """列出 MCP server 注册的所有工具。"""
    console = _get_console()
    try:
        tools = mcp._tool_manager.list_tools()
    except Exception as e:
        _get_err().print(f"[red]❌ 获取工具列表失败: {e}[/red]")
        return 1

    if not tools:
        console.print("[yellow]MCP server 未注册任何工具[/yellow]")
        return 0

    console.print(
        _panel(
            f"[bold cyan]🔧 Workspace MCP Tools ({len(tools)} 个)[/bold cyan]",
            "cyan",
        )
    )

    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
    table.add_column("工具名称", style="bold green", no_wrap=True)
    table.add_column("描述", style="dim")
    for tool in tools:
        name = getattr(tool, "name", str(tool))
        desc = getattr(tool, "description", "") or ""
        table.add_row(name, desc[:120])
    console.print(table)

    console.print("\n[dim]使用 `workspace mcp` 启动 server 后，客户端可通过上述工具交互[/dim]")
    return 0
