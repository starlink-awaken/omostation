"""Agora MCP Server — unified entry point for all services.

工具分组 (42 tools → Phase 1: API Keys 已提取至 server/tools_api_keys.py):
  ┌─ BOS Tools        (L511):  mutate_resource, read_resource
  ├─ Proxy Tools      (L535):  proxy_connect/call/status/list/add/remove
  ├─ Registry Tools   (L697):  register_service
  ├─ Routing Tools    (L827):  list_services, check_health, add_route, route_call
  ├─ Event Tools      (L911):  publish/subscribe/get_event_log
  ├─ Audit Tools      (L975):  audit_query, audit_stats
  ├─ API Key Tools    (extracted → server/tools_api_keys.py)  ✅ Phase 1
  ├─ A2A Notify       (L1067): register_push_notification
  ├─ A2A Task Tools   (L1104): a2a_send/get/cancel/list_tasks
  ├─ State Tools      (L1203): get_state_transitions
  ├─ Agent Cards      (L1286): list/get_agent_card
  ├─ Repo Tools       (L1335): repo_search/discover/status/install/load/unload/pipeline
  ├─ Lifecycle Tools  (L1567): lifecycle_status/start_watch/stop_watch/load_all/unload_all
  └─ Execution        (L1703): agora_execute

拆分计划: docs/god-module-split-plan.md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, ClassVar

import structlog
from fastmcp import FastMCP
from fastmcp.server.auth.authorization import AuthContext
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import AuthMiddleware
from fastmcp.tools import Tool, ToolResult

from agora.plugins.identity.agent_card import service_to_agent_card  # type: ignore[import-not-found]
from agora.audit_subscriber import AuditSubscriber  # type: ignore[import-not-found]
from agora.auth.identity import normalize_identity  # type: ignore[import-not-found]
from agora.core.service_base import is_safe_url, parse_protocol_config, parse_tags  # type: ignore[import-not-found]
from agora.core.state import get_event_bus, get_registry, get_router  # type: ignore[import-not-found]
from agora.mcp import mcp_bootstrap  # type: ignore[import-not-found]
from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]
from agora.mcp_registry.embeddings import EmbeddingStore  # type: ignore[import-not-found]
from agora.mcp_registry.lifecycle import LifecycleManager  # type: ignore[import-not-found]
from agora.mcp_registry.orchestrator import Orchestrator  # type: ignore[import-not-found]
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]
from agora.mcp_registry.router import SmartRouter  # type: ignore[import-not-found]

# L0 审计 hook — BOS URI 前置校验 + 后置审计
import sys as _sys
_sys.path.insert(0, str(Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools"))
from mof_agora_hook import pre_check as _bos_pre_check, post_audit as _bos_post_audit  # type: ignore[import-not-found]

# BOS URI 解析器 (P45 W1) — 统一 POC_SERVICES 路由
from agora.mcp.bos_resolver import resolve_bos_uri as _resolve_bos_uri  # type: ignore[import-not-found]
from agora.mcp.bos_resolver import list_services as _list_poc_services        # type: ignore[import-not-found]
from agora.mcp.bos_resolver import POC_SERVICES as _POC_SERVICES              # type: ignore[import-not-found]

# BOSRouter (P45 W2) — 统一路由注册表
from agora.mcp.bos_router import bos_router as _bos_router  # type: ignore[import-not-found]

# BOS 中间件 (P46 W0) — 限流/熔断/缓存
from agora.mcp.bos_middleware import bos_rate_limiter, bos_circuit_breaker, bos_cache  # type: ignore[import-not-found]
from agora.mcp.bos_middleware import config_watcher  # type: ignore[import-not-found]

# BOS Metrics (P46 W2) — 可观测性
from agora.mcp.bos_metrics import bos_metrics  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

FORMAT_VERSION = "agora-v1"

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")

# Module-level component cache — avoids re-creating ToolCatalog, EmbeddingStore,
# Orchestrator, SmartRouter, and LifecycleManager on every agora_execute call.
_cached_catalog: ToolCatalog | None = None
_cached_embeddings: EmbeddingStore | None = None
_cached_orchestrator: Orchestrator | None = None
_cached_router: SmartRouter | None = None
_cached_lifecycle_mgr: LifecycleManager | None = None


def _require_agora_api_key(ctx: AuthContext) -> bool:
    """Auth check for AGORA_API_KEY.

    - If AGORA_API_KEY is not configured → permissive mode (allow all, local dev).
    - If configured → require exact bearer token match.
    """
    if not _AGORA_API_KEY:
        return True  # permissive mode for local development
    if ctx.token is None:
        return False
    # AccessToken.token holds the raw bearer token string
    return ctx.token.token == _AGORA_API_KEY


@asynccontextmanager
async def _proxy_lifespan(server: FastMCP):
    """Initialize proxy connections within mcp.run()'s event loop.

    This replaces the old ``asyncio.run(_init_proxy())`` pattern which
    killed subprocesses when the temporary event loop closed. By running
    inside the lifespan context manager, subprocesses stay alive for the
    entire server lifetime.
    """
    _sync_task = None
    try:
        await _init_proxy()
        _sync_task = asyncio.create_task(_proxy_sync_loop())
    except Exception:
        logger.exception("proxy_init_in_lifespan")
    global \
        _lifecycle_manager, \
        _cached_catalog, \
        _cached_embeddings, \
        _cached_orchestrator, \
        _cached_router, \
        _cached_lifecycle_mgr
    yield {}
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
    if _cached_embeddings is not None:
        _cached_embeddings.close()
    if _lifecycle_manager is not None:
        await _lifecycle_manager.close()
    _cached_catalog = None
    _cached_embeddings = None
    _cached_orchestrator = None
    _cached_router = None
    _cached_lifecycle_mgr = None
    _lifecycle_manager = None


from agora.middleware.middleware import FastMCPAuditMiddleware

mcp = FastMCP(
    "Agora — Service Convergence Hub",
    lifespan=_proxy_lifespan,
    mask_error_details=True,
    middleware=[
        AuthMiddleware(auth=_require_agora_api_key),
        FastMCPAuditMiddleware()
    ],
)
registry = get_registry()
_bus = get_event_bus(registry)
_auditor = AuditSubscriber(_bus, registry)
# Wire audit into event bus: every published event is automatically persisted
_bus.register_hook(_auditor.on_event)
router = get_router(registry, _bus)

# ── A2A Task Manager ──────────────────────────────────────────────────

_task_manager: TaskManager | None = None  # noqa: F821


def _get_task_manager() -> TaskManager:  # noqa: F821
    """Lazy-init and return the global TaskManager instance."""
    global _task_manager
    if _task_manager is None:
        from agora.a2a.task_manager import TaskManager  # type: ignore[import-not-found]

        _task_manager = TaskManager(router)
    return _task_manager


# ── MCP Proxy ───────────────────────────────────────────────────────

_proxy_manager: ProxyManager | None = None
_lifecycle_manager: LifecycleManager | None = None  # singleton for background watch tasks

# Path to enriched service config (with command/args for stdio services)
# Resolved relative to project root (same convention as registry.py's agora-services.json)
_PROXY_CONFIG_PATH = mcp_bootstrap.get_data_dir() / "agora-proxy-services.json"

# Forge asset registry path — the single source of truth for service port configs
_FORGE_REGISTRY_PATH = Path.home() / "Workspace" / "Forge" / "assets" / "registry.json"


def _load_proxy_services() -> list[dict]:
    """Load proxy service configs.

    Priority:
    1. `agora-proxy-services.json` explicit config (stdio + HTTP services).
    2. Fallback: Forge asset registry (`assets/registry.json`) — filtered to
       MCP-tagged services with port > 0, enriched with HTTP MCP endpoint URLs.

    The explicit config takes priority because it contains stdio service configs
    with command/args that cannot be expressed in the Forge registry alone.
    """
    # Try explicit config first (supports stdio services with command/args)
    if _PROXY_CONFIG_PATH.exists():
        from agora.persistence import json_load  # type: ignore[import-not-found]

        data = json_load(_PROXY_CONFIG_PATH, default={})
        if data:
            result = data if isinstance(data, list) else data.get("services", [])
            if result:
                return result

    # Fallback to Forge registry auto-discovery
    forge_services = _try_load_forge_registry()
    if forge_services:
        return forge_services

    return []


def _try_load_forge_registry() -> list[dict] | None:
    """Try to load MCP service configs from the Forge asset registry.

    Returns a list of proxy-compatible service configs, or None if the
    registry file is unavailable.
    """
    if not _FORGE_REGISTRY_PATH.exists():
        return None

    try:
        reg = json.loads(_FORGE_REGISTRY_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    svcs = reg.get("entities", {}).get("service", {}).get("items", [])
    if not svcs:
        return None

    results = []
    for s in svcs:
        name = s.get("name", "")
        port = s.get("port", 0)
        host = s.get("host", "localhost")
        tags = s.get("tags", [])
        health = s.get("health_endpoint", "")

        if not name or port <= 0:
            continue

        # Only include MCP-tagged services that can be proxied
        tags_lower = [t.lower() for t in tags]
        if not any(t in tags_lower for t in ("mcp", "runtime", "api")):
            continue

        # Build MCP endpoint — try /mcp first, fall back to /sse
        mcp_endpoint = f"http://{host}:{port}/mcp"
        cfg = {
            "name": name,
            "description": s.get("description", ""),
            "mcp_endpoint": mcp_endpoint,
        }
        if health:
            cfg["health_endpoint"] = health
        if "sharedbrain" in name.lower():
            cfg["mcp_endpoint"] = f"http://{host}:{port}/mcp"
        elif "hermes" in name.lower():
            cfg["mcp_endpoint"] = f"http://{host}:{port}/sse"

        results.append(cfg)

    return results if results else None


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
    global _proxy_manager, _lifecycle_manager, _cached_lifecycle_mgr
    if _proxy_manager is not None:
        return

    _proxy_manager = ProxyManager()
    _lifecycle_manager = _get_lifecycle_manager()

    # ── Phase 1: Try bootstrap (scan_and_launch internally calls start() with full configs) ──
    bootstrap_results = await mcp_bootstrap.scan_and_launch(_proxy_manager)

    if not bootstrap_results:
        # No bootstrap available — load from proxy config file
        services = _load_proxy_services()
        if services:
            await _proxy_manager.start(services)
    # else: scan_and_launch already connected services via _build_enabled_services + proxy_manager.start

    # ── Phase 2: Register HTTP services from ServiceRegistry ──
    proxy_configs = _load_proxy_services()
    await _proxy_manager.registry.register_from_registry(registry, proxy_configs)

    # ── Phase 3: Register proxy tools ──
    _register_proxy_tools(mcp, _proxy_manager)

    # ── Phase 4 (P45 W2): Seed BOSRouter from POC_SERVICES ──
    for uri, svc in _POC_SERVICES.items():
        _bos_router.register(uri, adapter="poc", config={
            "domain": getattr(svc, "domain", ""),
            "transport": getattr(svc, "transport", ""),
            "description": getattr(svc, "description", ""),
        })
    logger.info("bos_router_seeded", poc_count=_bos_router.count())

    # ── Phase 5 (P46 W0): 配置 BOS 中间件 ──
    # 从配置文件读取限流 QPS，硬编码作为回退
    import yaml
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
                logger.info("config_watcher: rates reloaded (%d routes)", len(rates.get("routes", [])))
            except Exception as e:
                logger.error("config_watcher: reload failed: %s", e)
        config_watcher.file_path = str(rates_path)
        config_watcher._on_change = _reload_rates
        config_watcher.start(interval=5)
        logger.info("config_watcher: started")


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
                logger.info("signal_handler: rate limits reloaded (%d routes)", len(rates.get("routes", [])))
            except Exception as e:
                logger.error("signal_handler: failed to reload rates: %s", e)
        # Reload BOSRouter from POC_SERVICES
        for uri, svc in _POC_SERVICES.items():
            _bos_router.register(uri, adapter="poc", config={
                "domain": getattr(svc, "domain", ""),
                "transport": getattr(svc, "transport", ""),
            })
        logger.info("signal_handler: BOSRouter reloaded (%d routes)", _bos_router.count())

    try:
        signal.signal(signal.SIGUSR1, _reload_handler)
        logger.info("signal_handler: SIGUSR1 handler installed (kill -USR1 %d to reload)", os.getpid())
    except (AttributeError, ValueError):
        pass  # Windows 不支持 SIGUSR1


# ── 辅助函数 ─────────────────────────────────────────
# _ok() / _error() 集中管理返回格式。
# 注意：_ok() 的 data 参数中不内建 format_version，
# 要求每个工具函数显式传递（以便 SOP 的 AST 静态检测能在工具函数体中找到字面量）。


def _error(msg: str) -> dict:
    """返回标准错误响应（内建 format_version）。"""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}

# NOTE: _ok/_error 定义当前与 agora.response_helpers 略有不同（此处内建 format_version）。
# 待 God Module 拆分完成后可统一使用 response_helpers 版本。


# ── BOSRouter 路由辅助函数 (P48 W3) ──────────────────────────
async def _resolve_with_router(uri: str, **kwargs: Any) -> tuple[dict, str]:
    """路由解析链: BOSRouter → POC_SERVICES.

    Args:
        uri: BOS URI
        **kwargs: 传给下游服务的参数

    Returns:
        (result_dict, source_name) 其中 source_name 标明来源
    """
    # Step 1: BOSRouter 查找
    route = _bos_router.resolve(uri)
    if route is not None:
        adapter = route.get("adapter", "")
        if adapter == "poc":
            # POC 路由 → 走子进程
            result = await _resolve_bos_uri(uri, **kwargs)
            if isinstance(result, dict) and result.get("status") == "error":
                # URI 在 BOSRouter 注册表中但 POC_SERVICES 没有执行后端
                # → 返回路由配置信息作为回退
                config = route.get("config", {})
                return {
                    "uri": uri,
                    "status": "info",
                    "source": "bos_router_metadata",
                    "note": "Route registered but no executable backend (metadata only)",
                    "adapter": adapter,
                    "config": config,
                }, "bos_router_metadata"
            return result, "bos_router_poc"
        elif adapter == "proxy" and _proxy_manager is not None:
            try:
                result = await _proxy_manager.read_resource(uri)
                if isinstance(result, dict) and "contents" in result:
                    return result["contents"], "bos_router_proxy"
            except Exception:
                pass
        elif adapter in ("http", "internal"):
            # HTTP / internal 路由 → 尝试 POC_SERVICES 调用回退
            result = await _resolve_bos_uri(uri, **kwargs)
            if isinstance(result, dict) and result.get("status") != "error":
                return result, "bos_router_fallback"
            # 返回路由元数据
            return {
                "uri": uri,
                "status": "info",
                "source": "bos_router_metadata",
                "note": f"Route registered (adapter={adapter}) but no executable backend",
                "adapter": adapter,
                "config": route.get("config", {}),
            }, "bos_router_metadata"
        # 未知 adapter → 继续 Step 2

    # Step 2: POC_SERVICES 直查（兼容旧版）
    result = await _resolve_bos_uri(uri, **kwargs)
    return result, "poc_services"


def _identity_from_auth_token() -> dict | None:
    """Best-effort identity derivation from the current FastMCP access token."""
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
    if scopes := getattr(token, "scopes", None):
        identity["scopes"] = list(scopes)
    return identity


def _resolve_caller_identity(caller_identity: str | dict | None) -> str | dict:
    try:
        explicit_identity = (
            json.loads(caller_identity) if isinstance(caller_identity, str) and caller_identity else caller_identity
        )
    except json.JSONDecodeError:
        explicit_identity = "unknown"

    if explicit_identity:
        normalized = normalize_identity(explicit_identity)
        return normalized.to_payload() if normalized else explicit_identity

    token_identity = _identity_from_auth_token()
    if token_identity:
        normalized = normalize_identity(token_identity)
        return normalized.to_payload() if normalized else token_identity

    return "unknown"


# ── ProxyForwardTool ──────────────────────────────────────────────


class ProxyForwardTool(Tool):
    """FastMCP Tool that forwards calls directly to the proxy dispatch.

    Unlike FunctionTool, this bypasses argument type validation (which cannot
    handle dynamic downstream JSON Schemas), allowing any downstream service's
    tools to be exposed as native FastMCP tools.
    """

    # Stored as ClassVar to exclude from Pydantic model fields (ProxyManager
    # is not a Pydantic model and cannot be serialised by pydantic-core).
    _pm: ClassVar[ProxyManager | None] = None
    proxy_tool_name: str = ""

    async def run(self, arguments: dict) -> ToolResult:
        pm = self._pm
        if pm is None:
            msg = "Proxy not initialized"
            return self.convert_result({"status": "error", "error": msg})
        try:
            result = await pm.dispatch(self.proxy_tool_name, arguments)
            return self.convert_result(result)
        except ValueError as e:
            return self.convert_result({"status": "error", "error": str(e)})
        except Exception as e:
            return self.convert_result({"status": "error", "error": f"Proxy call failed: {str(e)[:200]}"})


# Track which proxy tools have been registered as FastMCP tools,
# so we can clean up on re-registration.
_registered_proxy_tools: set[str] = set()


def _register_proxy_tools(mcp_server: FastMCP, pm: ProxyManager):
    """Register all proxy downstream tools as native FastMCP tools.

    Each downstream tool becomes directly callable via ``tools/call``
    with ``name: "{service}.{original_tool_name}"``.
    Re-registration: if a tool was previously registered, it is removed
    first to avoid FastMCP duplicate-tool errors.
    """
    # Set the ClassVar proxy manager reference once for all tools
    ProxyForwardTool._pm = pm

    for entry in pm.registry.entries.values():
        # Remove stale version if this is a reconnection
        if entry.tool_name in _registered_proxy_tools:
            try:
                mcp_server.remove_tool(entry.tool_name)
            except Exception:
                pass
        mcp_server.add_tool(
            ProxyForwardTool(
                name=entry.tool_name,
                description=entry.description,
                parameters=entry.parameters,
                proxy_tool_name=entry.tool_name,
            )
        )
        _registered_proxy_tools.add(entry.tool_name)


def _unregister_proxy_tools(mcp_server: FastMCP, pm: ProxyManager):
    """Remove all proxy tools previously registered as FastMCP tools."""
    for entry in pm.registry.entries.values():
        if entry.tool_name in _registered_proxy_tools:
            try:
                mcp_server.remove_tool(entry.tool_name)
            except Exception:
                pass
            _registered_proxy_tools.discard(entry.tool_name)


def _get_lifecycle_manager() -> LifecycleManager:
    """Get or create the global LifecycleManager singleton.

    Ensures all lifecycle tools (start_watch, stop_watch, load_all, unload_all)
    operate on the same instance so that background watch tasks can be correctly
    started, stopped, and share state (``_last_used`` timestamps).
    """
    global _cached_lifecycle_mgr
    if _cached_lifecycle_mgr is not None:
        return _cached_lifecycle_mgr
    catalog = _get_cached_catalog()
    _cached_lifecycle_mgr = LifecycleManager(
        catalog=catalog,
        proxy_manager=_proxy_manager,
    )
    return _cached_lifecycle_mgr


def _get_cached_catalog() -> ToolCatalog:
    """Get or create the module-level cached ToolCatalog instance."""
    global _cached_catalog
    if _cached_catalog is None:
        _cached_catalog = ToolCatalog()
    return _cached_catalog


def _get_cached_embeddings() -> EmbeddingStore:
    """Get or create the module-level cached EmbeddingStore instance."""
    global _cached_embeddings
    if _cached_embeddings is None:
        catalog = _get_cached_catalog()
        _cached_embeddings = EmbeddingStore(catalog._db_path)
    return _cached_embeddings


def _get_cached_orchestrator() -> Orchestrator:
    """Get or create the module-level cached Orchestrator instance."""
    global _cached_orchestrator
    if _cached_orchestrator is None:
        catalog = _get_cached_catalog()
        lifecycle = _get_lifecycle_manager()
        _cached_orchestrator = Orchestrator(catalog=catalog, lifecycle=lifecycle)
    return _cached_orchestrator


def _get_cached_router() -> SmartRouter:
    """Get or create the module-level cached SmartRouter instance."""
    global _cached_router
    if _cached_router is None:
        catalog = _get_cached_catalog()
        embeddings = _get_cached_embeddings()
        lifecycle = _get_lifecycle_manager()
        orchestrator = _get_cached_orchestrator()
        _cached_router = SmartRouter(
            catalog=catalog,
            embeddings=embeddings,
            lifecycle=lifecycle,
            orchestrator=orchestrator,
        )
    return _cached_router


async def _proxy_sync_loop():
    """Background task: periodically sync ServiceRegistry -> ProxyRegistry.

    Picks up services registered via CLI (discover --register, sync, etc.)
    that were not added to the proxy at registration time because the proxy
    runs in a different process.

    Uses exponential backoff: starts at 10 seconds, doubles up to 120 seconds
    on failure; resets to 10 seconds on success.
    """
    backoff = 10
    while True:
        await asyncio.sleep(backoff)
        if _proxy_manager is None:
            backoff = min(backoff * 2, 120)
            continue
        try:
            proxy_configs = _load_proxy_services()
            await _proxy_manager.registry.register_from_registry(registry, proxy_configs)
            backoff = 10  # reset on success
        except Exception:
            logger.exception("proxy_sync_loop_error")
            backoff = min(backoff * 2, 120)


# ── Phase 34: Agora Mesh V2 (Agent Experience Layer) ────────────────

@mcp.resource("bos://agora/registry")
def agora_registry() -> str:
    """Introspection: returns a JSON dump of all registered tools and resources."""
    import json
    if _proxy_manager:
        tools = _proxy_manager.list_tools()
        resources = _proxy_manager.list_resources()
        return json.dumps({
            "tools": [{"name": t.name, "description": t.description} for t in tools],
            "resources": [{"uri": r.uri, "name": r.name} for r in resources]
        }, indent=2)
    return json.dumps({"error": "proxy manager not initialized"})


@mcp.resource("bos://{domain}/{package}/{action}")
async def bos_universal_resource(domain: str, package: str, action: str) -> str:
    """P45 W2: Universal BOS URI resource handler — 匹配所有 bos:// 请求。
    
    路由优先级: BOSRouter (POC) → ProxyManager (MCP 代理) → 404
    """
    import json
    uri = f"bos://{domain}/{package}/{action}"
    # Step 1: BOSRouter
    route = _bos_router.resolve(uri)
    if route:
        if route["adapter"] == "poc":
            try:
                result = await _resolve_bos_uri(uri)
                return json.dumps({"status": "ok", "uri": uri, "source": "bos_router",
                                  "result": result, "format_version": FORMAT_VERSION})
            except Exception as e:
                return json.dumps({"status": "error", "uri": uri, "error": str(e),
                                  "format_version": FORMAT_VERSION})
    # Step 2: ProxyManager
    if _proxy_manager:
        try:
            result = await _proxy_manager.read_resource(uri)
            if isinstance(result, dict) and "contents" in result:
                return json.dumps({"status": "ok", "uri": uri, "source": "proxy",
                                  "contents": result["contents"], "format_version": FORMAT_VERSION})
        except Exception:
            pass
    # Step 3: Not found
    return json.dumps({"status": "error", "uri": uri,
                      "error": f"Resource not found or no provider for: {uri}",
                      "format_version": FORMAT_VERSION})


# ═══════════════════════════════════════════════════════════════
# Section 1: BOS Tools (行 530-553)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def mutate_resource(uri: str, payload: str, action: str = "update") -> dict:
    """Unified BOS URI mutation protocol. Routes to downstream service via resolve_bos_uri.
    
    Args:
        uri: The bos:// URI to mutate.
        payload: JSON string payload.
        action: The verb (update, create, delete).
    """
    import json
    import time as _time
    logger.info("mutate_resource", uri=uri, action=action)
    if not uri.startswith("bos://"):
        return _error(f"Invalid URI scheme. Must start with bos://. Received: {uri}")
    
    # P46 W0: 限流
    if not bos_rate_limiter.acquire(uri):
        return _error(f"Rate limit exceeded for: {uri}")
    
    # L0 前置校验
    ok, reason = _bos_pre_check(uri)
    if not ok:
        logger.warning("bos_pre_check_blocked", uri=uri, reason=reason)
        return _error(f"BOS pre-check failed: {reason}")
    
    _t0 = _time.time()
    try:
        # P48 W3: BOSRouter 优先路由
        result, source = await _resolve_with_router(uri, payload=json.loads(payload) if isinstance(payload, str) else payload, action=action)
        _duration_ms = int((_time.time() - _t0) * 1000)
        # 写入操作 → 缓存失效
        bos_cache.invalidate(uri)
        _bos_post_audit(uri, 200, _duration_ms)
        _publish_bos_event(uri, "mutate", "ok", _duration_ms)
        return _ok({"format_version": FORMAT_VERSION, "uri": uri, "action": action, "source": source, "result": result})
    except Exception as e:
        _duration_ms = int((_time.time() - _t0) * 1000)
        _bos_post_audit(uri, 500, _duration_ms)
        _publish_bos_event(uri, "mutate", "error", _duration_ms)
        logger.exception("mutate_resource_failed", uri=uri, action=action)
        return _error(f"Mutation failed: {e}")


# ═══════════════════════════════════════════════════════════════
# Section 2: Proxy Tools (行 558-715)
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def proxy_connect() -> dict:
    """Connect to all configured downstream MCP services via the proxy.

    Reads from agora-proxy-services.json for service definitions.
    Returns connection results for each service.
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()

    services = _load_proxy_services()
    if not services:
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "warning": "No proxy services configured in agora-proxy-services.json",
            }
        )

    results = await _proxy_manager.start(services)

    # Register downstream proxy tools as native FastMCP tools
    _register_proxy_tools(mcp, _proxy_manager)

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "services": results,
        }
    )


@mcp.tool()
async def proxy_call(tool_name: str, arguments: str = "{}") -> dict:
    """Call a downstream service tool through the MCP proxy.

    The proxy connects to registered downstream MCP services (via stdio or HTTP)
    and forwards tool calls. Supports both exact and prefix tool name matching.

    Args:
        tool_name: Full tool name (e.g. 'kos.semantic_search', 'minerva.research_now')
        arguments: JSON string of tool arguments
    """
    if _proxy_manager is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}

    # L0 前置校验
    _bos_uri = f"bos://agora/tools/{tool_name}"
    _ok_check, _reason = _bos_pre_check(_bos_uri)
    if not _ok_check:
        logger.warning("bos_pre_check_blocked", uri=_bos_uri, reason=_reason)
        return _error(_reason)

    _t0 = __import__('time').time()
    try:
        result = await _proxy_manager.dispatch(tool_name, args)
        _bos_post_audit(_bos_uri, 200, int((__import__('time').time() - _t0) * 1000))
        return _ok({"format_version": FORMAT_VERSION, **result})
    except ValueError as e:
        _bos_post_audit(_bos_uri, 400, int((__import__('time').time() - _t0) * 1000))
        return _error(str(e))
    except Exception as e:
        _bos_post_audit(_bos_uri, 500, int((__import__('time').time() - _t0) * 1000))
        return _error(f"Proxy call failed: {str(e)[:200]}")


@mcp.tool()
async def proxy_status() -> dict:
    """Show current proxy connection status and available tools."""
    if _proxy_manager is None:
        return _error("Proxy not initialized")

    status = _proxy_manager.status()
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": status,
        }
    )


@mcp.tool()
async def proxy_list_tools() -> dict:
    """List all available downstream proxy tools with full schemas.

    Returns a flat list of all currently registered proxy tools,
    each with name, description, and inputSchema compatible with
    standard MCP tool format.
    """
    if _proxy_manager is None:
        return _error("Proxy not initialized")

    tools = []
    for entry in _proxy_manager.registry.entries.values():
        tools.append(
            {
                "name": entry.tool_name,
                "description": entry.description,
                "inputSchema": entry.parameters,
                "service_name": entry.service_name,
                "original_name": entry.original_name,
            }
        )

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "tools": tools,
            "count": len(tools),
        }
    )


@mcp.tool()
async def proxy_add_service(
    name: str,
    mcp_endpoint: str = "",
    command: str = "",
    args: str = "",
) -> dict:
    """Add and connect a downstream MCP service to the proxy.

    Args:
        name: Service name (e.g. 'kos', 'minerva')
        mcp_endpoint: HTTP endpoint URL (e.g. 'http://localhost:7420/mcp')
                      Leave empty for stdio services
        command: Command for stdio services (e.g. 'python3')
        args: Space-separated arguments for stdio command
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()

    svc: dict = {"name": name}
    if mcp_endpoint:
        svc["mcp_endpoint"] = mcp_endpoint
    if mcp_endpoint and not is_safe_url(mcp_endpoint):
        return _error(f"Unsafe endpoint URL: {mcp_endpoint}")
    if command:
        svc["command"] = command
    if args:
        svc["args"] = args.split()

    result = await _proxy_manager.add_service(svc)
    return _ok({"format_version": FORMAT_VERSION, "action": result})


@mcp.tool()
async def proxy_remove_service(name: str) -> dict:
    """Disconnect and remove a downstream service from the proxy."""
    if _proxy_manager is None:
        return _error("Proxy not initialized")

    await _proxy_manager.remove_service(name)
    _bus.publish("registry:service.removed", {"name": name}, source="agora.server.mcp")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "removed",
            "service": name,
        }
    )


# ── Service management tools ─────────────────────────────────────



# ═══════════════════════════════════════════════════════════════
# Section 3: Registry Tools (register_service)
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def register_service(
    name: str,
    description: str = "",
    protocol: str = "mcp",
    protocol_config: str = "{}",
    mcp_endpoint: str = "",
    health_endpoint: str = "",
    port: int = 0,
    tags: str = "",
    command: str = "",
    mcp_args: str = "",
    # A2A metadata for Agent Card
    has_auth: bool = False,
    has_push_notifications: bool = False,
    has_state_transitions: bool = False,
    provider_info: str = "",
    documentation_url: str = "",
) -> dict:
    """Register a service with the Agora hub.

    Args:
        name: Unique service name (e.g. 'minerva', 'kos', 'sophia')
        description: Human-readable description
        protocol: Service protocol — mcp | rest | grpc | stdio | websocket (default: mcp)
        protocol_config: JSON string of protocol-specific settings (default: {})
        mcp_endpoint: Server URL (e.g. 'http://localhost:8765/mcp'), also used for REST endpoints
        health_endpoint: Health check URL (e.g. 'http://localhost:8765/health')
        port: Service port
        tags: Comma-separated tags
        command: Command for proxy/stdio connection (e.g. 'python3')
        mcp_args: Space-separated args for proxy/stdio command
        has_auth: Service uses authentication
        has_push_notifications: Service supports push notifications
        has_state_transitions: Service tracks state transitions
        provider_info: JSON string with provider info (e.g. '{"organization":"MyOrg"}')
        documentation_url: Documentation URL for the service
    """
    from agora.core.registry import Service, ServiceConfig  # type: ignore[import-not-found]

    cfg = ServiceConfig(
        name=name,
        description=description,
        protocol=protocol,
        protocol_config=protocol_config,
        mcp_endpoint=mcp_endpoint,
        health_endpoint=health_endpoint,
        port=port,
        tags=tags,
        command=command,
        mcp_args=mcp_args,
    )
    if not (0 <= cfg.port <= 65535):
        return _error("Port must be 0-65535")

    proto_cfg, err = parse_protocol_config(cfg.protocol_config)
    if err:
        return _error(f"protocol_config is not valid JSON: {err}")

    svc = Service(
        name=cfg.name,
        description=cfg.description,
        protocol=cfg.protocol,
        protocol_config=proto_cfg,
        mcp_endpoint=cfg.mcp_endpoint,
        health_endpoint=cfg.health_endpoint,
        port=cfg.port,
        tags=parse_tags(cfg.tags),
    )
    try:
        registry.register(svc)
    except ValueError as e:
        return _error(str(e))

    # Set A2A / Agent Card metadata
    svc.has_auth = has_auth
    svc.has_push_notifications = has_push_notifications
    svc.has_state_transitions = has_state_transitions
    if provider_info:
        try:
            svc.provider_info = json.loads(provider_info)
        except json.JSONDecodeError:
            svc.provider_info = {"raw": provider_info}
    if documentation_url:
        svc.documentation_url = documentation_url

    if cfg.command:
        _save_proxy_service(
            {
                "name": cfg.name,
                "command": cfg.command,
                "args": cfg.mcp_args.split() if cfg.mcp_args else [],
                "mcp_endpoint": cfg.mcp_endpoint,
            }
        )

    # If proxy is active, also add to proxy runtime dynamically
    if _proxy_manager and (cfg.mcp_endpoint.startswith("http") or cfg.command):
        proxy_svc: dict = {"name": cfg.name}
        if cfg.mcp_endpoint:
            proxy_svc["mcp_endpoint"] = cfg.mcp_endpoint
        if cfg.command:
            proxy_svc["command"] = cfg.command
            proxy_svc["args"] = cfg.mcp_args.split() if cfg.mcp_args else []
        proxy_result = await _proxy_manager.add_service(proxy_svc)
        if proxy_result.startswith("error"):
            logger.warning("register_service_proxy_add_failed", service=cfg.name, reason=proxy_result)

    _bus.publish("registry:service.registered", {"name": cfg.name}, source="agora.server.mcp")

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "registered",
            "name": name,
        }
    )


def _save_proxy_service(svc: dict):
    """Append a service config to the proxy services file."""
    from agora.persistence import json_save

    existing = _load_proxy_services()
    # Replace if exists, else append
    existing = [s for s in existing if s.get("name") != svc.get("name")]
    existing.append(svc)
    json_save(_PROXY_CONFIG_PATH, existing)



# ═══════════════════════════════════════════════════════════════
# Section 4: Routing & Events
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def list_services() -> dict:
    """List all registered services and their health status."""
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": registry.to_dict(),
        }
    )


@mcp.tool()
async def check_health() -> dict:
    """Probe all registered services' health endpoints."""
    await registry.health_check_all()
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "total": len(registry.list_all()),
            "healthy": len(registry.list_healthy()),
            "services": registry.to_dict(),
        }
    )


@mcp.tool()
def add_route(tool_name: str, service_name: str) -> dict:
    """Map a tool name to a service for routing.

    Args:
        tool_name: The tool name (e.g. 'minerva.research_now' or just 'minerva' for prefix)
        service_name: The registered service name
    """
    if not tool_name.strip() or not service_name.strip():
        return _error("Tool name and service name required")

    # L0 审计 — 路由变更事件
    _bos_post_audit(f"bos://agora/routes/{tool_name}", 200, 0)

    router.add_route(tool_name, service_name)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "routed",
            "tool": tool_name,
            "service": service_name,
        }
    )


@mcp.tool()
def list_routes() -> dict:
    """List all tool → service route mappings."""
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": router.list_routes(),
        }
    )


@mcp.tool()
async def route_call(tool_name: str, arguments: str = "{}", caller_identity: str = "") -> dict:
    """Route a tool call to the appropriate service.

    Args:
        tool_name: The tool to call (e.g. 'minerva.research_now')
        arguments: JSON string of arguments
        caller_identity: Optional JSON string with structured caller identity
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}
    identity = _resolve_caller_identity(caller_identity)
    result = await router.route(tool_name, args, caller_id=identity or "unknown")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": result,
        }
    )


# ── Event Bus tools (Phase 1, spec §4.2) ──────────────────────────────


@mcp.tool()
def publish_event(event_type: str, payload: str, source: str = "") -> dict:
    """Publish an event to the bus. payload is a JSON string.

    Args:
        event_type: Event type (e.g. 'index:done', 'registry:tools.updated')
        payload: JSON string with event data
        source: Source service name (e.g. 'kos', 'claude-code')
    """
    bus = _bus
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        data = {"raw": payload}
    event_id = bus.publish(event_type, data, source)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "event_id": event_id,
            "action": "published",
        }
    )


@mcp.tool()
def subscribe_event(pattern: str, callback_url: str = "") -> dict:
    """Subscribe to events matching pattern.

    Args:
        pattern: Event pattern ('index:*', 'index:done', '*')
        callback_url: Optional HTTP callback URL for push delivery
    """
    bus = _bus
    sub_id = bus.subscribe("mcp-caller", pattern, callback_url)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "subscription_id": sub_id,
            "pattern": pattern,
        }
    )


@mcp.tool()
def get_event_log(limit: int = 50, since: str = "") -> dict:
    """Query historical events.

    Args:
        limit: Max events to return (default 50)
        since: ISO timestamp, only return events after this time
    """
    bus = _bus
    events = bus.get_event_log(limit, since)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": events,
        }
    )


# ── Governance tools (v2.0) ─────────────────────────────────────



# ═══════════════════════════════════════════════════════════════
# Section 5: Audit Tools
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def audit_query(actor: str = "", resource: str = "", event_type: str = "", since: str = "", limit: int = 50) -> dict:
    """Query the audit log for persisted events.

    Use this for debugging, compliance checks, and understanding
    what has happened in the system over time.

    Args:
        actor: Filter by actor (e.g., 'registry', 'pipeline', 'proxy', 'system')
        resource: Filter by resource type (e.g., 'service', 'route', 'proxy', 'system')
        event_type: Filter by event type pattern (e.g., 'registry:*', 'error:*')
        since: ISO timestamp (e.g., '2026-05-01T00:00:00Z')
        limit: Max results (default 50)

    Returns filtered audit log entries with metadata.
    """
    entries = _auditor.query(actor=actor, resource=resource, event_type=event_type, since=since, limit=limit)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "entries": entries,
            "count": len(entries),
        }
    )


@mcp.tool()
def audit_stats(since: str = "") -> dict:
    """Get audit log statistics — counts grouped by risk level and event type.

    Args:
        since: ISO timestamp to filter from (e.g., '2026-05-01T00:00:00Z')

    Returns summary stats useful for dashboards and monitoring.
    """
    stats = _auditor.stats(since=since)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "stats": stats,
        }
    )



# ═══════════════════════════════════════════════════════════════
# Section 6: API Key Tools (extracted → server/tools_api_keys.py)
# ═══════════════════════════════════════════════════════════════
from agora.server.tools_api_keys import register_tools as _register_api_keys

_register_api_keys(mcp, _ok, FORMAT_VERSION)


# ── Push Notification tools (A2A-compatible) ──────────────────────────



# ═══════════════════════════════════════════════════════════════
# Section 7: A2A Tools (push/task/state)
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def register_push_notification(callback_url: str, event_types: str = "*") -> dict:
    """Register a webhook callback for push notification delivery.

    When matching events occur, Agora will POST the event payload
    to the specified callback URL (with retry up to 3 attempts).

    Args:
        callback_url: HTTP endpoint to receive push notifications
        event_types: Comma-separated event type patterns
                     (e.g. 'registry:*,route:call.failed' or '*' for all)
    """
    if not callback_url or not callback_url.startswith("http"):
        return _error("callback_url must be a valid HTTP URL")
    if not is_safe_url(callback_url):
        return _error(f"Unsafe callback URL: {callback_url}")

    patterns = [p.strip() for p in event_types.split(",") if p.strip()]

    bus = _bus
    results = {}
    for pattern in patterns:
        sub_id = bus.subscribe("a2a-push", pattern, callback_url)
        results[pattern] = sub_id

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "subscriptions": results,
            "callback_url": callback_url,
        }
    )


# ── A2A Task tools (A2A-compatible) ───────────────────────────────────


@mcp.tool()
async def a2a_send_task(tool_name: str, arguments: str = "{}", session_id: str = "") -> dict:
    """Submit a tool call as an A2A task and execute it.

    Creates a task, routes it to the appropriate service via the router,
    and returns the completed result with task metadata.

    Args:
        tool_name: Full tool name (e.g. 'minerva.research_now')
        arguments: JSON string of tool arguments
        session_id: Optional session identifier for grouping related tasks
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}

    tm = _get_task_manager()
    task = tm.create_task("", tool_name, args, session_id)
    result = await tm.execute_task(task.id)
    if result is None:
        return _error("Task execution returned no result")

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "task": result.to_dict(),
        }
    )


@mcp.tool()
def a2a_get_task(task_id: str) -> dict:
    """Get an A2A task's current status and result.

    Args:
        task_id: The task ID to query
    """
    tm = _get_task_manager()
    task = tm.get_task(task_id)
    if task is None:
        return _error(f"Task '{task_id}' not found")

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "task": task.to_dict(),
        }
    )


@mcp.tool()
def a2a_cancel_task(task_id: str) -> dict:
    """Cancel a submitted or in-progress A2A task.

    Only tasks in 'submitted' or 'working' state can be canceled.

    Args:
        task_id: The task ID to cancel
    """
    tm = _get_task_manager()
    if tm.cancel_task(task_id):
        task = tm.get_task(task_id)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "canceled",
                "task_id": task_id,
                "task": task.to_dict() if task else None,
            }
        )
    else:
        return _error(f"Task '{task_id}' not found or already completed")


@mcp.tool()
def a2a_list_tasks(service: str = "", status: str = "", since: str = "", limit: int = 50) -> dict:
    """List A2A tasks with optional filters.

    Args:
        service: Filter by service name (empty returns all)
        status: Filter by status — submitted | working | completed | failed | canceled (empty returns all)
        since: ISO timestamp lower bound (e.g. '2026-05-01T00:00:00Z')
        limit: Max results (default 50)
    """
    tm = _get_task_manager()
    tasks = tm.list_tasks(service=service, status=status, since=since, limit=limit)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "tasks": [t.to_dict() for t in tasks],
            "count": len(tasks),
        }
    )


# ── State Transition tools (A2A-compatible) ───────────────────────────


@mcp.tool()
def get_state_transitions(service: str = "", since: str = "", limit: int = 50) -> dict:
    """Query state transition history for services.

    Tracks circuit breaker state changes, service registration, and
    service unregistration events. Use this to understand service
    lifecycle and failure patterns.

    Args:
        service: Filter by service name (empty returns all)
        since: ISO timestamp filter (e.g. '2026-05-01T00:00:00Z')
        limit: Max results (default 50)
    """
    transitions = registry.get_transitions(service=service, since=since, limit=limit)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "transitions": transitions,
            "count": len(transitions),
        }
    )


# ── Agent Card tools (A2A-compatible) ─────────────────────────────────


def _get_proxy_tools(service_name: str) -> list[dict]:
    """Collect proxy tool descriptions for a service.

    Returns list of tool dicts with name/description/inputSchema keys,
    or empty list if proxy manager is not initialized or has no matching tools.
    """
    if not _proxy_manager:
        return []
    tools = []
    for entry in _proxy_manager.registry.entries.values():
        if entry.service_name == service_name:
            tools.append(
                {
                    "name": entry.original_name,
                    "description": entry.description,
                    "inputSchema": entry.parameters,
                }
            )
    return tools


def _build_agent_card(service_name: str) -> tuple[dict | None, str | None]:
    """Build an A2A Agent Card dict for a registered service.

    Returns (card_dict, None) on success, or (None, error_message) on failure.
    """
    svc = registry.get(service_name)
    if not svc:
        return None, f"Service '{service_name}' not found"
    try:
        tools = _get_proxy_tools(service_name)
        tags = svc.tags if isinstance(svc.tags, list) else (svc.tags.split(",") if svc.tags else [])

        # Check if authentication is configured
        from agora.governance import KeyManager

        has_auth = KeyManager().has_keys()

        card = service_to_agent_card(
            name=svc.name,
            description=svc.description,
            protocol=svc.protocol,
            mcp_endpoint=svc.mcp_endpoint,
            port=svc.port,
            tags=tags,
            tools=tools if tools else None,
            has_auth=has_auth,
            has_push_notifications=_bus.has_push_subscribers(),
            has_state_transitions=bool(registry.get_transitions(limit=1)),
            provider_info={"organization": "Agora Hub"},
            documentation_url="https://github.com/starlink-awaken/agora",
        )
        return card.to_dict(), None
    except Exception as e:
        return None, str(e)



# ═══════════════════════════════════════════════════════════════
# Section 8: Agent Cards
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def list_agent_cards() -> dict:
    """List all registered Agent Cards — A2A-compatible agent metadata.

    Returns a mapping of service name → Agent Card for every registered
    service, including basic identity, capabilities, and skills.

    Use this tool when you (or another agent) need to discover what
    agents/services are available through the Agora hub.
    """
    services = registry.list_all()
    cards = {}
    for svc in services:
        card, err = _build_agent_card(svc.name)
        cards[svc.name] = card if card else {"error": err}

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "agent_cards": cards,
            "count": len(cards),
        }
    )


@mcp.tool()
def get_agent_card(name: str) -> dict:
    """Get the Agent Card for a specific service.

    Args:
        name: Service name (e.g., 'minerva', 'kos', 'sophia')

    Returns a single A2A-compatible Agent Card with identity, capabilities,
    and skills for the requested service.
    """
    card, err = _build_agent_card(name)
    if card is None:
        return _error(err or "Failed to build Agent Card")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "agent_card": card,
        }
    )


# ── MCP Registry tools (Phase 1) ────────────────────────────────────



# ═══════════════════════════════════════════════════════════════
# Section 9: Repository/Registry Tools
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def repo_search(query: str = "", source: str = "local", limit: int = 20) -> dict:
    """Search the tool catalog (local) or external sources (GitHub/registry).

    Args:
        query: Search keyword (empty = list all)
        source: 'local' (catalog), 'external' (GitHub+registry), or 'all'
        limit: Max results (default 20)
    """
    try:
        catalog = ToolCatalog()
        try:
            if source == "external":
                from agora.mcp_registry.sources import search_all  # type: ignore[import-not-found]

                results = await search_all(query or "mcp-server")
                results = results[:limit]
            elif source == "all":
                from agora.mcp_registry.sources import search_all

                local = catalog.search_tools(query, limit=limit)
                ext = await search_all(query or "mcp-server")
                merged = local + ext
                seen = set()
                results = []
                for t in merged:
                    tid = t.get("id") or t.get("name", "")
                    if tid not in seen:
                        seen.add(tid)
                        results.append(t)
                results = results[:limit]
            else:
                results = catalog.search_tools(query, limit=limit)
            return _ok({"format_version": FORMAT_VERSION, "tools": results, "count": len(results)})
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_search_error")
        return _error(f"Search failed: {e}")


@mcp.tool()
async def repo_discover(query: str = "mcp-server") -> dict:
    """Discover MCP tools from external sources (GitHub + registry) and save to local catalog.

    Args:
        query: Search query passed to external sources
    """
    try:
        catalog = ToolCatalog()
        try:
            orchestrator = _build_registry_orchestrator(catalog)
            results = await orchestrator.discover_and_save(query)
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "discovered": len(results),
                    "tools": results,
                }
            )
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_discover_error")
        return _error(f"Discovery failed: {e}")


@mcp.tool()
async def repo_status() -> dict:
    """Show tool catalog status — counts by status and list of all tools."""
    try:
        catalog = ToolCatalog()
        try:
            counts = catalog.count_by_status()
            tools = catalog.list_tools()
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "total": sum(counts.values()),
                    "by_status": counts,
                    "tools": tools,
                }
            )
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_status_error")
        return _error(f"Status check failed: {e}")


@mcp.tool()
async def repo_install(name: str) -> dict:
    """Mark a discovered tool as installed (Phase 2: status update via orchestrator).

    Args:
        name: Tool name or ID to install
    """
    try:
        catalog = ToolCatalog()
        try:
            orchestrator = _build_registry_orchestrator(catalog)
            ok, msg = await orchestrator.install_tool(name)
            if ok:
                return _ok(
                    {
                        "format_version": FORMAT_VERSION,
                        "action": "installed" if "installed" in msg else "already_installed",
                        "name": name,
                        "msg": msg,
                    }
                )
            return _error(msg or f"Install failed for '{name}'")
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_install_error")
        return _error(f"Install failed: {e}")


@mcp.tool()
async def repo_load(name: str) -> dict:
    """Load a tool via the LifecycleManager with proxy integration.

    Transitions tool from idle/installed to loaded status and connects
    to the downstream MCP service through the proxy.

    Args:
        name: Tool name or ID to load
    """
    try:
        catalog = ToolCatalog()
        try:
            orchestrator = _build_registry_orchestrator(catalog)
            ok, msg = await orchestrator.load_tool(name)
            if ok:
                return _ok(
                    {
                        "format_version": FORMAT_VERSION,
                        "action": "loaded",
                        "name": name,
                        "msg": msg,
                    }
                )
            return _error(msg or f"Failed to load tool '{name}'")
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_load_error")
        return _error(f"Load failed: {e}")


@mcp.tool()
async def repo_unload(name: str) -> dict:
    """Unload a tool via the LifecycleManager.

    Transitions tool from loaded to idle status and disconnects
    from the downstream MCP service.

    Args:
        name: Tool name or ID to unload
    """
    try:
        catalog = ToolCatalog()
        try:
            orchestrator = _build_registry_orchestrator(catalog)
            ok, msg = await orchestrator.unload_tool(name)
            if ok:
                return _ok(
                    {
                        "format_version": FORMAT_VERSION,
                        "action": "unloaded",
                        "name": name,
                        "msg": msg,
                    }
                )
            return _error(msg or f"Failed to unload tool '{name}'")
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_unload_error")
        return _error(f"Unload failed: {e}")


@mcp.tool()
async def repo_pipeline(query: str = "mcp-server", auto_load: bool = True) -> dict:
    """Full discover → install → load pipeline (Phase 2).

    Discovers tools from external sources (GitHub + registry), evaluates
    quality, saves to local catalog, marks as installed, and optionally
    loads them via LifecycleManager/proxy.

    Args:
        query: Search query passed to external sources (default: "mcp-server")
        auto_load: If True, automatically load newly discovered tools (default: True)
    """
    try:
        catalog = ToolCatalog()
        try:
            orchestrator = _build_registry_orchestrator(catalog)
            result = await orchestrator.discover_install_load(
                query=query,
                auto_load=auto_load,
            )
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "discovered": result["discovered"],
                    "installed": result["installed"],
                    "loaded": result["loaded"],
                }
            )
        finally:
            catalog.close()
    except Exception as e:
        logger.exception("repo_pipeline_error")
        return _error(f"Pipeline failed: {e}")


def _build_registry_orchestrator(catalog: ToolCatalog) -> Orchestrator:
    """Build an Orchestrator, reusing the singleton LifecycleManager when available.

    The singleton lifecycle manager (created by :func:`_get_lifecycle_manager`)
    owns the background watch tasks. This ensures ``lifecycle_start_watch`` and
    ``lifecycle_stop_watch`` operate on the same instance.
    """
    lm = _get_lifecycle_manager()
    return Orchestrator(catalog, lifecycle=lm)


# ── Lifecycle Management tools (Phase 2) ──────────────────────────────



# ═══════════════════════════════════════════════════════════════
# Section 10: Lifecycle Tools
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def lifecycle_status() -> dict:
    """Show current lifecycle manager status — loaded tools, idle watch state."""
    lm = _get_lifecycle_manager()
    if lm is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    loaded = []
    for tool_id, last_used in lm._last_used.items():
        tool = lm._catalog.get_tool(tool_id)
        loaded.append(
            {
                "id": tool_id,
                "name": tool.get("name", tool_id) if tool else tool_id,
                "last_used": last_used,
                "idle_for_seconds": round(time.time() - last_used, 1) if last_used else 0,
            }
        )

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "watch_running": lm._idle_watch_task is not None and not lm._idle_watch_task.done(),
            "idle_timeout": lm._idle_timeout,
            "check_interval": lm._check_interval,
            "loaded_count": len(loaded),
            "loaded_tools": loaded,
        }
    )


@mcp.tool()
async def lifecycle_start_watch(idle_timeout: int = 300, check_interval: int = 60) -> dict:
    """Start the idle timeout background watcher.

    Automatically unloads tools that have not been used for longer than
    the configured idle timeout period.

    Args:
        idle_timeout: Seconds of inactivity before auto-unload (default: 300)
        check_interval: Seconds between idle checks (default: 60)
    """
    lm = _get_lifecycle_manager()
    if lm is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    lm._idle_timeout = float(idle_timeout)
    lm._check_interval = float(check_interval)
    try:
        await lm.start_idle_watch()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "watch_started",
                "idle_timeout": idle_timeout,
                "check_interval": check_interval,
            }
        )
    except Exception as e:
        logger.exception("lifecycle_start_watch_error")
        return _error(f"Failed to start watch: {e}")


@mcp.tool()
async def lifecycle_stop_watch() -> dict:
    """Stop the idle timeout background watcher.

    Loaded tools will remain loaded until explicitly unloaded.
    """
    lm = _get_lifecycle_manager()
    if lm is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    try:
        await lm.stop_idle_watch()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "watch_stopped",
            }
        )
    except Exception as e:
        logger.exception("lifecycle_stop_watch_error")
        return _error(f"Failed to stop watch: {e}")


@mcp.tool()
async def lifecycle_load_all() -> dict:
    """Load all idle tools into the proxy.

    Loads every tool with 'idle' status, connecting each downstream MCP
    service for runtime use.
    """
    lm = _get_lifecycle_manager()
    if lm is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    try:
        count = await lm.load_by_status("idle")
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "loaded_idle",
                "count": count,
            }
        )
    except Exception as e:
        logger.exception("lifecycle_load_all_error")
        return _error(f"Load all failed: {e}")


@mcp.tool()
async def lifecycle_unload_all() -> dict:
    """Unload all currently loaded tools from the proxy.

    Disconnects every loaded downstream service and transitions
    status back to 'idle'.
    """
    lm = _get_lifecycle_manager()
    if lm is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    try:
        count = await lm.unload_by_status("loaded")
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "unloaded_loaded",
                "count": count,
            }
        )
    except Exception as e:
        logger.exception("lifecycle_unload_all_error")
        return _error(f"Unload all failed: {e}")



# ═══════════════════════════════════════════════════════════════
# Section 11: Execution Engine
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# Section: BOS URI 统一入口 (P45 W1)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
@bos_metrics.track("bos://")
async def resolve_bos_uri(uri: str, arguments: str = "{}") -> dict:
    """将 BOS URI 解析为实际调用，路由到对应的后端服务。
    
    支持 bos://memory/* bos://omo/* bos://analysis/* bos://persona/* bos://forge/*
    
    Args:
        uri: BOS URI (e.g. bos://memory/kos/search)
        arguments: JSON 参数字符串 (e.g. '{"query": "什么是 eCOS?"}')
    """
    import json
    if not uri.startswith("bos://"):
        return _error(f"Invalid BOS URI: {uri}")

    # P45 W3 T13: BOS 域级别鉴权
    if not _bos_domain_authorized(uri, "read"):
        return _error(f"Access denied to domain: {uri}")

    # P46 W0: 限流检查
    if not bos_rate_limiter.acquire(uri):
        return _error(f"Rate limit exceeded for: {uri}")

    # P46 W0: 熔断检查
    if bos_circuit_breaker.is_open(uri):
        return _error(f"Circuit breaker open for: {uri}")

    # P45 W3 T14: L0 审计
    ok, reason = _bos_pre_check(uri)

    import json
    import time as _time
    _t0 = _time.time()
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        result, source = await _resolve_with_router(uri, **args)
        bos_circuit_breaker.record_success(uri)
        _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
        _publish_bos_event(uri, "resolve", "ok", int((_time.time() - _t0) * 1000))
        return _ok({"format_version": FORMAT_VERSION, "uri": uri, "source": source, "result": result})
    except json.JSONDecodeError:
        return _error(f"Invalid JSON arguments: {arguments}")
    except Exception as e:
        bos_circuit_breaker.record_failure(uri)
        _bos_post_audit(uri, 500, int((_time.time() - _t0) * 1000))
        _publish_bos_event(uri, "resolve", "error", int((_time.time() - _t0) * 1000))
        logger.exception("resolve_bos_uri_failed", uri=uri)
        return _error(f"BOS URI resolve failed: {e}")


@mcp.tool()
@bos_metrics.track("bos://")
async def read_resource(uri: str, params: str = "{}") -> dict:
    """通过 BOS URI 读取资源。先尝试 ProxyManager (MCP 下游)，回退到 bos_resolver。

    Args:
        uri: BOS URI (e.g. bos://memory/kos/search)
        params: JSON 参数字符串 (e.g. '{"query": "..."}')
    """
    import json
    if not uri.startswith("bos://"):
        return _error(f"Invalid BOS URI: {uri}")

    # P45 W3 T13: BOS 域级别鉴权
    if not _bos_domain_authorized(uri, "read"):
        return _error(f"Access denied to domain: {uri}")

    # P46 W0: 限流检查
    if not bos_rate_limiter.acquire(uri):
        return _error(f"Rate limit exceeded for: {uri}")

    # P46 W0: 缓存查询 (读操作)
    try:
        args = json.loads(params) if isinstance(params, str) else params
    except json.JSONDecodeError:
        return _error(f"Invalid JSON params: {params}")
    cached = bos_cache.get(uri, args)
    if cached:
        return _ok({"format_version": FORMAT_VERSION, "uri": uri, "source": "cache", "result": cached})

    # P45 W3 T14: L0 审计
    import time as _time
    _t0 = _time.time()
    # Step 1: BOSRouter → POC_SERVICES 统一路由链
    try:
        result, source = await _resolve_with_router(uri, **args)
        # 如果结果不是 error 状态，且没有进一步尝试 ProxyManager 的必要
        if isinstance(result, dict) and result.get("status") != "error":
            bos_cache.set(uri, args, result, ttl=30)
            bos_circuit_breaker.record_success(uri)
            _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
            _publish_bos_event(uri, "read", "ok", int((_time.time() - _t0) * 1000))
            return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                       "source": source, "result": result})
    except Exception:
        pass

    # Step 2: 尝试 ProxyManager (MCP 下游代理)
    if _proxy_manager is not None:
        try:
            result = await _proxy_manager.read_resource(uri)
            if isinstance(result, dict) and "contents" in result:
                bos_cache.set(uri, args, result["contents"], ttl=30)
                bos_circuit_breaker.record_success(uri)
                _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
                _publish_bos_event(uri, "read", "ok", int((_time.time() - _t0) * 1000))
                return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                           "source": "proxy", "contents": result["contents"]})
        except Exception:
            pass
    # Step 2: 回退到 bos_resolver (POC_SERVICES 子进程)
    try:
        result = await _resolve_bos_uri(uri, **args)
        bos_cache.set(uri, args, result, ttl=30)
        bos_circuit_breaker.record_success(uri)
        _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
        _publish_bos_event(uri, "read", "ok", int((_time.time() - _t0) * 1000))
        return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                   "source": "bos_resolver", "result": result})
    except Exception as e:
        bos_circuit_breaker.record_failure(uri)
        _bos_post_audit(uri, 500, int((_time.time() - _t0) * 1000))
        _publish_bos_event(uri, "read", "error", int((_time.time() - _t0) * 1000))
        logger.exception("read_resource_failed", uri=uri)
        return _error(f"Resource read failed: {e}")


@mcp.tool()
async def list_bos_resources(prefix: str = "") -> dict:
    """列出所有可用的 BOS 资源。合并 POC_SERVICES + ProxyManager。

    Args:
        prefix: URI 前缀过滤 (可选，如 bos://memory/)
    """
    resources = []
    # Part A: BOSRouter routes
    for route in _bos_router.list_all(prefix_filter=prefix):
        uri = route["prefix"].rstrip("/")
        config = route.get("config", {})
        resources.append({
            "uri": uri,
            "domain": config.get("domain", uri.split("/")[2] if "/" in uri else "unknown"),
            "source": "bos_router",
            "adapter": route["adapter"],
            "description": config.get("description", config.get("workflow", f"BOSRouter: {route['adapter']}")),
            "schema_available": bool(config.get("steps", 0) or config.get("workflow")),
        })
    # Part B: POC services (legacy, 部分已由 BOSRouter 覆盖)
    for svc in _list_poc_services():
        uri = svc.get("uri", "")
        # 去重：BOSRouter 已包含的跳过
        if any(r["uri"] == uri for r in resources):
            continue
        resources.append({
            "uri": uri,
            "domain": svc.get("domain", ""),
            "source": "poc",
            "transport": svc.get("transport", ""),
            "description": svc.get("description", ""),
            "schema_available": False,
        })
    # Part C: ProxyManager configs
    if _proxy_manager is not None:
        for name, config in getattr(_proxy_manager, '_configs', {}).items():
            if isinstance(config, dict):
                for bos_prefix in config.get("bos_prefixes", []):
                    resources.append({
                        "uri": bos_prefix,
                        "domain": bos_prefix.split("/")[2] if "/" in bos_prefix else "unknown",
                        "source": "proxy",
                        "transport": "mcp_proxy",
                        "description": config.get("description", f"Proxy: {name}"),
                    })
    if prefix:
        resources = [r for r in resources if r["uri"].startswith(prefix)]

    # 附上 schema 信息: 标注哪些 URI 有已知 schema
    try:
        wf_dir = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "workflow"
        if wf_dir.exists():
            import yaml
            known_actions = set()
            for f in wf_dir.glob("WORKFLOW-*.yaml"):
                node = yaml.safe_load(open(f))
                if node and node.get("type") == "Workflow":
                    for step in node.get("steps", []):
                        if step.get("action"):
                            known_actions.add(step["action"])
            for r in resources:
                uri = r["uri"]
                # Check if URI matches any known action
                parts = uri.replace("bos://", "").split("/")
                if len(parts) >= 3:
                    pkg_action = f"{parts[1]}.{parts[2]}"
                    r["schema_available"] = pkg_action in known_actions
                else:
                    r["schema_available"] = False
    except Exception:
        pass

    return _ok({"format_version": FORMAT_VERSION, "resources": resources, "total": len(resources)})


@mcp.tool()
async def list_bos_domains() -> dict:
    """列出所有已注册的 BOS 域及其路由摘要。"""
    from collections import Counter
    doms = Counter()
    # POC services
    for svc in _list_poc_services():
        doms[svc.get("domain", "unknown")] += 1
    # BOSRouter routes (补充不在 POC 中的域)
    bos_domains = set()
    for route in _bos_router.list_all():
        config = route.get("config", {})
        d = config.get("domain", "")
        if d:
            bos_domains.add(d)
    for d in bos_domains:
        if d not in doms:
            doms[d] = sum(1 for r in _bos_router.list_all()
                          if r.get("config", {}).get("domain") == d)
    return _ok({"format_version": FORMAT_VERSION, "domains": dict(doms),
               "description": "BOS URI 5+1+扩展域: memory/omo/analysis/persona/forge + M1 扩展",
               "total_routes": _bos_router.count()})

# ═══════════════════════════════════════════════════════════════
# BOS 鉴权 (P45 W3 T13)
# ═══════════════════════════════════════════════════════════════

_BOS_DOMAIN_ACCESS = {
    # 默认所有域允许，可配置为 {domain: [scopes]}
    "memory":    ["read", "write"],
    "omo":       ["read", "write"],
    "analysis":  ["read", "write"],
    "persona":   ["read", "write"],
    "forge":     ["read", "write"],
    "meta":      ["read"],
    "ecos":      ["read"],
    "agora":     ["read"],
}

def _bos_domain_authorized(uri: str, operation: str = "read") -> bool:
    """检查 BOS URI 的域级别权限。"""
    if not _AGORA_API_KEY:
        return True  # 本地开发模式
    domain = uri.split("/")[2] if uri.startswith("bos://") and "/" in uri else ""
    allowed = _BOS_DOMAIN_ACCESS.get(domain, [])
    return operation in allowed

# ═══════════════════════════════════════════════════════════════
# BOS Schema (P45 W3 T15)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_bos_schema(uri: str = "") -> dict:
    """获取 BOS URI 的参数规范。从 M1 Workflow 节点的 steps 读取。

    Args:
        uri: BOS URI 或 action 名称 (如 bos://analysis/minerva/research 或 minerva.research)
             不传则返回所有已知 schema 摘要
    """
    import yaml
    try:
        wf_dir = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "workflow"
        if not wf_dir.exists():
            return _error("M1 Workflow 目录不存在")

        schemas = {}
        for f in sorted(wf_dir.glob("WORKFLOW-*.yaml")):
            try:
                node = yaml.safe_load(open(f))
                if not node or node.get("type") != "Workflow":
                    continue
                for step in node.get("steps", []):
                    action = step.get("action", "")
                    if not action:
                        continue
                    schemas[action] = {
                        "workflow": node.get("name", ""),
                        "action": action,
                        "description": step.get("description", ""),
                        "order": step.get("order"),
                        "input": step.get("input", {}),
                        "output": step.get("output", {}),
                        "sla": node.get("sla", {}),
                        "domain": node.get("domain", ""),
                        "layer": node.get("layer", ""),
                    }
            except Exception:
                pass

        if uri:
            # 匹配: 直接 action 名 或 从 URI 中提取
            action_key = uri
            if uri.startswith("bos://"):
                parts = uri.replace("bos://", "").split("/")
                # 尝试匹配 package.action 格式
                if len(parts) >= 3:
                    action_key = f"{parts[1]}.{parts[2]}"
            if action_key in schemas:
                return _ok({"format_version": FORMAT_VERSION, "uri": uri, "schema": schemas[action_key]})
            # 部分匹配
            matches = {k: v for k, v in schemas.items() if action_key in k}
            if matches:
                return _ok({"format_version": FORMAT_VERSION, "uri": uri, "schemas": matches, "match_count": len(matches)})
            return _error(f"No schema found for: {uri}. Use get_bos_schema() without args to list all.")

        return _ok({"format_version": FORMAT_VERSION, "total_schemas": len(schemas),
                   "schemas": schemas, "hint": "Use get_bos_schema('minerva.research') for specific"})
    except Exception as e:
        return _error(f"Schema lookup failed: {e}")

# ═══════════════════════════════════════════════════════════════
# BOS 可观测性 (P46 W0)
@mcp.tool()
async def bos_middleware_status() -> dict:
    """BOS 中间件状态查询 — 限流/熔断/缓存实时状态。"""
    return _ok({
        "format_version": FORMAT_VERSION,
        "rate_limiter": bos_rate_limiter.status(),
        "circuit_breaker": {"open_circuits": bos_circuit_breaker.status()},
        "cache": bos_cache.status(),
        "router": {"total_routes": _bos_router.count(), "stats": _bos_router.stats()},
    })


# ═══════════════════════════════════════════════════════════════
# BOS 可观测性 (P46 W2)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def bos_metrics_status(prefix: str = "", format: str = "json") -> dict | str:
    """BOS 调用指标 — 支持 JSON 和 Prometheus 两种格式。

    Args:
        prefix: URI 前缀过滤
        format: "json" (默认) 或 "prometheus" (Prometheus scrape)
    """
    if format == "prometheus":
        lines = []
        status = bos_metrics.status(prefix)
        for p, s in sorted(status.items()):
            labels = p.replace("://", "_").replace("/", "_").replace("-", "_")
            lines.append(f"# HELP bos_calls_total Total BOS calls per prefix")
            lines.append(f"# TYPE bos_calls_total counter")
            lines.append(f'bos_calls_total{{prefix="{p}"}} {s["calls"]}')
            lines.append(f"# HELP bos_success_rate BOS success rate per prefix")
            lines.append(f"# TYPE bos_success_rate gauge")
            lines.append(f'bos_success_rate{{prefix="{p}"}} {s["success_rate"]}')
            lines.append(f"# HELP bos_latency_ms_avg Average latency per prefix")
            lines.append(f"# TYPE bos_latency_ms_avg gauge")
            lines.append(f'bos_latency_ms_avg{{prefix="{p}"}} {s["avg_latency_ms"]}')
        return "\n".join(lines) + "\n"
    if prefix:
        return _ok({"format_version": FORMAT_VERSION, "metrics": bos_metrics.status(prefix)})
    return _ok({
        "format_version": FORMAT_VERSION,
        "summary": bos_metrics.summary(),
        "detail": bos_metrics.status(),
    })


# BOS 事件订阅 (watch_resource)

def _bos_uri_to_event_type(uri: str) -> str:
    """将 bos:// URI 转换为事件类型。

    bos://memory/kos/search → bos:memory:kos:search
    bos://memory/kos/*     → bos:memory:kos:*
    """
    return uri.replace("://", ":").replace("/", ":")


def _publish_bos_event(uri: str, operation: str, status: str = "ok",
                       duration_ms: int = 0) -> None:
    """发布 BOS URI 操作事件到总线。"""
    event_type = _bos_uri_to_event_type(uri)
    _bus.publish(event_type, {
        "uri": uri,
        "operation": operation,
        "status": status,
        "duration_ms": duration_ms,
    }, source="bos")


@mcp.tool()
async def watch_resource(uri_pattern: str, callback_url: str = "") -> dict:
    """监听 BOS URI 的变化事件。

    当指定的 bos:// URI 被解析、读取或变更时，通过事件总线通知。
    支持通配符: bos://memory/kos/* (监听所有 kos 操作)

    Args:
        uri_pattern: BOS URI 模式 (e.g. bos://memory/kos/search 或 bos://memory/kos/*)
        callback_url: 可选 HTTP 回调 URL，事件发生时 POST 通知

    Returns:
        包含 subscription_id 的响应
    """
    if not uri_pattern.startswith("bos://"):
        return _error(f"Invalid BOS URI pattern: {uri_pattern}")

    event_pattern = _bos_uri_to_event_type(uri_pattern)

    bus = _bus
    sub_id = bus.subscribe("bos-watch", event_pattern, callback_url)

    logger.info("watch_resource_registered", uri_pattern=uri_pattern,
                event_pattern=event_pattern, sub_id=sub_id)

    return _ok({
        "format_version": FORMAT_VERSION,
        "action": "watching",
        "uri_pattern": uri_pattern,
        "event_pattern": event_pattern,
        "subscription_id": sub_id,
        "hint": "Use get_event_log() to poll events, or provide callback_url for push delivery",
    })


@mcp.tool()
def unwatch_resource(subscription_id: str) -> dict:
    """取消 BOS URI 事件监听。

    Args:
        subscription_id: watch_resource 返回的订阅 ID
    """
    bus = _bus
    bus.unsubscribe(subscription_id)
    logger.info("watch_resource_unregistered", sub_id=subscription_id)
    return _ok({
        "format_version": FORMAT_VERSION,
        "action": "unwatched",
        "subscription_id": subscription_id,
    })



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
        router = _get_cached_router()
        result = await router.route(query, mode=mode)
        return _ok({"format_version": FORMAT_VERSION, **result})
    except Exception as e:
        logger.exception("agora_execute_failed", query=query, mode=mode)
        return _error(f"Execution failed: {e}")


def main():
    """Start the Agora MCP server in stdio mode with proxy initialization.

    Auto-discovers and launches downstream MCP services via bootstrap when
    no explicit proxy config is available. Proxy initialization runs inside
    FastMCP's lifespan context manager to keep subprocesses alive.
    """
    sys.stderr.write("Agora MCP Server (stdio) starting...\n")
    mcp.run()


def http_main():
    """Start the Agora MCP server in HTTP mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    """
    import asyncio

    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=7422))


def sse_main():
    """Start the Agora MCP server in SSE mode with proxy initialization.

    Proxy connections are initialized inside the lifespan context manager,
    keeping subprocesses alive for the entire server lifetime.
    """
    import asyncio

    sys.stderr.write("Agora MCP Server (SSE) starting on port 7431...\n")
    asyncio.run(mcp.run_http_async(transport="sse", host="0.0.0.0", port=7431))


if __name__ == "__main__":
    sse_main()
