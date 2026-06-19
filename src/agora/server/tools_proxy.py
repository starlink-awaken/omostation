"""Proxy management/forwarding MCP tools — extracted from server/mcp.py (God Module Phase 1).

Provides tools for managing downstream MCP service connections through the proxy layer:
connect, call, status, list, add, remove.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import ClassVar

import structlog
from fastmcp import FastMCP
from fastmcp.tools import Tool, ToolResult

from agora.core.service_base import is_safe_url  # type: ignore[import-not-found]
from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]
from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)

# ── Module globals — these are set by the parent mcp.py init flow ──────
_PROXY_CONFIG_PATH: Path | None = None
_FORGE_REGISTRY_PATH: Path | None = None


def _set_constants(proxy_config_path: Path, forge_registry_path: Path) -> None:
    """Set shared paths from the parent mcp.py module at init time."""
    global _PROXY_CONFIG_PATH, _FORGE_REGISTRY_PATH
    _PROXY_CONFIG_PATH = proxy_config_path
    _FORGE_REGISTRY_PATH = forge_registry_path


def _get_proxy_manager() -> ProxyManager | None:
    """Lazy-import ProxyManager singleton from dependencies.py."""
    from agora.server.dependencies import get_proxy_manager  # type: ignore[import-not-found]
    return get_proxy_manager()


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
    if _PROXY_CONFIG_PATH and _PROXY_CONFIG_PATH.exists():
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
    if not _FORGE_REGISTRY_PATH or not _FORGE_REGISTRY_PATH.exists():
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
        cfg: dict = {
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


def _save_proxy_service(svc: dict) -> None:
    """Append a service config to the proxy services file."""
    from agora.persistence import json_save

    existing = _load_proxy_services()
    # Replace if exists, else append
    existing = [s for s in existing if s.get("name") != svc.get("name")]
    existing.append(svc)
    json_save(_PROXY_CONFIG_PATH, existing)




class ProxyForwardTool(Tool):
    """FastMCP Tool that forwards calls directly to the proxy dispatch.

    Unlike FunctionTool, this bypasses argument type validation (which cannot
    handle dynamic downstream JSON Schemas), allowing any downstream service's
    tools to be exposed as native FastMCP tools.
    """

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
            return self.convert_result(
                {"status": "error", "error": f"Proxy call failed: {str(e)[:200]}"}
            )

_registered_proxy_tools: set[str] = set()

def _register_proxy_tools(mcp_server: FastMCP, pm: ProxyManager):
    ProxyForwardTool._pm = pm

    for entry in pm.registry.entries.values():
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
    for entry in pm.registry.entries.values():
        if entry.tool_name in _registered_proxy_tools:
            try:
                mcp_server.remove_tool(entry.tool_name)
            except Exception:
                pass
            _registered_proxy_tools.discard(entry.tool_name)

async def proxy_sync_loop(registry_ref):
    """Background task: periodically sync ServiceRegistry -> ProxyRegistry.
    Uses exponential backoff: starts at 10 seconds, doubles up to 120 seconds.
    """
    backoff = 10
    while True:
        await asyncio.sleep(backoff)
        pm = _get_proxy_manager()
        if pm is None:
            backoff = min(backoff * 2, 120)
            continue
        try:
            proxy_configs = _load_proxy_services()
            await pm.registry.register_from_registry(
                registry_ref, proxy_configs
            )
            backoff = 10  # reset on success
        except Exception:
            logger.exception("proxy_sync_loop_error")
            backoff = min(backoff * 2, 120)

# ═══════════════════════════════════════════════════════════════
# Module-level Tool Functions
# ═══════════════════════════════════════════════════════════════


async def proxy_call(tool_name: str, arguments: str = "{}") -> dict:
    """Call a downstream service tool through the MCP proxy.

    The proxy connects to registered downstream MCP services (via stdio or HTTP)
    and forwards tool calls. Supports both exact and prefix tool name matching.

    Args:
        tool_name: Full tool name (e.g. 'kos.semantic_search', 'minerva.research_now')
        arguments: JSON string of tool arguments
    """
    pm = _get_proxy_manager()
    if pm is None:
        return _error("Proxy not initialized. Call proxy_connect first.")

    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}

    # L0 前置校验 — lazy import from ecos hook
    from ecos.ssot.tools.mof_agora_hook import (  # type: ignore[import-not-found]
        post_audit as _bos_post_audit,
        pre_check as _bos_pre_check,
    )

    _bos_uri = f"bos://agora/tools/{tool_name}"
    _ok_check, _reason = _bos_pre_check(_bos_uri)
    if not _ok_check:
        logger.warning("bos_pre_check_blocked", uri=_bos_uri, reason=_reason)
        return _error(_reason)

    _t0 = __import__("time").time()
    try:
        result = await pm.dispatch(tool_name, args)
        _bos_post_audit(_bos_uri, 200, int((__import__("time").time() - _t0) * 1000))
        return _ok({"format_version": FORMAT_VERSION, **result})
    except ValueError as e:
        _bos_post_audit(_bos_uri, 400, int((__import__("time").time() - _t0) * 1000))
        return _error(str(e))
    except Exception as e:
        _bos_post_audit(_bos_uri, 500, int((__import__("time").time() - _t0) * 1000))
        return _error(f"Proxy call failed: {str(e)[:200]}")


async def proxy_status() -> dict:
    """Show current proxy connection status and available tools."""
    pm = _get_proxy_manager()
    if pm is None:
        return _error("Proxy not initialized")

    status = pm.status()
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "data": status,
        }
    )


async def proxy_remove_service(name: str) -> dict:
    """Disconnect and remove a downstream service from the proxy."""
    pm = _get_proxy_manager()
    if pm is None:
        return _error("Proxy not initialized")

    await pm.remove_service(name)

    from agora.server.mcp import _bus

    _bus.publish("registry:service.removed", {"name": name}, source="agora.server.mcp")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "removed",
            "service": name,
        }
    )


# ═══════════════════════════════════════════════════════════════
# Tool Registration
# ═══════════════════════════════════════════════════════════════


def register_proxy_tools(mcp: FastMCP) -> None:
    """Register all proxy management/forwarding tools with the MCP instance."""

    # ── proxy_connect ──────────────────────────────────────────────

    @mcp.tool()
    async def proxy_connect() -> dict:
        """Connect to all configured downstream MCP services via the proxy.

        Reads from agora-proxy-services.json for service definitions.
        Returns connection results for each service.
        """
        pm = _get_proxy_manager()
        if pm is None:
            from agora.server.dependencies import set_proxy_manager
            from agora.mcp_proxy.manager import ProxyManager
            pm = ProxyManager()
            set_proxy_manager(pm)

        services = _load_proxy_services()
        if not services:
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "warning": "No proxy services configured in agora-proxy-services.json",
                }
            )

        results = await pm.start(services)

        # Register downstream proxy tools as native FastMCP tools
        from agora.server.mcp import _register_proxy_tools as _rpt

        _rpt(mcp, pm)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "services": results,
            }
        )

    # ── proxy_call ──────────────────────────────────────────────────

    mcp.tool()(proxy_call)

    # ── proxy_status ────────────────────────────────────────────────

    mcp.tool()(proxy_status)

    # ── proxy_list_tools ────────────────────────────────────────────

    @mcp.tool()
    async def proxy_list_tools() -> dict:
        """List all available downstream proxy tools with full schemas.

        Returns a flat list of all currently registered proxy tools,
        each with name, description, and inputSchema compatible with
        standard MCP tool format.
        """
        pm = _get_proxy_manager()
        if pm is None:
            return _error("Proxy not initialized")

        tools = []
        for entry in pm.registry.entries.values():
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

    # ── proxy_add_service ───────────────────────────────────────────

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
        pm = _get_proxy_manager()
        if pm is None:
            from agora.server.dependencies import set_proxy_manager
            from agora.mcp_proxy.manager import ProxyManager
            pm = ProxyManager()
            set_proxy_manager(pm)

        svc: dict = {"name": name}
        if mcp_endpoint:
            svc["mcp_endpoint"] = mcp_endpoint
        if mcp_endpoint and not is_safe_url(mcp_endpoint):
            return _error(f"Unsafe endpoint URL: {mcp_endpoint}")
        if command:
            svc["command"] = command
        if args:
            svc["args"] = args.split()

        result = await pm.add_service(svc)
        return _ok({"format_version": FORMAT_VERSION, "action": result})

    # ── proxy_remove_service ────────────────────────────────────────

    mcp.tool()(proxy_remove_service)
