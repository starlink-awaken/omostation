"""Agora MCP Server — unified entry point for all services.

工具分组 (35 tools → BOS/extracted to tools_bos.py, API Keys extracted to tools_api_keys.py):
  ┌─ Proxy Tools      :  proxy_connect/call/status/list/add/remove
  ├─ Registry Tools   :  register_service
  ├─ Routing Tools    :  list_services, check_health, add_route, route_call
  ├─ Event Tools      :  publish/subscribe/get_event_log
  ├─ Audit Tools      :  audit_query, audit_stats
  ├─ API Key Tools    :  extracted → server/tools_api_keys.py  ✅
  ├─ BOS Tools        :  extracted → server/tools_bos.py  ✅
  ├─ A2A Task Tools   :  a2a_send/get/cancel/list_tasks/push_notification
  ├─ State Tools      :  get_state_transitions
  ├─ Agent Cards      :  list/get_agent_card
  ├─ Repo Tools       :  repo_search/discover/status/install/load/unload/pipeline
  ├─ Lifecycle Tools  :  lifecycle_status/start_watch/stop_watch/load_all/unload_all
  └─ Execution        :  agora_execute

拆分计划: docs/god-module-split-plan.md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastmcp import FastMCP
from fastmcp.server.middleware import AuthMiddleware

from agora.audit_subscriber import AuditSubscriber  # type: ignore[import-not-found]
from agora.core.state import get_event_bus, get_registry, get_router  # type: ignore[import-not-found]
from agora.mcp import mcp_bootstrap  # type: ignore[import-not-found]
from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]

# BOS URI 解析器 (P45 W1) — 统一 POC_SERVICES 路由
from agora.mcp.bos_resolver import resolve_bos_uri as _resolve_bos_uri  # type: ignore[import-not-found]
from agora.mcp.bos_resolver import POC_SERVICES as _POC_SERVICES  # type: ignore[import-not-found]

# BOSRouter (P45 W2) — 统一路由注册表
from agora.mcp.bos_router import bos_router as _bos_router  # type: ignore[import-not-found]

# BOS 中间件 (P46 W0) — 限流/熔断/缓存
from agora.mcp.bos_middleware import bos_rate_limiter, bos_circuit_breaker, bos_cache  # type: ignore[import-not-found]
from agora.mcp.bos_middleware import config_watcher  # type: ignore[import-not-found]

# 响应工具 (God Module 拆分)
from agora.server._response import (
    FORMAT_VERSION,
    _error,
    _ok,
)

# BOS 工具 (God Module 拆分 — 13个工具 + 路由/事件/鉴权)
from agora.server.tools_bos import register_bos_tools

logger = structlog.get_logger(__name__)

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")

# Module-level component cache extracted to agora.server.dependencies


from agora.server.tools_auth import (  # noqa: E402
    get_access_token as get_access_token,
    require_agora_api_key as _require_agora_api_key,
)


def identity_from_auth_token() -> dict | None:
    """Backward-compatible identity resolver that respects monkeypatched mcp.get_access_token."""
    token = get_access_token()
    if token is None:
        return None

    claims = getattr(token, "claims", {}) or {}
    subject_id = claims.get("sub") or claims.get("subject_id") or getattr(token, "client_id", "")
    if not subject_id:
        return None

    identity: dict[str, object] = {
        "subject_id": subject_id,
        "subject_type": claims.get("subject_type") or "service",
    }
    if issuer := claims.get("iss") or claims.get("issuer"):
        identity["issuer"] = issuer
    if tenant := claims.get("tenant") or claims.get("org") or getattr(token, "resource", None):
        identity["tenant"] = tenant
    return identity


def _resolve_caller_identity(caller_identity: str | dict | None) -> str | dict:
    """Backward-compatible caller identity normalization for tools_registry."""
    if caller_identity not in (None, ""):
        if isinstance(caller_identity, str):
            try:
                parsed = json.loads(caller_identity)
            except json.JSONDecodeError:
                return caller_identity
            return parsed if isinstance(parsed, dict) else caller_identity
        return caller_identity

    derived = identity_from_auth_token()
    if derived is not None:
        return derived
    return "anonymous"


@asynccontextmanager
async def _proxy_lifespan(server: FastMCP):
    """Initialize proxy connections within mcp.run()'s event loop."""
    from agora.server.dependencies import get_proxy_manager, clear_caches
    from agora.server.tools_proxy import proxy_sync_loop

    _sync_task = None
    _swarm = None
    try:
        await _init_proxy()
        _sync_task = asyncio.create_task(proxy_sync_loop(registry))

        # ── Swarm 启动 (P55) ──
        swarm_role = os.environ.get("AGORA_SWARM_ROLE", "")
        if swarm_role:
            from agora.mcp.swarm import get_swarm, SWARM_DEFAULT_PORT

            swarm_port = int(
                os.environ.get("AGORA_SWARM_PORT", str(SWARM_DEFAULT_PORT))
            )
            _swarm = get_swarm(role=swarm_role, port=swarm_port)
            _swarm.set_proxy_manager(get_proxy_manager())
            _swarm.start()
            logger.info("swarm_started", role=swarm_role, port=swarm_port)
    except Exception:
        logger.exception("proxy_init_in_lifespan")
    
    yield {}
    
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
            
    clear_caches()
    if _swarm is not None:
        _swarm.stop()
        logger.info("swarm_stopped")


from agora.middleware.middleware import FastMCPAuditMiddleware  # noqa: E402

mcp = FastMCP(
    "Agora — Service Convergence Hub",
    lifespan=_proxy_lifespan,
    mask_error_details=True,
    middleware=[AuthMiddleware(auth=_require_agora_api_key), FastMCPAuditMiddleware()],
)
registry = get_registry()
_bus = get_event_bus(registry)
_auditor = AuditSubscriber(_bus, registry)
# Wire audit into event bus: every published event is automatically persisted
_bus.register_hook(_auditor.on_event)
router = get_router(registry, _bus)

# ── BOS Tools Registration ──────────────────────────────────────────
# 注册在 mcp 实例创建后、任何工具定义之前


register_bos_tools(mcp, _bus)

from agora.server.tools_swarm import register_swarm_tools  # type: ignore[import-not-found]  # noqa: E402

register_swarm_tools(mcp)

# ── Proxy / Registry / Diagnostics / Governance Tools ──────────────
# Phase 1: extracted from God Module (server/mcp.py) into focused modules.
# NOTE: imports are at module top level; registration calls are deferred
# until after _PROXY_CONFIG_PATH / _FORGE_REGISTRY_PATH are defined.
from agora.server.tools_proxy import register_proxy_tools, _set_constants as _set_proxy_constants  # noqa: E402, F811
from agora.server.tools_registry import register_registry_tools  # noqa: E402
from agora.server.tools_diagnostics import register_diagnostics_tools  # noqa: E402
from agora.server.tools_governance import register_governance_tools  # noqa: E402
from agora.server.tools_workspace_audit import register_workspace_audit_tools  # noqa: E402

# ── A2A Task Manager ──────────────────────────────────────────────────

_task_manager: TaskManager | None = None  # noqa: F821


def _get_task_manager() -> TaskManager:  # noqa: F821
    """Lazy-init and return the global TaskManager instance."""
    global _task_manager
    if _task_manager is None:
        from agora.a2a.task_manager import TaskManager  # type: ignore[import-not-found]

        _task_manager = TaskManager(router)
    return _task_manager


# ── MCP Proxy Configs ───────────────────────────────────────────────────────

# Path to enriched service config (with command/args for stdio services)
# Resolved relative to project root (same convention as registry.py's agora-services.json)
_PROXY_CONFIG_PATH = mcp_bootstrap.get_data_dir() / "agora-proxy-services.json"

# Forge asset registry path — the single source of truth for service port configs
_FORGE_REGISTRY_PATH = Path.home() / "Workspace" / "Forge" / "assets" / "registry.json"

# ── Wire in proxy/registry/diagnostics/governance tools ─────────────
_set_proxy_constants(_PROXY_CONFIG_PATH, _FORGE_REGISTRY_PATH)
register_proxy_tools(mcp)
register_registry_tools(mcp)
register_diagnostics_tools(mcp)
register_governance_tools(mcp)
register_workspace_audit_tools(mcp)  # Round 43 P1: 6 维度全方位审计 MCP 暴露


async def _init_proxy():
    """Initialize the proxy manager and connect to all configured downstream services.

    Phase 1 — tries ``mcp_bootstrap.scan_and_launch()`` which internally calls
    ``proxy_manager.start()`` with full configs (command/args/cwd/init_timeout).
    If bootstrap succeeds, the second ``start()`` call is *skipped* to avoid
    disconnecting already-connected services.

    Phase 2 — syncs HTTP services from ``ServiceRegistry`` → ``ProxyRegistry``
    so that CLI-registered services appear in the proxy tool listing.

    Phase 3 — registers all proxy downstream tools as native FastMCP tools.
    """
    from agora.server.dependencies import get_proxy_manager, set_proxy_manager, get_lifecycle_manager, set_lifecycle_manager
    pm = get_proxy_manager()
    if pm is not None:
        return

    # ── Phase 0 (BOS-ONLY): 立即裁剪非 BOS 工具，不等 proxy 初始化 ──
    if os.environ.get("AGORA_BOS_ONLY", "").lower() in ("1", "true", "yes"):
        await _bos_only_cleanup(mcp)
        logger.info("bos_only_mode: removed non-BOS management tools")

    pm = ProxyManager()
    set_proxy_manager(pm)
    set_lifecycle_manager(get_lifecycle_manager())

    # ── Phase 1: Try bootstrap (scan_and_launch internally calls start() with full configs) ──
    bootstrap_results = await mcp_bootstrap.scan_and_launch(pm)

    if not bootstrap_results:
        # No bootstrap available — load from proxy config file
        from agora.server.tools_proxy import _load_proxy_services  # type: ignore[import-not-found]  # noqa: F811

        services = _load_proxy_services()
        if services:
            await pm.start(services)
    # else: scan_and_launch already connected services via _build_enabled_services + proxy_manager.start

    # ── Phase 2: Register HTTP services from ServiceRegistry ──
    from agora.server.tools_proxy import _load_proxy_services  # type: ignore[import-not-found]

    proxy_configs = _load_proxy_services()
    await pm.registry.register_from_registry(
        registry, proxy_configs, lazy=True
    )

    # ── Phase 3: Register proxy tools ──
    from agora.server.tools_proxy import _register_proxy_tools
    _register_proxy_tools(mcp, pm)

    # ── Phase 4 (P45 W2): Seed BOSRouter from POC_SERVICES ──
    _bos_router.seed_from_poc(_POC_SERVICES)
    logger.info("bos_router_seeded", poc_count=_bos_router.count())

    # ── Phase 5.5 (FeatureGate): 加载 feature_groups + bos_domains ──
    from agora.mcp_proxy.feature_gate import FeatureGate

    gate = FeatureGate.get_instance()
    # 从代理配置文件预加载 feature_groups & bos_domains
    proxy_config_path = mcp_bootstrap.get_data_dir() / "agora-proxy-services.json"
    if proxy_config_path.exists():
        try:
            proxy_data = json.loads(proxy_config_path.read_text(encoding="utf-8"))
            gate.load(proxy_data)
            logger.info("feature_gate_initialized_from_proxy_config")
        except (json.JSONDecodeError, OSError):
            gate.load()
            logger.info("feature_gate_initialized_defaults")
    else:
        gate.load()
        logger.info("feature_gate_initialized_defaults")

    # ── Phase 6 (P46 W0): 配置 BOS 中间件 ──
    import yaml

    # 预种子路由表
    _bos_router.seed_from_poc(_POC_SERVICES)
    logger.info("bos_router: seeded from POC_SERVICES")

    rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
    if rates_path.exists():
        rates = yaml.safe_load(open(rates_path))
        for route in rates.get("routes", []):
            bos_rate_limiter.configure(route["prefix"], qps=route["qps"])
    else:
        # 硬编码回退
        bos_rate_limiter.configure("bos://analysis/minerva/", qps=5)
        bos_rate_limiter.configure("bos://analysis/code/", qps=10)
        bos_rate_limiter.configure("bos://memory/kronos/", qps=10)
        bos_rate_limiter.configure("bos://memory/kos/", qps=20)
    logger.info("bos_middleware_configured")

    # ── Phase 6 (P46 W1): 从 M1 Workflow 节点自动注册 BOS 路由 ──
    from agora.mcp.bos_auto_register import auto_register_from_m1  # type: ignore[import-not-found]

    count = auto_register_from_m1()
    logger.info("auto_register_from_m1: %d workflow routes seeded", count)

    # ── Phase 7 (P47): 从 AGENTS.md 自动发现 + 信号热加载 ──
    from agora.mcp.bos_discovery import discover_from_workspace  # type: ignore[import-not-found]

    discovered = discover_from_workspace()
    logger.info("bos_discovery: %d URIs discovered from AGENTS.md", discovered)
    _install_signal_handler()

    # ── Phase 8 (P48): 启动配置文件监听 ──
    rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
    if rates_path.exists():

        def _reload_rates():
            import yaml

            try:
                rates = yaml.safe_load(open(rates_path))
                for route in rates.get("routes", []):
                    bos_rate_limiter.configure(route["prefix"], qps=route["qps"])
                logger.info(
                    "config_watcher: rates reloaded (%d routes)",
                    len(rates.get("routes", [])),
                )
            except Exception as e:
                logger.error("config_watcher: reload failed: %s", e)

        config_watcher.file_path = str(rates_path)
        config_watcher._on_change = _reload_rates
        config_watcher.start(interval=5)
        logger.info("config_watcher: started")


async def _bos_only_cleanup(mcp_server: FastMCP) -> None:
    """移除所有非 BOS URI 相关的管理工具。

    BOS-only 模式下只保留:
      - BOS URI 解析 (resolve_bos_uri, read_resource, mutate_resource, ...)
      - BOS 资源 (bos://...)
      移除: proxy 基础设施、代理下游工具、路由/健康、管理噪声
    """
    # 只保留纯 BOS URI 工具
    KEEP_TOOLS = {
        "mutate_resource",
        "resolve_bos_uri",
        "read_resource",
        "list_bos_resources",
        "list_bos_domains",
        "get_bos_schema",
        "bos_middleware_status",
        "bos_reload_m1",
        "bos_reload_discovery",
        "bos_metrics_status",
        "watch_resource",
        "unwatch_resource",
        "list_bos_tools",
    }

    # 获取所有已注册工具
    try:
        provider = getattr(mcp_server, "_local_provider", None)
        if provider is None:
            return
        tools = await provider.list_tools()
    except Exception:
        return

    removed = 0
    for tool in tools:
        name = tool.name if hasattr(tool, "name") else str(tool)
        # 仅保留白名单中的 BOS URI 工具
        if name in KEEP_TOOLS:
            continue
        # 其余全部移除（含代理下游工具、proxy 基础设施、路由、管理工具）
        try:
            provider.remove_tool(name)
            removed += 1
        except (KeyError, Exception):
            pass

    if removed:
        logger.info("bos_only_cleanup: removed %d management tools", removed)


# ── 信号处理 (P46 W2) ─────────────────────────────────


def _install_signal_handler() -> None:
    """安装 SIGUSR1 信号处理器 — 热加载 BOS 配置。"""
    import signal
    import yaml

    def _reload_handler(signum, frame):
        logger.info("signal_handler: received SIGUSR1, reloading BOS config")
        rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
        if rates_path.exists():
            try:
                rates = yaml.safe_load(open(rates_path))
                for route in rates.get("routes", []):
                    bos_rate_limiter.configure(route["prefix"], qps=route["qps"])
                logger.info(
                    "signal_handler: rate limits reloaded (%d routes)",
                    len(rates.get("routes", [])),
                )
            except Exception as e:
                logger.error("signal_handler: failed to reload rates: %s", e)
        # Reload BOSRouter from POC_SERVICES
        for uri, svc in _POC_SERVICES.items():
            _bos_router.register(
                uri,
                adapter="poc",
                config={
                    "domain": getattr(svc, "domain", ""),
                    "transport": getattr(svc, "transport", ""),
                },
            )
        logger.info(
            "signal_handler: BOSRouter reloaded (%d routes)", _bos_router.count()
        )

    try:
        signal.signal(signal.SIGUSR1, _reload_handler)
        logger.info(
            "signal_handler: SIGUSR1 handler installed (kill -USR1 %d to reload)",
            os.getpid(),
        )
    except (AttributeError, ValueError):
        pass  # Windows 不支持 SIGUSR1


# ── 信号处理 (P46 W2) ─────────────────────────────────


# ── Extracted Proxy Tools and Singletons to tools_proxy.py and dependencies.py ──


# ── Phase 34: Agora Mesh V2 (Agent Experience Layer) ────────────────


@mcp.resource("bos://agora/registry")
def agora_registry() -> str:
    """Introspection: returns a JSON dump of all registered tools and resources."""
    import json
    from agora.server.dependencies import get_proxy_manager

    pm = get_proxy_manager()
    if pm:
        tools = pm.list_tools()
        resources = pm.list_resources()
        return json.dumps(
            {
                "tools": [
                    {"name": t.name, "description": t.description} for t in tools
                ],
                "resources": [{"uri": r.uri, "name": r.name} for r in resources],
            },
            indent=2,
        )
    return json.dumps({"error": "proxy manager not initialized"})


@mcp.resource("bos://agora/status")
async def bos_agora_status() -> str:
    """BOS 系统内省 — 统一大盘: 路由/域/中间件/调用量.

    Agent 单次调用即可获取 BOS 系统全貌，无需调多个工具。
    """
    import json

    status = {
        "format_version": FORMAT_VERSION,
        "service": "agora",
        "router": {
            "total_routes": _bos_router.count(),
            "stats": _bos_router.stats(),
        },
        "middleware": {
            "rate_limiter": bos_rate_limiter.status(),
            "circuit_breaker": {
                "open_circuits": bos_circuit_breaker.status(),
            },
            "cache": bos_cache.status(),
        },
        "metrics": bos_metrics.summary(),  # noqa: F821
        "resources_total": _bos_router.count() + len(_POC_SERVICES),
    }
    return json.dumps(status, ensure_ascii=False, indent=2)


@mcp.resource("bos://{domain}/{package}/{action}")
async def bos_universal_resource(domain: str, package: str, action: str) -> str:
    """P45 W2: Universal BOS URI resource handler — 匹配所有 bos:// 请求。

    路由优先级: BOSRouter (POC) → ProxyManager (MCP 代理) → 404
    """
    import json
    from agora.server.dependencies import get_proxy_manager

    uri = f"bos://{domain}/{package}/{action}"
    # Step 1: BOSRouter
    route = _bos_router.resolve(uri)
    if route:
        if route["adapter"] == "poc":
            try:
                result = await _resolve_bos_uri(uri)
                return json.dumps(
                    {
                        "status": "ok",
                        "uri": uri,
                        "source": "bos_router",
                        "result": result,
                        "format_version": FORMAT_VERSION,
                    }
                )
            except Exception as e:
                return json.dumps(
                    {
                        "status": "error",
                        "uri": uri,
                        "error": str(e),
                        "format_version": FORMAT_VERSION,
                    }
                )
    # Step 2: ProxyManager
    pm = get_proxy_manager()
    if pm:
        try:
            result = await pm.read_resource(uri)
            if isinstance(result, dict) and "contents" in result:
                return json.dumps(
                    {
                        "status": "ok",
                        "uri": uri,
                        "source": "proxy",
                        "contents": result["contents"],
                        "format_version": FORMAT_VERSION,
                    }
                )
        except Exception:
            pass
    # Step 3: Not found
    return json.dumps(
        {
            "status": "error",
            "uri": uri,
            "error": f"Resource not found or no provider for: {uri}",
            "format_version": FORMAT_VERSION,
        }
    )


# ── Service management tools ─────────────────────────────────────


# ═══════════════════════════════════════════════════════════════
# Section 6: API Key Tools (extracted → server/tools_api_keys.py)
# ═══════════════════════════════════════════════════════════════
from agora.server.tools_api_keys import register_tools as _register_api_keys  # noqa: E402

_register_api_keys(mcp, _ok, FORMAT_VERSION)


# ═══════════════════════════════════════════════════════════════
# Section: 执行引擎
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
async def agora_execute(query: str, mode: str = "auto") -> dict:
    """Execute a natural language query by routing to the best matching MCP tool.

    Three modes:
    - direct: User knows the tool name ("docker list images" loads docker gateway)
    - recommend: User is unsure, system returns ranked recommendations
    - auto (default): Try direct → recommend → auto-discover external tools

    Args:
        query: Natural language description of what to do
        mode: Routing mode - 'direct', 'recommend', or 'auto' (default: auto)
    """
    try:
        from agora.server.dependencies import get_cached_router
        router_instance = get_cached_router()
        result = await router_instance.route(query, mode=mode)
        return _ok({"format_version": FORMAT_VERSION, **result})
    except Exception as e:
        logger.exception("agora_execute_failed", query=query, mode=mode)
        return _error(f"Execution failed: {e}")


def main():
    """Start the Agora MCP server. Default: stdio. Use --sse for SSE mode."""
    import argparse
    parser = argparse.ArgumentParser(description="Agora MCP Server")
    parser.add_argument("--sse", action="store_true", help="Start in SSE mode (port 7431)")
    parser.add_argument("--http", action="store_true", help="Start in HTTP mode (port 7422)")
    args = parser.parse_args()

    if args.sse:
        sse_main()
    elif args.http:
        http_main()
    else:
        sys.stderr.write("Agora MCP Server (stdio) starting...\n")
        mcp.run()


def http_main():
    """Start the Agora MCP server in HTTP mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    """

    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=7422))  # noqa: S104 — MCP server intentionally binds all interfaces


def sse_main():
    """Start the Agora MCP server in SSE mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    Exposes a /health HTTP endpoint alongside the SSE transport.
    """
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health_endpoint(request):
        return JSONResponse(
            {
                "status": "ok",
                "service": "agora-mcp-sse",
                "tools": len(await mcp.list_tools()),
            }
        )

    from agora.server.a2a import a2a_send_endpoint

    # Add routes
    mcp._additional_http_routes.append(Route("/health", endpoint=health_endpoint))
    mcp._additional_http_routes.append(Route("/api/v1/a2a/send", endpoint=a2a_send_endpoint, methods=["POST"]))

    sys.stderr.write("Agora MCP Server (SSE) starting on port 7431...\n")
    asyncio.run(mcp.run_http_async(transport="sse", host="0.0.0.0", port=7431))  # noqa: S104 — MCP SSE server intentionally binds all interfaces


if __name__ == "__main__":
    main()

# Re-exports for test imports
from agora.server.tools_registry import route_call as route_call  # noqa: E402
from agora.server.tools_proxy import proxy_status as proxy_status  # noqa: E402
from agora.server.tools_proxy import proxy_call as proxy_call  # noqa: E402
from agora.server.tools_proxy import proxy_remove_service as proxy_remove_service  # noqa: E402
