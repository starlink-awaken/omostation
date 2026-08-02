"""ProxyManager — manages lifecycle of downstream MCP client connections.

Orchestrates connecting, disconnecting, and routing to multiple
downstream MCP services through the proxy layer.

Integrates with :class:`IdleTimeoutManager` for automatic disconnection
of idle services and supports dynamic load/unload via reference counting.
"""

from __future__ import annotations

import os

import structlog

from agora.mcp_proxy.client import create_client  # type: ignore[import-not-found]
from agora.mcp_proxy.idle_timeout import (  # type: ignore[import-not-found]
    IdleTimeoutConfig,
    IdleTimeoutManager,
)
from agora.mcp_proxy.registry import (  # type: ignore[import-not-found]
    ProxyRegistry,
    UsageCallback,
)

logger = structlog.get_logger(__name__)


class ProxyManager:
    """Manages downstream MCP service connections and tool dispatch.

    Responsible for:
    - Starting/stopping connections to downstream MCP services
    - Registering/unregistering services dynamically
    - Dispatching tool calls to the correct service
    - Idle timeout management (optional, enabled via config)
    - Ref-count-based dynamic load/unload (optional)
    - Providing status information for observability
    """

    def __init__(
        self,
        idle_timeout_config: IdleTimeoutConfig | None = None,
    ):
        """Initialize the proxy manager.

        Args:
            idle_timeout_config: Optional idle timeout configuration.
                When provided, the idle timeout manager is automatically
                created and can be started via :meth:`enable_idle_timeout`.
                When None, idle timeout is disabled.
        """
        self.registry = ProxyRegistry()
        self._configs: dict[str, dict] = {}  # service_name → config dict
        self._idle_timeout_enabled = False

        # Idle timeout (optional)
        self._idle_config = idle_timeout_config
        self._idle_manager: IdleTimeoutManager | None = None

    # ── Callback management ────────────────────────────────────────────

    def set_usage_callback(self, callback: UsageCallback | None):
        """Set or clear the usage notification callback on the underlying registry.

        The callback receives ``(service_name, original_tool_name, arguments)``
        and is invoked after each successful ``dispatch()`` call.
        """
        self.registry.set_usage_callback(callback)

    # ── Idle timeout ──────────────────────────────────────────────────

    def is_idle_timeout_enabled(self) -> bool:
        """Check whether idle timeout is currently active."""
        return self._idle_timeout_enabled

    def enable_idle_timeout(self, config: IdleTimeoutConfig | None = None):
        """Enable idle timeout with the given (or existing) configuration.

        Starts the background sweep loop.  Safe to call multiple times.
        """
        if config is not None:
            self._idle_config = config

        if self._idle_config is None:
            self._idle_config = IdleTimeoutConfig()

        if self._idle_manager is None:
            # Wire idle timeout to registry's unregister_service
            self._idle_manager = IdleTimeoutManager(
                config=self._idle_config,
                on_idle=self.registry.unregister_service,
            )

        # Wire usage callback to refresh idle timer on dispatch
        self.registry.add_usage_callback(self._on_usage)

        # Wire unload callback to mark service as unloaded in idle tracker
        self.registry.add_unload_callback(self._on_unloaded)

        self._idle_manager.start()
        self._idle_timeout_enabled = True
        logger.info("proxy_idle_timeout_enabled", config=self._idle_config)

    async def disable_idle_timeout(self):
        """Disable idle timeout and stop the background sweep loop."""
        if self._idle_manager:
            await self._idle_manager.stop()
        self._idle_timeout_enabled = False
        logger.info("proxy_idle_timeout_disabled")

    def get_idle_timeout_status(self) -> dict:
        """Get current idle timeout status for observability."""
        if not self._idle_manager or not self._idle_timeout_enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "sweep_interval": self._idle_manager.config.sweep_interval,
            "default_timeout": self._idle_manager.config.default_timeout,
            "tracked_services": list(self._idle_manager.last_used.keys()),
            "idle_now": self._idle_manager.idle_services(),
        }

    # ── Internal callbacks ────────────────────────────────────────────

    async def _on_usage(self, service_name: str, tool_name: str, arguments: dict):
        """Usage callback — refresh idle timer on every dispatch."""
        if self._idle_manager:
            self._idle_manager.refresh(service_name)

    async def _on_unloaded(self, service_name: str):
        """Unload callback — mark service as unloaded in idle tracker."""
        if self._idle_manager:
            self._idle_manager.mark_unloaded(service_name)

    # ── Service lifecycle ─────────────────────────────────────────────

    async def start(self, services: list[dict], lazy: bool = False) -> dict[str, str]:
        """Connect to all configured downstream services in parallel.

        Args:
            services: List of service config dicts, each containing:
                - name: Service name
                - mcp_endpoint: HTTP endpoint URL or 'stdio'
                - command: Command for stdio transport
                - args: List of command arguments
            lazy: If True, do not connect immediately; wait for first tool dispatch.

        Returns:
            Dict mapping service_name → result string
        """
        import asyncio

        async def _connect_one(svc: dict) -> tuple[str, str]:
            name = svc.get("name", "unknown")
            try:
                result = await self.add_service(svc, lazy=lazy)
                return name, result
            except Exception as e:  # defensive fallback
                logger.error("proxy_start_failed", service=name, error=str(e))
                return name, f"error: {str(e)[:100]}"

        tasks = [_connect_one(svc) for svc in services]
        gathered = await asyncio.gather(*tasks)
        return dict(gathered)

    async def add_service(self, svc: dict, lazy: bool = False) -> str:
        """Connect and register a single downstream service.

        Also saves the service config in the registry for later
        lazy reconnection (idle timeout, dynamic load).

        Args:
            svc: Service config dict with name, mcp_endpoint/command/args.
            lazy: If True, only save the config and do not connect yet.

        Returns:
            Result string: "ok: N tools registered" or error message.
        """
        name = svc.get("name", "unknown")
        mcp_endpoint = svc.get("mcp_endpoint", "")
        command = svc.get("command", "")
        args = svc.get("args", [])
        # 治本 (backend dead=20 真根因): --package X 无 --directory 时在 agora 目录跑报
        # "workspace does not have a member X" (X 非 agora workspace member) + agora venv
        # 缺大部分 backend 包. 加 --directory 让 backend 回各自 workspace:
        #   kairon 包 → projects/kairon (保 --package, kairon workspace member)
        #   独立项目 (omo/ecos/cockpit) → projects/<X> (去 --package, root package -m)
        if "--package" in args and "--directory" not in args:
            from pathlib import Path

            _ws_root = (
                Path(__file__).resolve().parents[5]
            )  # agora/src/agora/mcp_proxy → workspace root
            _pi = args.index("--package")
            _pkg = args[_pi + 1] if _pi + 1 < len(args) else ""
            # 动态检测 kairon workspace member (治本硬编码漏列, e.g. kos 事故 PR#277):
            # kairon 包都在 projects/kairon/packages/<pkg>, 独立项目在 projects/<pkg>.
            # 替代旧 frozenset 硬编码 (漏 kos 致 os error 2), 新包加入 kairon 自动识别.
            _kairon_member = (
                _ws_root / "projects" / "kairon" / "packages" / _pkg
            ).is_dir()
            if _kairon_member:
                _ri = args.index("run") + 1
                args = (
                    args[:_ri]
                    + ["--directory", str(_ws_root / "projects" / "kairon")]
                    + args[_ri:]
                )
            else:
                args = args[:_pi] + args[_pi + 2 :]  # 去 --package X
                _ri = args.index("run") + 1
                args = (
                    args[:_ri]
                    + ["--directory", str(_ws_root / "projects" / _pkg)]
                    + args[_ri:]
                )
            svc["args"] = args
        cwd = svc.get("cwd")
        env = svc.get("env")
        init_timeout = svc.get("init_timeout", 10)

        # CR-ADMISSION-01 via AdmissionPort SPI (ADR-0181) — no direct metaos import
        try:
            from agora.admission import evaluate_admission

            admission_meta = svc.get("admission") or svc.get("metaos_admission")
            if not admission_meta:
                core_services = {
                    # Workspace projects
                    "gbrain",
                    "kairon",
                    "omo",
                    "runtime",
                    "metaos",
                    "ecos",
                    "agora",
                    "cockpit",
                    "cockpit-mcp",
                    "agent-runtime",
                    "kos",
                    "eidos",
                    "minerva",
                    "kronos",
                    "ontoderive",
                    "codeanalyze",
                    "iris",
                    "sophia",
                    "aetherforge",
                    "compute-mesh",
                    "llm-gateway",
                    "model-driven",
                    # Trusted external / community MCP servers
                    "chrome-devtools-mcp",
                    "docker-mcp-gateway",
                    "gitnexus",
                    "mcp-server-apple-events",
                    "mcp-server-sqlite",
                    "serena",
                }
                # Local workspace services are trusted by default (self-hosted / source-controlled).
                # Use WORKSPACE_ROOT env (no hard-coded absolute path).
                _workspace_root = os.environ.get(
                    "WORKSPACE_ROOT", os.path.expanduser("~/Workspace")
                )
                _cmd = " ".join([svc.get("command", ""), *svc.get("args", [])])
                _is_local_workspace = (
                    f"{_workspace_root}/projects/" in _cmd
                    or _cmd.startswith(f"{_workspace_root}/")
                )
                if (
                    name not in core_services
                    and not name.startswith("sys-")
                    and not _is_local_workspace
                ):
                    raise ValueError(
                        "Missing 'admission' (or legacy 'metaos_admission') metadata block."
                    )
                admission_meta = {
                    "role": "evaluator" if name == "kairon" else "generator",
                    "supports_otlp": True,
                    "omo_audit_trail_id": "SYS-BOOTSTRAP",
                    "declared_values": ["human-centric", "objective", "transparent"],
                }

            req = {"domain": name, **admission_meta}
            decision = evaluate_admission(req)
            if decision.get("status") != "admitted":
                raise ValueError(f"Reasons: {decision.get('reasons')}")
            if decision.get("degraded"):
                logger.warning(
                    "proxy_admission_degraded",
                    service=name,
                    reasons=decision.get("reasons"),
                )
        except ValueError as e:
            logger.error("proxy_admission_rejected", service=name, error=str(e))
            return f"error: Admission Rejected - {e}"

        # Save config for lazy reconnection (even if connection fails)
        self._configs[name] = dict(svc)
        self.registry.save_config(name, svc)

        if lazy:
            logger.info("proxy_service_lazy_configured", service=name)
            return "ok: lazy configured"

        # Remove existing if reconnecting
        if name in self.registry._clients:
            await self.registry.unregister_service(name)

        try:
            client = create_client(
                name,
                mcp_endpoint,
                command,
                args,
                cwd=cwd,
                env=env,
                init_timeout=init_timeout,
            )
        except ValueError as e:
            logger.error("proxy_create_client_failed", service=name, error=str(e))
            return f"error: {str(e)[:100]}"

        ok = await self.registry.register_service(name, client)
        if ok:
            count = len(
                [e for e in self.registry.entries.values() if e.service_name == name]
            )
            logger.info("proxy_service_connected", service=name, tools=count)
            return f"ok: {count} tools registered"
        else:
            logger.error("proxy_service_connect_failed", service=name)
            return "error: connection failed"

    async def remove_service(self, name: str) -> str:
        """Disconnect and permanently remove a downstream service.

        Removes both the connection and the saved config, so the
        service cannot be lazily reconnected.

        Args:
            name: Service name to remove.

        Returns:
            "removed" or error message.
        """
        if name not in self.registry._clients and name not in self._configs:
            return "not_found"
        self.registry.forget_config(name)
        self._configs.pop(name, None)
        if name in self.registry._clients:
            await self.registry.unregister_service(name)
        return "removed"

    async def reload_service(self, name: str) -> str:
        """Force-reconnect a service using its saved config.

        Useful after a configuration change or to recover from a
        persistent connection failure.

        Args:
            name: Service name to reload.

        Returns:
            Result string (same format as add_service).
        """
        config = self._configs.get(name)
        if not config:
            return "not_found"
        return await self.add_service(config)

    # ── Reference-counted lifecycle ───────────────────────────────────

    def acquire(self, service_name: str) -> int:
        """Acquire a reference to a service (for scoped usage).

        Increments the reference count.  Does NOT auto-connect —
        use :meth:`ensure_connected` for that.

        Returns the new reference count.
        """
        return self.registry.acquire(service_name)

    def release(self, service_name: str) -> int:
        """Release a previously acquired reference.

        When the count reaches zero, the service will be disconnected
        (if idle timeout is enabled, the next sweep will handle it;
        otherwise it remains connected until explicitly removed).

        Returns the new reference count.
        """
        return self.registry.release(service_name)

    async def ensure_connected(self, service_name: str) -> bool:
        """Ensure a service is connected, using lazy reconnect if needed.

        Useful when a caller wants to guarantee a service is available
        before dispatching.  Safe to call on already-connected services.

        Returns True if the service is now connected.
        """
        if self.registry.is_connected(service_name):
            return True
        if self.registry.has_saved_config(service_name):
            return await self.registry.lazy_connect(service_name)
        return False

    # ── Dispatch ──────────────────────────────────────────────────────

    async def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Dispatch a tool call to the correct downstream service.

        If the target service has been disconnected (e.g. by idle
        timeout), this method attempts a lazy reconnect automatically.

        Args:
            tool_name: Full tool name (e.g. 'kos.semantic_search').
            arguments: Dict of tool arguments.

        Returns:
            Tool result dict.
        """
        return await self.registry.dispatch(tool_name, arguments)

    async def list_resources(self) -> list[dict]:
        """Aggregate resources from all connected/known downstream services."""
        import asyncio

        all_resources = []
        tasks = []
        # Connect lazy services if needed, but for list we only query currently connected ones to be fast
        # Alternatively, we can query all known.
        for client in self.registry._clients.values():
            if client.connected:
                tasks.append(client.list_resources())
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    all_resources.extend(res)
        return all_resources

    async def read_resource(self, uri: str) -> dict:
        """Route a resource read request based on its prefix.

        Currently tries all connected clients until one returns the resource,
        or we can use a prefix mapping. For now we will fan-out or route by known prefixes.
        """
        # Use MountRegistry to dynamically resolve routing instead of hardcoded if/else
        from agora.mcp.mount_registry import get_mount_registry

        registry = get_mount_registry()
        # Fallback to simple prefixes mapping if not registered dynamically
        # In the future, everything should be registered through MountRegistry

        service_name = registry.resolve_provider(uri)
        if not service_name:
            if uri.startswith("bos://omo/"):
                service_name = "omo"
            elif uri.startswith("bos://memory/gbrain/"):
                service_name = "gbrain"
            elif uri.startswith("bos://memory/"):
                service_name = "ecos-bos-mounter"
            elif uri.startswith("bos://forge/"):
                service_name = "forge"
            elif uri.startswith("bos://persona/"):
                service_name = "sot-bridge-persona"
            elif uri.startswith("bos://analysis/code/"):
                service_name = "codeanalyze"
            elif uri.startswith("bos://analysis/derive/"):
                service_name = "ontoderive"
            elif uri.startswith("bos://analysis/research/"):
                service_name = "minerva"
            elif uri.startswith("bos://forge/registry/"):
                service_name = "forge"

        if service_name:
            if isinstance(service_name, str):  # Downstream proxy client by service name
                await self.ensure_connected(service_name)
                client = self.registry._clients.get(service_name)
                if client and client.connected:
                    return await client.read_resource(uri)
            else:
                # If provider is a direct local handler (not implemented yet, but for future)
                pass

        # Fallback: broadcast to all connected
        for name, client in self.registry._clients.items():
            if name == service_name:
                continue
            if client.connected:
                res = await client.read_resource(uri)
                if isinstance(res, dict) and "contents" in res:
                    return res
        return {
            "status": "error",
            "error": f"Resource not found or no provider for: {uri}",
        }

    # ── Status ────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Get current proxy status.

        Returns dict with:
        - status: 'idle' or 'running'
        - connected_services: list of connected service names
        - tools: total registered tool count
        - services: dict of service → tool count
        - known_services: all services (including disconnected but configured)
        - idle_timeout: idle timeout status if enabled
        - ref_counts: current reference counts per service
        """
        if not self.registry._clients and not self.registry.known_services:
            result = {
                "status": "idle",
                "connected_services": [],
                "tools": 0,
                "services": {},
                "ref_counts": self.registry.ref_counts,
            }
            if self._idle_timeout_enabled and self._idle_config:
                result["idle_timeout"] = {
                    "default_timeout": self._idle_config.default_timeout,
                    "sweep_interval": self._idle_config.sweep_interval,
                }
            return result

        services_info = {}
        for name in self.registry.known_services:
            client = self.registry._clients.get(name)
            tool_count = len(
                [e for e in self.registry.entries.values() if e.service_name == name]
            )
            services_info[name] = {
                "connected": client.connected if client else False,
                "tools": tool_count,
                "ref_count": self.registry._ref_counts.get(name, 0),
                "has_config": name in self._configs,
            }

        return {
            "status": "running",
            "connected_services": list(self.registry._clients.keys()),
            "tools": len(self.registry.entries),
            "services": services_info,
            "known_services": self.registry.known_services,
            "ref_counts": self.registry.ref_counts,
        }

    async def shutdown(self):
        """Disconnect all downstream services and stop idle timeout."""
        if self._idle_timeout_enabled:
            await self.disable_idle_timeout()
        await self.registry.disconnect_all()
        self._configs.clear()
        logger.info("proxy_manager_shutdown_complete")
