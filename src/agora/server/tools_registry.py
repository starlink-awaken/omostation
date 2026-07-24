"""MCP Registry/Inventory tools — extracted from server/mcp.py (God Module Phase 1).

Provides tools for service registration, routing, event bus, and
tool registry/repository management.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from fastmcp import FastMCP

from agora.core.service_base import (  # type: ignore[import-not-found]
    parse_protocol_config,
    parse_tags,
)
from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)


def _get_registry():
    """Lazy-import ServiceRegistry singleton from mcp.py."""
    from agora.server.mcp import registry as _registry  # type: ignore[import-not-found]

    return _registry


def _get_bus():
    """Lazy-import EventBus from mcp.py."""
    from agora.server.mcp import _bus  # type: ignore[import-not-found]

    return _bus


def _get_router():
    """Lazy-import Router from mcp.py."""
    from agora.server.mcp import router  # type: ignore[import-not-found]

    return router


def _get_proxy_manager():
    """Lazy-import ProxyManager from dependencies.py."""
    from agora.server.dependencies import get_proxy_manager

    return get_proxy_manager()


def _resolve_caller_identity(caller_identity: str | dict | None) -> str | dict:
    """Resolve caller identity from explicit argument or auth token."""
    from agora.server.mcp import (
        _resolve_caller_identity as _rci,  # type: ignore[import-not-found]
    )

    return _rci(caller_identity)


def _get_lifecycle_manager():
    """Lazy-import LifecycleManager from mcp.py."""
    from agora.server.mcp import (
        _get_lifecycle_manager as _glm,  # type: ignore[import-not-found]
    )

    return _glm()


def _get_cached_catalog():
    """Lazy-import cached ToolCatalog from mcp.py."""
    from agora.server.mcp import (
        _get_cached_catalog as _gcc,  # type: ignore[import-not-found]
    )

    return _gcc()


def _build_registry_orchestrator(catalog):
    """Build Orchestrator reusing the singleton LifecycleManager."""
    lm = _get_lifecycle_manager()
    from agora.mcp_registry.orchestrator import (
        Orchestrator,  # type: ignore[import-not-found]
    )

    return Orchestrator(catalog, lifecycle=lm)


def _load_proxy_services() -> list[dict]:
    """Lazy-import _load_proxy_services from tools_proxy.py."""
    # Import lazily to avoid circular dependency at module level.
    # This is called during register_service to sync proxy config.
    from agora.server.tools_proxy import (
        _load_proxy_services as _lps,  # type: ignore[import-not-found]
    )

    return _lps()


def _get_proxy_config_path() -> Path:
    """Get the proxy config path."""
    from agora.server.mcp import _PROXY_CONFIG_PATH  # type: ignore[import-not-found]

    return _PROXY_CONFIG_PATH


def _save_proxy_service(svc: dict) -> None:
    """Append a service config to the proxy services file."""
    from agora.server.tools_proxy import (
        _save_proxy_service as _sps,  # type: ignore[import-not-found]
    )

    _sps(svc)


# ═══════════════════════════════════════════════════════════════
# Module-level Tool Functions
# ═══════════════════════════════════════════════════════════════


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
    import json as _json

    from agora.core.registry import (  # type: ignore[import-not-found]
        Service,
        ServiceConfig,
    )

    registry = _get_registry()

    # Parse protocol_config from JSON string to dict
    if isinstance(protocol_config, str):
        try:
            config = _json.loads(protocol_config)
        except _json.JSONDecodeError as e:
            return {"status": "error", "error": f"Invalid protocol_config JSON: {e}"}
        if not isinstance(config, dict):
            return {"status": "error", "error": "protocol_config must be a JSON object"}
    elif isinstance(protocol_config, dict):
        config = protocol_config
    else:
        return {
            "status": "error",
            "error": f"protocol_config must be str or dict, got {type(protocol_config).__name__}",
        }

    cfg = ServiceConfig(
        name=name,
        description=description,
        protocol=protocol,
        protocol_config=config,
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
    pm = _get_proxy_manager()
    if pm and (cfg.mcp_endpoint.startswith("http") or cfg.command):
        proxy_svc: dict = {"name": cfg.name}
        if cfg.mcp_endpoint:
            proxy_svc["mcp_endpoint"] = cfg.mcp_endpoint
        if cfg.command:
            proxy_svc["command"] = cfg.command
            proxy_svc["args"] = cfg.mcp_args.split() if cfg.mcp_args else []
        proxy_result = await pm.add_service(proxy_svc)
        if proxy_result.startswith("error"):
            logger.warning(
                "register_service_proxy_add_failed",
                service=cfg.name,
                reason=proxy_result,
            )

    bus = _get_bus()
    bus.publish(
        "registry:service.registered",
        {"name": cfg.name},
        source="agora.server.mcp",
    )

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "registered",
            "name": name,
        }
    )


def list_services() -> dict:
    """List all registered services and their health status."""
    registry = _get_registry()
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": registry.to_dict(),
        }
    )


def add_route(tool_name: str, service_name: str) -> dict:
    """Map a tool name to a service for routing.

    Args:
        tool_name: The tool name (e.g. 'minerva.research_now' or just 'minerva' for prefix)
        service_name: The registered service name
    """
    if not tool_name.strip() or not service_name.strip():
        return _error("Tool name and service name required")

    router = _get_router()

    # L0 审计 — 路由变更事件
    from ecos.ssot.tools.mof_agora_hook import (
        post_audit as _bos_post_audit,  # type: ignore[import-not-found]
    )

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


def list_routes() -> dict:
    """List all tool → service route mappings."""
    router = _get_router()
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": router.list_routes(),
        }
    )


async def route_call(
    tool_name: str, arguments: str = "{}", caller_identity: str = ""
) -> dict:
    """Route a tool call to the appropriate service.

    Args:
        tool_name: The tool to call (e.g. 'minerva.research_now')
        arguments: JSON string of arguments
        caller_identity: Optional JSON string with structured caller identity
    """
    router = _get_router()
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


def publish_event(event_type: str, payload: str, source: str = "") -> dict:
    """Publish an event to the bus. payload is a JSON string.

    Args:
        event_type: Event type (e.g. 'index:done', 'registry:tools.updated')
        payload: JSON string with event data
        source: Source service name (e.g. 'kos', 'claude-code')
    """
    bus = _get_bus()
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


def subscribe_event(pattern: str, callback_url: str = "") -> dict:
    """Subscribe to events matching pattern.

    Args:
        pattern: Event pattern ('index:*', 'index:done', '*')
        callback_url: Optional HTTP callback URL for push delivery
    """
    bus = _get_bus()
    sub_id = bus.subscribe("mcp-caller", pattern, callback_url)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "subscription_id": sub_id,
            "pattern": pattern,
        }
    )


def get_event_log(limit: int = 50, since: str = "") -> dict:
    """Query historical events.

    Args:
        limit: Max events to return (default 50)
        since: ISO timestamp, only return events after this time
    """
    bus = _get_bus()
    events = bus.get_event_log(limit, since)
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": events,
        }
    )


async def repo_search(query: str = "", source: str = "local", limit: int = 20) -> dict:
    """Search the tool catalog (local) or external sources (GitHub/registry).

    Args:
        query: Search keyword (empty = list all)
        source: 'local' (catalog), 'external' (GitHub+registry), or 'all'
        limit: Max results (default 20)
    """
    try:
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

        catalog = ToolCatalog()
        try:
            if source == "external":
                from agora.mcp_registry.sources import (
                    search_all,  # type: ignore[import-not-found]
                )

                results = await search_all(query or "mcp-server")
                results = results[:limit]
            elif source == "all":
                from agora.mcp_registry.sources import (
                    search_all,  # type: ignore[import-not-found]
                )

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
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "tools": results,
                    "count": len(results),
                }
            )
        finally:
            catalog.close()
    except Exception as e:  # defensive fallback
        logger.exception("repo_search_error")
        return _error(f"Search failed: {e}")


async def repo_discover(query: str = "mcp-server") -> dict:
    """Discover MCP tools from external sources (GitHub + registry) and save to local catalog.

    Args:
        query: Search query passed to external sources
    """
    try:
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

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
    except Exception as e:  # defensive fallback
        logger.exception("repo_discover_error")
        return _error(f"Discovery failed: {e}")


async def repo_status() -> dict:
    """Show tool catalog status — counts by status and list of all tools."""
    try:
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

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
    except Exception as e:  # defensive fallback
        logger.exception("repo_status_error")
        return _error(f"Status check failed: {e}")


async def repo_install(name: str) -> dict:
    """Mark a discovered tool as installed (Phase 2: status update via orchestrator).

    Args:
        name: Tool name or ID to install
    """
    try:
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

        catalog = ToolCatalog()
        try:
            orchestrator = _build_registry_orchestrator(catalog)
            ok, msg = await orchestrator.install_tool(name)
            if ok:
                return _ok(
                    {
                        "format_version": FORMAT_VERSION,
                        "action": "installed"
                        if "installed" in msg
                        else "already_installed",
                        "name": name,
                        "msg": msg,
                    }
                )
            return _error(msg or f"Install failed for '{name}'")
        finally:
            catalog.close()
    except Exception as e:  # defensive fallback
        logger.exception("repo_install_error")
        return _error(f"Install failed: {e}")


async def repo_load(name: str) -> dict:
    """Load a tool via the LifecycleManager with proxy integration.

    Transitions tool from idle/installed to loaded status and connects
    to the downstream MCP service through the proxy.

    Args:
        name: Tool name or ID to load
    """
    try:
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

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
    except Exception as e:  # defensive fallback
        logger.exception("repo_load_error")
        return _error(f"Load failed: {e}")


async def repo_unload(name: str) -> dict:
    """Unload a tool via the LifecycleManager.

    Transitions tool from loaded to idle status and disconnects
    from the downstream MCP service.

    Args:
        name: Tool name or ID to unload
    """
    try:
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

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
    except Exception as e:  # defensive fallback
        logger.exception("repo_unload_error")
        return _error(f"Unload failed: {e}")


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
        from agora.mcp_registry.repository import (
            ToolCatalog,  # type: ignore[import-not-found]
        )

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
    except Exception as e:  # defensive fallback
        logger.exception("repo_pipeline_error")
        return _error(f"Pipeline failed: {e}")


# ═══════════════════════════════════════════════════════════════
# Tool Registration — register all tools with the MCP instance
# ═══════════════════════════════════════════════════════════════


def register_registry_tools(mcp: FastMCP) -> None:
    """Register all registry/inventory MCP tools."""
    mcp.tool(name="register_service")(register_service)
    mcp.tool(name="list_services")(list_services)
    mcp.tool(name="add_route")(add_route)
    mcp.tool(name="list_routes")(list_routes)
    mcp.tool(name="route_call")(route_call)
    mcp.tool(name="publish_event")(publish_event)
    mcp.tool(name="subscribe_event")(subscribe_event)
    mcp.tool(name="get_event_log")(get_event_log)
    mcp.tool(name="repo_search")(repo_search)
    mcp.tool(name="repo_discover")(repo_discover)
    mcp.tool(name="repo_status")(repo_status)
    mcp.tool(name="repo_install")(repo_install)
    mcp.tool(name="repo_load")(repo_load)
    mcp.tool(name="repo_unload")(repo_unload)
    mcp.tool(name="repo_pipeline")(repo_pipeline)
