"""命令: mcp / serve — MCP server及开发服务"""

import threading
import time

from ontoderive.mcp_server import main as mcp_main
from ontoderive.watcher import FileWatcher


def cmd_mcp(port: int = 0) -> None:
    """启动MCP server (FastMCP)"""
    mcp_main()


def cmd_serve(
    project: str = ".",
    watch_enabled: bool = True,
    interval: int = 5,
    auto: bool = False,
    no_mcp: bool = False,
    http: bool = False,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """启动开发服务: MCP + 文件监听 + Web仪表盘(可选)

    Args:
        http: 启动 Web 仪表盘 (FastAPI) + MCP over HTTP
        host: Web 服务绑定地址
        port: Web 服务端口
    """
    enable_mcp = not no_mcp

    if http:
        from ontoderive.web_server import serve

        serve(project=project, host=host, port=port, watch=watch_enabled)
        return

    print(f"{'=' * 50}")
    print("  OntoDerive Serve — 开发服务")
    print(f"  项目: {project}")
    print(f"  工具: {5} FastMCP | LLM={'auto' if auto else 'off'}")
    print(f"{'=' * 50}")

    threads = []

    # MCP server thread (stdio, 供agentmesh消费)
    if enable_mcp:
        t = threading.Thread(target=mcp_main, daemon=True)
        t.start()
        threads.append(t)
        print("  [mcp]    ✅ 已启动 (stdin/stdout)")

    # 文件监听
    if watch_enabled:
        w = FileWatcher(project)
        print(f"  [watch]  👀 监听中... (间隔{interval}秒)")
        w.watch(interval=interval)

    elif enable_mcp and not watch_enabled:
        # 只启动MCP时保持主线程存活
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[serve] 🛑 服务已停止")
