"""ProxyRegistry — maps tool names to downstream services and manages client connections.

Supports dynamic load/unload with reference counting and lazy reconnection.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]
from agora.mcp_proxy.client import MCPClient, create_client  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

# Type alias for usage callback: async fn(service_name, original_tool_name, arguments)
UsageCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]

# Type alias for unload callback: async fn(service_name)
UnloadCallback = Callable[[str], Awaitable[None]]


@dataclass
class ProxyEntry:
    """A registered downstream tool in the proxy."""

    tool_name: str  # Full name: "kos.semantic_search"
    service_name: str  # Downstream service name
    original_name: str  # Original tool name in the downstream service
    description: str  # Tool description from schema
    parameters: dict  # JSON Schema for parameters
    client: MCPClient  # The client instance to use for calling


class ProxyRegistry:
    """Registry of all downstream tools available through the proxy.

    Maps tool names (with service prefix) to client connections,
    and provides dispatch logic for routing tool calls.

    Supports:
    - **Usage callback**: invoked on every successful dispatch (idle timeout refresh).
    - **Unload callback**: invoked when a service is released with zero refs (for cleanup).
    - **Reference counting**: :meth:`acquire` / :meth:`release` for lifecycle management.
    - **Lazy reconnect**: :meth:`dispatch` auto-reconnects known services whose client
      has been disconnected (e.g. by idle timeout).
    """

    def __init__(self):
        self._entries: dict[str, ProxyEntry] = {}  # tool_name → entry
        self._clients: dict[str, MCPClient] = {}  # service_name → client
        self._usage_callbacks: list[UsageCallback] = []
        self._unload_callbacks: list[UnloadCallback] = []

        # Reference counting — used for dynamic load/unload
        self._ref_counts: dict[str, int] = {}  # service_name → ref_count
        # Saved configs — used for lazy reconnection after idle timeout unload
        self._saved_configs: dict[str, dict] = {}  # service_name → config dict

    # ── Callback management ────────────────────────────────────────────

    # ── Multi-callback support ──────────────────────────────────────
    #
    # Multiple consumers (IdleTimeoutManager, LifecycleManager) can
    # independently register their own usage/unload callbacks without
    # overwriting each other.  ``set_*`` clears all and sets a single
    # callback (backward-compat); ``add_*`` / ``remove_*`` manage the
    # list incrementally.

    def add_usage_callback(self, callback: UsageCallback) -> None:
        """Register an additional usage callback.

        The callback receives ``(service_name, original_tool_name, arguments)``
        and is invoked after each successful ``dispatch()`` call.
        No-op if the same callback is already registered.
        """
        if callback not in self._usage_callbacks:
            self._usage_callbacks.append(callback)

    def remove_usage_callback(self, callback: UsageCallback) -> None:
        """Remove a previously registered usage callback."""
        self._usage_callbacks = [cb for cb in self._usage_callbacks if cb != callback]

    def set_usage_callback(self, callback: UsageCallback | None):
        """Set or clear the usage notification callback (legacy).

        Clears all existing callbacks first, then adds the given one
        if not None.  Prefer :meth:`add_usage_callback` /
        :meth:`remove_usage_callback` for cooperative multi-consumer use.
        """
        self._usage_callbacks.clear()
        if callback is not None:
            self._usage_callbacks.append(callback)

    def add_unload_callback(self, callback: UnloadCallback) -> None:
        """Register an additional unload callback.

        The callback receives ``(service_name)`` and is invoked when a
        service is being released with zero reference count.
        No-op if the same callback is already registered.
        """
        if callback not in self._unload_callbacks:
            self._unload_callbacks.append(callback)

    def remove_unload_callback(self, callback: UnloadCallback) -> None:
        """Remove a previously registered unload callback."""
        self._unload_callbacks = [cb for cb in self._unload_callbacks if cb != callback]

    def set_unload_callback(self, callback: UnloadCallback | None):
        """Set or clear the unload notification callback (legacy).

        Clears all existing callbacks first, then adds the given one
        if not None.  Prefer :meth:`add_unload_callback` /
        :meth:`remove_unload_callback` for cooperative multi-consumer use.
        """
        self._unload_callbacks.clear()
        if callback is not None:
            self._unload_callbacks.append(callback)

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def entries(self) -> dict[str, ProxyEntry]:
        return self._entries

    @property
    def connected_services(self) -> list[str]:
        return list(self._clients.keys())

    @property
    def ref_counts(self) -> dict[str, int]:
        """Return a copy of current reference counts."""
        return dict(self._ref_counts)

    @property
    def known_services(self) -> list[str]:
        """Return names of all services that have been registered at least once.

        Includes both currently connected and previously disconnected services
        whose configs are still saved.
        """
        connected = set(self._clients.keys())
        saved = set(self._saved_configs.keys())
        return sorted(connected | saved)

    # ── Entry lookup ──────────────────────────────────────────────────

    def get_entry(self, tool_name: str) -> ProxyEntry | None:
        """Resolve a tool name to its ProxyEntry.

        Supports exact match first, then prefix match.
        E.g. "kos.semantic_search" → exact match on "kos.semantic_search"
        E.g. "kos" → prefix match (no service registered with just "kos")
        """
        if tool_name in self._entries:
            return self._entries[tool_name]
        # Prefix match: try "kos" prefix for "kos.semantic_search"
        parts = tool_name.split(".", 1)
        if len(parts) > 1 and parts[0] in self._clients:
            return self._entries.get(tool_name)
        return None

    # ── Reference counting / dynamic lifecycle ─────────────────────────

    def save_config(self, service_name: str, config: dict):
        """Store a service configuration for later lazy reconnection.

        Args:
            service_name: Name of the service.
            config: Config dict (must contain at least ``mcp_endpoint`` or
                    ``command`` so that :meth:`create_client` can work).
        """
        self._saved_configs[service_name] = dict(config)

    def get_saved_config(self, service_name: str) -> dict | None:
        """Return saved config for a service, or None."""
        return self._saved_configs.get(service_name)

    def forget_config(self, service_name: str):
        """Remove saved config for a service (permanent removal)."""
        self._saved_configs.pop(service_name, None)
        self._ref_counts.pop(service_name, None)

    def has_saved_config(self, service_name: str) -> bool:
        """Check whether a service has a saved config for lazy reconnect."""
        return service_name in self._saved_configs

    def is_connected(self, service_name: str) -> bool:
        """Check whether a specific service is currently connected."""
        client = self._clients.get(service_name)
        return client is not None and client.connected

    def acquire(self, service_name: str) -> int:
        """Acquire a reference to a service (for scoped usage).

        Increments the reference count for the service.  Does NOT
        automatically reconnect — use :meth:`lazy_connect` for that.

        Returns the new reference count.
        """
        count = self._ref_counts.get(service_name, 0) + 1
        self._ref_counts[service_name] = count
        return count

    async def lazy_connect(self, service_name: str) -> bool:
        """Try to connect a service using its saved configuration.

        Called automatically by :meth:`dispatch` when the target entry's
        client is not connected.  Can also be called explicitly.

        Returns True if the service is now connected.
        """
        config = self._saved_configs.get(service_name)
        if not config:
            logger.warning("proxy_lazy_connect_no_config", service=service_name)
            return False

        if self.is_connected(service_name):
            return True

        mcp_endpoint = config.get("mcp_endpoint", "")
        command = config.get("command", "")
        args = config.get("args", [])
        cwd = config.get("cwd")
        env = config.get("env")
        init_timeout = config.get("init_timeout", 10)

        try:
            client = create_client(
                service_name, mcp_endpoint, command, args, cwd=cwd, env=env, init_timeout=init_timeout
            )
        except ValueError as e:
            logger.error("proxy_lazy_connect_create_failed", service=service_name, error=str(e))
            return False

        return await self.register_service(service_name, client)

    def release(self, service_name: str) -> int:
        """Release a previously acquired reference.

        Decrements the reference count.  When the count reaches zero,
        the service is **not** automatically disconnected — call
        :meth:`unregister_service` separately, or wire :meth:`set_unload_callback`
        to handle zero-ref cleanup.

        Returns the new reference count (0 if the service had no refs).
        """
        current = self._ref_counts.get(service_name, 0)
        if current <= 0:
            return 0
        new_count = current - 1
        if new_count == 0:
            self._ref_counts.pop(service_name, None)
            # Notify all unload callbacks (safe to call without running loop)
            if self._unload_callbacks:
                try:
                    import asyncio

                    loop = asyncio.get_running_loop()
                    for cb in self._unload_callbacks:
                        loop.create_task(cb(service_name))
                except RuntimeError:
                    pass  # No running event loop — skip callback
                except Exception as e:
                    logger.warning("proxy_unload_callback_failed", service=service_name, error=str(e))
        else:
            self._ref_counts[service_name] = new_count
        return new_count

    # ── Registration / unregistration ──────────────────────────────────

    async def register_service(self, service_name: str, client: MCPClient) -> bool:
        """Connect to a service, discover its tools, and register them."""
        if not await client.connect():
            logger.error("proxy_connect_failed", service=service_name)
            return False

        tools = await client.list_tools()
        if not tools:
            logger.warning("proxy_no_tools_found", service=service_name)
            return False

        count = 0
        for tool in tools:
            original_name = tool.get("name", "")
            full_name = f"{service_name}.{original_name}"
            description = tool.get("description", "")
            parameters = tool.get("inputSchema", tool.get("parameters", {}))

            entry = ProxyEntry(
                tool_name=full_name,
                service_name=service_name,
                original_name=original_name,
                description=description,
                parameters=parameters,
                client=client,
            )
            self._entries[full_name] = entry
            count += 1

        self._clients[service_name] = client
        logger.info("proxy_service_registered", service=service_name, tools=count)
        return True

    async def unregister_service(self, service_name: str):
        """Disconnect and remove all tools for a service.

        Preserves the saved config so the service can be lazily reconnected
        later.  To permanently remove, call :meth:`forget_config` first.
        """
        # Remove all entries for this service
        to_remove = [name for name, entry in self._entries.items() if entry.service_name == service_name]
        for name in to_remove:
            del self._entries[name]

        # Disconnect and remove client
        client = self._clients.pop(service_name, None)
        if client:
            await client.disconnect()

        logger.info("proxy_service_unregistered", service=service_name, tools_removed=len(to_remove))

    async def unregister_and_forget(self, service_name: str):
        """Disconnect a service and permanently delete its saved config."""
        self.forget_config(service_name)
        await self.unregister_service(service_name)

    async def register_from_registry(self, service_registry: ServiceRegistry, proxy_configs: list[dict] | None = None):
        """Register all services from the existing ServiceRegistry into proxy connections.

        Args:
            service_registry: The ServiceRegistry to sync from.
            proxy_configs: Optional list of proxy service configs (from agora-proxy-services.json).
                           Needed for stdio services whose command/args are not stored in Service.
        """
        config_map: dict[str, dict] = {}
        if proxy_configs:
            for cfg in proxy_configs:
                config_map[cfg.get("name")] = cfg

        services = service_registry.list_all()
        for svc in services:
            if svc.name in self._clients:
                continue  # already connected

            # HTTP services: use mcp_endpoint from Service
            if svc.mcp_endpoint and svc.mcp_endpoint.startswith("http"):
                from agora.core.service_base import is_safe_url  # type: ignore[import-not-found]

                if not is_safe_url(svc.mcp_endpoint):
                    logger.warning("proxy_skip_unsafe_endpoint", service=svc.name, endpoint=svc.mcp_endpoint)
                    continue
                client = create_client(svc.name, svc.mcp_endpoint)
                await self.register_service(svc.name, client)
                continue

            # stdio services: use command/args from proxy configs
            cfg = config_map.get(svc.name)
            if cfg:
                command = cfg.get("command", "")
                args = cfg.get("args", [])
                endpoint = cfg.get("mcp_endpoint", "")
                if command or endpoint:
                    client = create_client(svc.name, endpoint, command, args)
                    await self.register_service(svc.name, client)

        logger.info("proxy_registry_sync_complete", services=len(self._clients))

    # ── Dispatch (with lazy reconnect) ─────────────────────────────────

    async def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the correct downstream service.

        If the target service's client has been disconnected (e.g. by
        idle timeout) but a saved config exists, this method attempts
        a lazy reconnect automatically.

        Args:
            tool_name: Full tool name (e.g. "kos.semantic_search")
            arguments: Tool arguments as a dict

        Returns:
            Tool result as a dict
        """
        entry = self.get_entry(tool_name)
        if not entry:
            return {"status": "error", "error": f"Tool '{tool_name}' not found in proxy"}

        svc_name = entry.service_name

        # Lazy reconnect if the client has been disconnected
        if not entry.client.connected:
            reconnect_ok = await self.lazy_connect(svc_name)
            if not reconnect_ok:
                return {
                    "status": "error",
                    "error": f"Service '{svc_name}' is disconnected and reconnect failed",
                }
            # Re-fetch entry after reconnect (entry.client pointer has been replaced)
            entry = self.get_entry(tool_name)
            if not entry:
                return {"status": "error", "error": f"Tool '{tool_name}' lost after reconnect"}

        try:
            result = await entry.client.call_tool(entry.original_name, arguments)
        except Exception as e:
            logger.error("proxy_dispatch_failed", tool=tool_name, service=svc_name, error=str(e))
            return {"status": "error", "error": str(e)}

        # Notify all usage callbacks for lifecycle management (idle timeout refresh)
        if self._usage_callbacks:
            for cb in self._usage_callbacks:
                try:
                    await cb(svc_name, entry.original_name, arguments)
                except Exception as e:
                    logger.warning("proxy_usage_callback_failed", tool=tool_name, callback=cb.__name__, error=str(e))

        return result if isinstance(result, dict) else {"status": "ok", "data": result}

    # ── Tool schema listing ────────────────────────────────────────────

    def get_tool_schemas(self) -> list[dict]:
        """Get all registered tool schemas for dynamic registration.

        Returns a list of dicts compatible with FastMCP tool registration:
        {name, description, parameters, handler}
        """
        schemas = []
        for entry in self._entries.values():
            schemas.append(
                {
                    "name": entry.tool_name,
                    "description": entry.description,
                    "parameters": entry.parameters,
                    "service_name": entry.service_name,
                    "original_name": entry.original_name,
                }
            )
        return schemas

    # ── Disconnect all ────────────────────────────────────────────────

    async def disconnect_all(self):
        """Disconnect all downstream clients and clear all state.

        Unlike :meth:`unregister_service`, this does NOT preserve
        saved configs.  Call :meth:`save_config` again before
        reconnecting.
        """
        for service_name in list(self._clients.keys()):
            await self.unregister_service(service_name)
        self._entries.clear()
        self._clients.clear()
        self._ref_counts.clear()
        self._saved_configs.clear()
