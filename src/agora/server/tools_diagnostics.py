"""Health/status/diagnostics MCP tools — extracted from server/mcp.py (God Module Phase 1).

Provides tools for health checks, state transitions, and lifecycle management.
"""

from __future__ import annotations

import time

import structlog
from fastmcp import FastMCP

from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)


def _get_registry():
    """Lazy-import ServiceRegistry from mcp.py."""
    from agora.server.mcp import registry  # type: ignore[import-not-found]

    return registry


def _get_lifecycle_manager():
    """Lazy-import LifecycleManager from mcp.py."""
    from agora.server.mcp import (
        _get_lifecycle_manager as _glm,  # type: ignore[import-not-found]
    )

    return _glm()


def _get_proxy_manager():
    """Lazy-import ProxyManager from dependencies.py."""
    from agora.server.dependencies import get_proxy_manager

    return get_proxy_manager()


# ═══════════════════════════════════════════════════════════════
# Module-level tool implementations (importable by tests)
# ═══════════════════════════════════════════════════════════════


async def check_health() -> dict:
    """Probe all registered services' health endpoints."""
    registry = _get_registry()
    await registry.health_check_all()
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "total": len(registry.list_all()),
            "healthy": len(registry.list_healthy()),
            "services": registry.to_dict(),
        }
    )


# ═══════════════════════════════════════════════════════════════
# Tool Registration
# ═══════════════════════════════════════════════════════════════


def register_diagnostics_tools(mcp: FastMCP) -> None:
    """Register all diagnostics/status MCP tools."""

    # ── check_health ──────────────────────────────────────────────

    mcp.tool()(check_health)

    # ── get_state_transitions ─────────────────────────────────────

    @mcp.tool()
    def get_state_transitions(
        service: str = "", since: str = "", limit: int = 50
    ) -> dict:
        """Query state transition history for services.

        Tracks circuit breaker state changes, service registration, and
        service unregistration events. Use this to understand service
        lifecycle and failure patterns.

        Args:
            service: Filter by service name (empty returns all)
            since: ISO timestamp filter (e.g. '2026-05-01T00:00:00Z')
            limit: Max results (default 50)
        """
        registry = _get_registry()
        transitions = registry.get_transitions(
            service=service, since=since, limit=limit
        )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "transitions": transitions,
                "count": len(transitions),
            }
        )

    # ── lifecycle_status ──────────────────────────────────────────

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
                    "idle_for_seconds": round(time.time() - last_used, 1)
                    if last_used
                    else 0,
                }
            )

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "watch_running": lm._idle_watch_task is not None
                and not lm._idle_watch_task.done(),
                "idle_timeout": lm._idle_timeout,
                "check_interval": lm._check_interval,
                "loaded_count": len(loaded),
                "loaded_tools": loaded,
            }
        )

    # ── lifecycle_start_watch ──────────────────────────────────────

    @mcp.tool()
    async def lifecycle_start_watch(
        idle_timeout: int = 300, check_interval: int = 60
    ) -> dict:
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
        except Exception as e:  # defensive fallback
            logger.exception("lifecycle_start_watch_error")
            return _error(f"Failed to start watch: {e}")

    # ── lifecycle_stop_watch ───────────────────────────────────────

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
        except Exception as e:  # defensive fallback
            logger.exception("lifecycle_stop_watch_error")
            return _error(f"Failed to stop watch: {e}")

    # ── lifecycle_load_all ─────────────────────────────────────────

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
        except Exception as e:  # defensive fallback
            logger.exception("lifecycle_load_all_error")
            return _error(f"Load all failed: {e}")

    # ── lifecycle_unload_all ───────────────────────────────────────

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
        except Exception as e:  # defensive fallback
            logger.exception("lifecycle_unload_all_error")
            return _error(f"Unload all failed: {e}")
