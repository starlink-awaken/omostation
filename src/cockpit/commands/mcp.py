"""cockpit.commands.mcp — workspace MCP server 命令。"""

from __future__ import annotations

import argparse
import os
from typing import Any

from .base import _get_console, _get_err, _panel


def cmd_mcp(args: argparse.Namespace) -> int:
    """启动 workspace MCP server 或列出可用工具。"""
    try:
        from cockpit.agent_runtime_mcp_server import mcp
    except ImportError as e:
        _get_err().print(f"[red]❌ 无法加载 MCP server: {e}[/red]")
        return 1

    if args.list_tools:
        rc = _list_tools(mcp)
        if rc != 0:
            return rc
        if getattr(args, "agora", False):
            return _list_agora_tools()
        return 0

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

        uvicorn.run(mcp.sse_app, host="127.0.0.1", port=port, log_level="warning")  # type: ignore[union-attr]
    else:
        _get_console().print(
            _panel(
                "[bold yellow]⚠️  DEPRECATED: stdio MCP 入口已废弃[/bold yellow]\n\n"
                "[red]推荐方式: 通过 Agora MCP (:7431) 访问[/red]\n"
                '  agora-mcp → resolve_bos_uri("bos://cockpit/context")\n\n'
                "[dim]保留此入口仅作向后兼容, Phase 4 后移除[/dim]\n"
                "[dim]按 Ctrl+C 停止[/dim]",
                "yellow",
            )
        )
        mcp.run(transport="stdio")  # type: ignore[union-attr]

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

    console.print("\n[yellow]⚠️  cockpit stdio MCP 已 deprecated, 推荐:[/yellow]")
    console.print('[dim]  agora-mcp → resolve_bos_uri("bos://cockpit/context")[/dim]')
    return 0


def _list_agora_tools() -> int:
    """列出 agora (:7431) 的 BOS 服务/工具 (与 cockpit MCP 工具对比)."""
    console = _get_console()
    try:
        from agora.mcp.resolver.services import POC_SERVICES
    except ImportError:
        # 进程内 import 失败 → 退化为 HTTP /health 探测
        try:
            import urllib.request

            with urllib.request.urlopen("http://127.0.0.1:7431/health", timeout=3) as resp:
                import json

                data = json.loads(resp.read())
                proxy = data.get("proxy", {})
                console.print(
                    _panel(
                        f"[bold magenta]🤖 Agora MCP (:7431)[/bold magenta]\n"
                        f"services={data.get('services', {}).get('total')} "
                        f"healthy={data.get('services', {}).get('healthy')} "
                        f"proxy_tools={proxy.get('tool_count')}",
                        "magenta",
                    )
                )
                return 0
        except Exception as exc:  # defensive
            _get_err().print(f"[red]❌ 无法连接 agora :7431: {exc}[/red]")
            return 1

    console.print(
        _panel(
            f"[bold magenta]🤖 Agora BOS 服务 ({len(POC_SERVICES)} 个)[/bold magenta]",
            "magenta",
        )
    )
    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold magenta")
    table.add_column("BOS URI", style="bold green", no_wrap=True)
    table.add_column("Transport", style="dim")
    table.add_column("Domain", style="dim")
    for svc in POC_SERVICES[:50]:
        table.add_row(
            getattr(svc, "uri", "?"),
            getattr(svc, "transport", "?"),
            getattr(svc, "domain", "?"),
        )
    console.print(table)
    if len(POC_SERVICES) > 50:
        console.print(f"[dim]… 还有 {len(POC_SERVICES) - 50} 个服务 (cockpit bos list 可看全部)[/dim]")
    return 0
