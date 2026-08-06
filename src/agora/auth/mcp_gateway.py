"""mcp_gateway — central MCP backend registration for all kairon packages.

Starts and registers all internal MCP backend services through agora's
ProxyManager, making them available via the unified MCP entry points
(ports 7430/7431). Other packages must NOT expose independent MCP ports.

Usage:
    python -m agora.mcp_gateway          # CLI mode (starts all, waits for signal)
    from agora.auth.mcp_gateway import start_all, stop_all
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

import structlog

from agora.mcp_proxy.health import BackendHealthChecker
from agora.mcp_proxy.manager import ProxyManager

logger = structlog.get_logger(__name__)

# ── Known MCP backends ────────────────────────────────────────────
# Each entry defines how ProxyManager should launch the service.
# These commands must be available on $PATH (installed via pip/uv).
# The MCP script entry points (e.g. ``eidos-mcp``) in each package's
# ``pyproject.toml`` remain intact — they are consumed here as stdio
# commands by ProxyManager.

KNOWN_BACKENDS: list[dict] = [
    {
        "name": "eidos",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "eidos", "python", "-m", "eidos.mcp_server"],
    },
    {
        "name": "iris",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "iris", "python", "-m", "iris.mcp_server"],
    },
    {
        "name": "kronos",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "kronos", "python", "-m", "kronos.mcp_server"],
    },
    # !! metaos 独立 MCP 入口已关闭 (2026-06-22) !!
    # 原因: 入口收敛 — metaos 编排能力已通过 bos://ecos/workflow 经 Agora 路由
    #        metaos core/workflow 已注册为 ecos/workflow backend (backend_registry)
    # 手动启动: uv run --package metaos python -m metaos.mcp_server
    # 参见: .omo/tasks/remediation/REMEDIATE-WF-CONV-P0-CLOSE-METAOS-MCP.yaml
    {
        "name": "minerva",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--package",
            "minerva",
            "python",
            "-m",
            "minerva.mcp_server.server",
        ],
    },
    {
        "name": "sophia",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--package",
            "sophia",
            "python",
            "-m",
            "sophia.server.mcp_server",
        ],
    },
    {
        "name": "cron-service",
        "mcp_endpoint": "",
        "command": "cron-service",
        "args": ["--mcp"],
    },
    {
        "name": "omo",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "omo", "python", "-m", "omo.mcp_server"],
    },
    {
        "name": "ecos-bos-mounter",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "ecos", "python", "-m", "ecos.mcp_vfs"],
    },
    {
        "name": "ecos-workflow",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "ecos", "python", "-m", "ecos.mcp_server"],
        "description": "eCOS L0 工作流引擎 MCP (8 workflow tools + SSOT + domain tools)",
    },
    {
        "name": "codeanalyze",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "codeanalyze", "python", "-m", "codeanalyze.mcp"],
    },
    {
        "name": "sot-bridge-persona",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--package",
            "sot-bridge",
            "python",
            "-m",
            "sot_bridge.sharedbrain_bridge.mcp",
        ],
    },
    {
        "name": "forge",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "forge", "python", "-m", "forge.mcp_server"],
    },
    {
        "name": "gbrain",
        "mcp_endpoint": "",
        "command": "bun",
        "args": ["run", "--cwd", "projects/gbrain", "src/cli.ts", "serve"],
    },
    {
        "name": "c2g",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--directory",
            "projects/c2g",
            "python",
            "-m",
            "c2g.mcp_server",
        ],
        "description": "C2G 战略需求引擎 MCP",
    },
    {
        "name": "runtime",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--directory",
            "projects/runtime",
            "python",
            "-m",
            "runtime.mcp_server",
        ],
        "description": "runtime L1 运行时 MCP (30 tools)",
    },
    {
        "name": "l4-kernel",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--directory",
            "projects/l4-kernel",
            "python",
            "-m",
            "l4_kernel.mcp_server",
        ],
        "description": "L4 自我层 MCP",
    },
    {
        "name": "aetherforge",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--directory",
            "projects/aetherforge",
            "python",
            "-m",
            "aetherforge.mcp_server",
        ],
        "description": "aetherforge 能力框架 MCP",
    },
    {
        "name": "aetherforge-gateway",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--directory",
            "projects/aetherforge",
            "--package",
            "aetherforge-gateway",
            "python",
            "-m",
            "llm_gateway.cli",
            "mcp",
        ],
        "description": "AetherForge LLM Gateway — 本地/远程模型统一路由 (SSOT)",
    },
    {
        "name": "model-driven",
        "mcp_endpoint": "",
        "command": "uv",
        "args": [
            "run",
            "--directory",
            "projects/model-driven",
            "python",
            "-m",
            "model_driven.mcp_server",
        ],
        "description": "model-driven 横切框架 MCP (28 tools)",
    },
]

# Module-level singleton — reused across start/stop calls.
_gateway_manager: ProxyManager | None = None
_health_checker: BackendHealthChecker | None = None


def _get_shared_manager() -> ProxyManager:
    """返回并注册共享 ProxyManager 单例.

    与 agora.server.dependencies 的全局单例对齐 (P1 收口):
    复用 dependencies 中的 ProxyManager, 避免两套独立实例各自拉起
    重叠的 backend 子进程。mcp_protocol 等消费方经 dependencies 读取。
    """
    global _gateway_manager
    from agora.server.dependencies import get_proxy_manager, set_proxy_manager

    shared = get_proxy_manager()
    if shared is not None:
        _gateway_manager = shared
        return shared
    if _gateway_manager is None:
        _gateway_manager = ProxyManager()
    set_proxy_manager(_gateway_manager)
    return _gateway_manager


async def start_all() -> dict[str, str]:
    """Start all known backends and register them with the proxy.

    Returns a dict mapping service name → result string ("ok: N tools registered"
    or "error: ..."). Each connection is attempted in parallel.
    """
    global _gateway_manager, _health_checker
    manager = _get_shared_manager()
    _gateway_manager = manager

    # gateway 自身经 launchd `--directory __AGORA_DIR__` 启动, cwd=agora 项目。
    # KNOWN_BACKENDS 用相对路径 (projects/gbrain, projects/c2g) 和 `--package`,
    # 需 cwd=workspace 根才能解析。给每个 backend 补 workspace 根 cwd。
    workspace_root = Path(__file__).resolve().parents[4]  # agora → projects → workspace
    backends = []
    for svc in KNOWN_BACKENDS:
        if not svc.get("cwd"):
            svc = dict(svc)
            svc["cwd"] = str(workspace_root)
        backends.append(svc)

    results = await manager.start(backends)
    ok_count = sum(1 for v in results.values() if v.startswith("ok"))
    logger.info(
        "mcp_gateway_started",
        ok=ok_count,
        failed=len(results) - ok_count,
        services=list(results.keys()),
    )

    # Start background health heartbeat
    if _health_checker is None:
        _health_checker = BackendHealthChecker(manager)
        await _health_checker.start()
        logger.info("mcp_gateway_health_checker_started")

    return results


async def stop_all() -> None:
    """Stop all known backends and clean up the proxy manager.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _gateway_manager, _health_checker
    if _health_checker is not None:
        await _health_checker.stop()
        _health_checker = None
        logger.info("mcp_gateway_health_checker_stopped")
    if _gateway_manager is not None:
        await _gateway_manager.shutdown()
        # 共享单例已注册到 dependencies 时一并清理, 避免悬挂引用。
        from agora.server.dependencies import get_proxy_manager, set_proxy_manager

        if get_proxy_manager() is _gateway_manager:
            set_proxy_manager(None)
        _gateway_manager = None
        logger.info("mcp_gateway_stopped")


def main() -> None:
    """CLI entry point — start all known MCP backends and wait for signal."""

    async def _run() -> None:
        logger.info("mcp_gateway_starting")
        await start_all()

        # Block until SIGINT or SIGTERM is received.
        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            logger.info("mcp_gateway_shutdown_signal_received")
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                # Windows or non-POSIX — fall back to polling
                logger.warning("mcp_gateway_signal_not_supported", sig=sig)

        await stop_event.wait()
        await stop_all()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
