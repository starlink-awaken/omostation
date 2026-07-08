"""cockpit.commands.mcp — workspace MCP server 命令。"""

from __future__ import annotations

import argparse
import os
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
        port = args.port or int(os.environ.get("AGORA_MCP_SSE_PORT", "7431"))
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


def _resolve_mcp_tools(mcp: Any) -> list:
    """列举 MCP server 工具, 兼容多版本 FastMCP API.

    产品走查 v5 #V5-15: 旧版 ``mcp._tool_manager.list_tools()`` 在新版 FastMCP
    已不存在 (AttributeError), 致 ``cockpit mcp --list`` 直接崩溃。按版本探测:
    优先 async ``list_tools()`` → 回退旧私有 ``_tool_manager`` → 回退 ``get_tools``。
    """
    import asyncio
    import inspect

    # 优先旧私有 _tool_manager (旧版 FastMCP + 现有测试 mock); 新版 FastMCP 无此属性
    # 则 hasattr 为 False, 自动落到 list_tools (新公开 coroutine API)。
    # v2 修复:_tool_manager 存在但可能是 None(未初始化),用 try/except 包裹
    try:
        if hasattr(mcp, "_tool_manager") and mcp._tool_manager is not None:
            result = mcp._tool_manager.list_tools()
            if result is not None:
                return result
    except (AttributeError, TypeError):
        pass  # 新版 FastMCP,落到下一分支
    if hasattr(mcp, "list_tools"):
        fn = mcp.list_tools
        return asyncio.run(fn()) if inspect.iscoroutinefunction(fn) else fn()
    if hasattr(mcp, "get_tools"):
        fn = mcp.get_tools
        got = asyncio.run(fn()) if inspect.iscoroutinefunction(fn) else fn()
        return list(got.values()) if isinstance(got, dict) else list(got)
    raise RuntimeError("FastMCP 无可用工具列举 API (list_tools/_tool_manager/get_tools 均缺)")


def _list_tools(mcp: Any) -> int:
    """列出 MCP server 注册的所有工具。"""
    console = _get_console()
    try:
        tools = _resolve_mcp_tools(mcp)
    except Exception as e:  # defensive fallback
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

    console.print("\n[dim]使用 `cockpit mcp` 启动 server 后，客户端可通过上述工具交互[/dim]")
    return 0
