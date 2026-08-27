"""CLI command: serve — 启动 MCP HTTP 服务"""

import click
from rich.panel import Panel

from codeanalyze.commands.common import console  # type: ignore[import-not-found]


@click.command()
@click.option("--port", default=8765, help="监听端口 (默认 8765)")
@click.option("--host", default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
def serve(port: int, host: str) -> None:
    """启动 MCP HTTP 服务。

    通过 Model Context Protocol 对外暴露所有分析工具（FastMCP），
    供 AI Agent（如 Claude、Agora）通过 HTTP 调用。

    服务端点:
      POST http://{host}:{port}/tools/call/{tool_name}
      GET  http://{host}:{port}/health
    """
    from codeanalyze.mcp import mcp  # type: ignore[import-not-found]

    console.print(
        Panel.fit(
            f"[bold cyan]🚀 MCP HTTP 服务启动[/]\n"
            f"地址: http://{host}:{port}\n"
            f"工具: status, analyze, export, audit, rg_search, codegraph_*, crg_*\n"
            f"退出: Ctrl+C",
            border_style="cyan",
        )
    )

    import asyncio

    asyncio.run(mcp.run_http_async(host=host, port=port))
