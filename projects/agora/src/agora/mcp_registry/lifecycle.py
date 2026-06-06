"""MCP tool lifecycle management — Phase 2: dynamic load/unload with real proxy integration and idle timeout."""

import asyncio
import time

import structlog

from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)


class LifecycleManager:
    """Manages tool load/unload lifecycle with real proxy integration and idle timeout.

    Phase 1: Status transitions only (discovered → loaded, loaded → idle).
    Phase 2: Actual proxy connection/disconnection + idle timeout auto-unload.
    """

    def __init__(
        self,
        catalog: ToolCatalog,
        proxy_manager: ProxyManager | None = None,
        idle_timeout: float = 300.0,
        check_interval: float = 60.0,
        max_load_retries: int = 2,
    ):
        self._catalog = catalog
        self._proxy = proxy_manager
        self._idle_timeout = idle_timeout
        self._check_interval = check_interval
        self._max_load_retries = max_load_retries
        self._idle_watch_task: asyncio.Task | None = None
        self._health_watch_task: asyncio.Task | None = None
        # Track last-used timestamps for loaded tools (tool_id → epoch seconds)
        self._last_used: dict[str, float] = {}
        # Whether the proxy usage callback has been wired to avoid redundant calls
        self._usage_callback_wired: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────

    async def load_tool(self, tool_id: str) -> bool:
        """Transition tool to loaded status.

        Phase 2: Connects to proxy and registers tools.
        Wires proxy usage callback to refresh idle timeout on tool dispatch.
        Retries on transient proxy failures (up to ``max_load_retries``).
        Returns True if tool was successfully loaded.
        """
        tool = self._catalog.get_tool(tool_id)
        if not tool:
            logger.warning("load_tool_not_found", tool_id=tool_id)
            return False

        if tool.get("status") == "loaded":
            return True

        # Phase 2: real proxy connection with retry
        if self._proxy:
            config = self._build_service_config(tool)
            if config is None:
                logger.error("load_tool_no_config", tool_id=tool_id, name=tool.get("name"))
                return False

            last_error = ""
            for attempt in range(1, self._max_load_retries + 1):
                result = await self._proxy.add_service(config)
                if result.startswith("ok"):
                    last_error = ""
                    break
                last_error = result
                if attempt < self._max_load_retries:
                    logger.warning(
                        "load_tool_retry",
                        tool_id=tool_id,
                        name=tool.get("name"),
                        attempt=attempt,
                        error=result,
                    )
                    await asyncio.sleep(1.0 * attempt)  # linear backoff

            if last_error:
                logger.error("load_tool_proxy_failed", tool_id=tool_id, result=last_error)
                return False

            # Wire usage callback once to refresh idle timeout on every tool dispatch
            if not self._usage_callback_wired:
                self._proxy.registry.add_usage_callback(self._record_usage_from_proxy)
                self._usage_callback_wired = True

        # Commit status transition
        self._catalog.update_status(tool_id, "loaded")
        async with self._lock:
            self._last_used[tool_id] = time.monotonic()
        logger.info("tool_loaded", tool_id=tool_id, name=tool.get("name"))
        return True

    async def unload_tool(self, tool_id: str) -> bool:
        """Transition tool from loaded to idle status.

        Phase 2: Disconnects from proxy.
        Clears usage callback if no loaded tools remain.
        Returns True if tool was successfully unloaded (or already idle/not found).
        """
        tool = self._catalog.get_tool(tool_id)
        if not tool:
            return False

        current_status = tool.get("status", "")
        if current_status != "loaded":
            return True  # Already unloaded or not yet loaded

        # Phase 2: real proxy disconnection
        if self._proxy:
            await self._proxy.remove_service(tool_id)

        self._catalog.update_status(tool_id, "idle")
        async with self._lock:
            self._last_used.pop(tool_id, None)
            remaining = bool(self._last_used)

        # Remove usage callback if no more tools are loaded
        if self._proxy and not remaining:
            self._proxy.registry.remove_usage_callback(self._record_usage_from_proxy)
            self._usage_callback_wired = False

        logger.info("tool_unloaded", tool_id=tool_id, name=tool.get("name"))
        return True

    async def record_usage(self, tool_id: str):
        """Record tool usage, refreshing its idle timeout."""
        async with self._lock:
            if tool_id in self._last_used:
                self._last_used[tool_id] = time.monotonic()
        self._catalog.record_usage(tool_id)

    async def load_by_status(self, status: str = "idle") -> int:
        """Load all tools with a given status.

        Args:
            status: Status filter (default "idle" — previously loaded tools).

        Returns:
            Number of tools successfully loaded.
        """
        tools = self._catalog.list_tools(status=status)
        count = 0
        for tool in tools:
            tid = tool.get("id", "")
            if not tid:
                continue
            ok = await self.load_tool(tid)
            if ok:
                count += 1
        logger.info("load_by_status_complete", status=status, requested=len(tools), loaded=count)
        return count

    async def unload_by_status(self, status: str = "loaded") -> int:
        """Unload all tools with a given status.

        Args:
            status: Status filter (default "loaded" — currently loaded tools).

        Returns:
            Number of tools successfully unloaded.
        """
        tools = self._catalog.list_tools(status=status)
        count = 0
        for tool in tools:
            tid = tool.get("id", "")
            if not tid:
                continue
            ok = await self.unload_tool(tid)
            if ok:
                count += 1
        logger.info("unload_by_status_complete", status=status, requested=len(tools), unloaded=count)
        return count

    # ── Status reporting ────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return current status of all managed tools.

        Returns a dict with:
        - loaded: list of tool_ids currently tracked as loaded
        - idle: list of tool_ids with idle status
        - unloaded: list of tool_ids that are not loaded
        - loaded_count: number of currently loaded tools
        - idle_watch_running: whether idle timeout watcher is active
        - health_watch_running: whether health check watcher is active
        """
        loaded = list(self._last_used.keys())
        idle: list[str] = []
        unloaded: list[str] = []
        for tool in self._catalog.list_tools():
            tid = tool.get("id", "")
            s = tool.get("status", "")
            if s == "idle":
                idle.append(tid)
            elif s != "loaded":
                unloaded.append(tid)

        return {
            "loaded": loaded,
            "loaded_count": len(loaded),
            "idle": idle,
            "unloaded": unloaded,
            "idle_watch_running": self._idle_watch_task is not None,
            "health_watch_running": self._health_watch_task is not None,
            "idle_timeout": self._idle_timeout,
            "check_interval": self._check_interval,
        }

    # ── Health check ────────────────────────────────────────────────

    async def start_health_watch(self):
        """Start the background health-check watcher.

        Periodically verifies loaded tools are still connected in the
        proxy. Disconnected tools are automatically unloaded.
        """
        if self._health_watch_task is not None:
            return
        self._health_watch_task = asyncio.create_task(self._health_watch_loop())
        logger.info("health_watch_started", check_interval=self._check_interval)

    async def stop_health_watch(self):
        """Stop the background health-check watcher."""
        if self._health_watch_task is not None:
            self._health_watch_task.cancel()
            try:
                await self._health_watch_task
            except asyncio.CancelledError:
                pass
            self._health_watch_task = None
            logger.info("health_watch_stopped")

    async def _health_watch_loop(self):
        """Periodically check if loaded tools are still connected in the proxy."""
        while True:
            await asyncio.sleep(self._check_interval * 2)  # less frequent than idle check
            if not self._proxy or not self._last_used:
                continue

            connected = set(self._proxy.registry._clients.keys()) if self._proxy else set()
            stale: list[str] = []
            async with self._lock:
                for tool_id in self._last_used:
                    if tool_id not in connected:
                        stale.append(tool_id)
            for tool_id in stale:
                tool = self._catalog.get_tool(tool_id)
                name = tool.get("name", tool_id) if tool else tool_id
                logger.warning(
                    "health_check_stale_service",
                    tool_id=tool_id,
                    name=name,
                )
                # Reconnect tool (stale detection → recover)
                tool_info = self._catalog.get_tool(tool_id)
                if tool_info:
                    async with self._lock:
                        self._last_used.pop(tool_id, None)
                    self._catalog.update_status(tool_id, "idle")
                    await self.load_tool(tool_id)

    # ── Idle timeout ────────────────────────────────────────────────

    async def start_idle_watch(self):
        """Start the background idle-timeout watcher."""
        if self._idle_watch_task is not None:
            return
        self._idle_watch_task = asyncio.create_task(self._idle_watch_loop())
        logger.info("idle_watch_started", idle_timeout=self._idle_timeout, check_interval=self._check_interval)

    async def stop_idle_watch(self):
        """Stop the background idle-timeout watcher."""
        if self._idle_watch_task is not None:
            self._idle_watch_task.cancel()
            try:
                await self._idle_watch_task
            except asyncio.CancelledError:
                pass
            self._idle_watch_task = None
            logger.info("idle_watch_stopped")

    async def _idle_watch_loop(self):
        """Periodically check for idle tools and auto-unload them."""
        while True:
            await asyncio.sleep(self._check_interval)
            now = time.monotonic()
            to_unload: list[str] = []
            idle_details: list[tuple[str, float]] = []
            async with self._lock:
                for tool_id, last_used in self._last_used.items():
                    idle_for = now - last_used
                    if idle_for > self._idle_timeout:
                        to_unload.append(tool_id)
                        idle_details.append((tool_id, idle_for))
            for tool_id, idle_secs in idle_details:
                tool = self._catalog.get_tool(tool_id)
                name = tool.get("name", tool_id) if tool else tool_id
                logger.info(
                    "tool_idle_timeout_unloading",
                    tool_id=tool_id,
                    name=name,
                    idle_for_seconds=round(idle_secs, 1),
                )
                await self.unload_tool(tool_id)

    # ── Cleanup ─────────────────────────────────────────────────────

    async def close(self):
        """Shutdown: stop watches, unload all loaded tools, disconnect from proxy."""
        await self.stop_idle_watch()
        await self.stop_health_watch()
        await self.unload_by_status("loaded")
        logger.info("lifecycle_manager_closed")

    # ── Internal helpers ────────────────────────────────────────────

    async def _record_usage_from_proxy(self, service_name: str, _tool_name: str, _arguments: dict):
        """Usage callback invoked by ProxyRegistry on every tool dispatch.

        Refreshes the idle timeout for the service whose tool was called.
        """
        async with self._lock:
            if service_name in self._last_used:
                self._last_used[service_name] = time.monotonic()
        self._catalog.record_usage(service_name)

    @staticmethod
    def _build_service_config(tool: dict) -> dict | None:
        """Build a ProxyManager-compatible service config from a catalog entry.

        Returns a config dict with ``name``, ``command``, ``args``, and
        ``mcp_endpoint`` fields, or ``None`` if no usable config can be built.

        Priority order:
        1. ``mcp_endpoint`` HTTP URL → HTTP transport (no command/args needed)
        2. ``metadata.command`` → stdio with explicit command
        3. ``entry`` → stdio with uv/python module
        4. ``install_path`` → stdio with explicit path
        5. ``tool_type`` → type-based fallback (npx/pipx)
        """
        name = tool.get("name", "")
        if not name:
            return None

        metadata = tool.get("metadata", {}) or {}
        entry = tool.get("entry", "")
        install_path = tool.get("install_path", "")
        command = metadata.get("command", "")
        args = metadata.get("args", [])
        tool_type = tool.get("tool_type", "")
        repo_url = tool.get("repo_url", "")

        config: dict = {"name": name}

        # Priority 1: HTTP endpoint — use HTTP transport
        mcp_endpoint = tool.get("mcp_endpoint", metadata.get("mcp_endpoint", ""))
        if mcp_endpoint and mcp_endpoint.startswith("http"):
            config["mcp_endpoint"] = mcp_endpoint
            return config

        # Priority 2: explicit metadata command
        if command:
            config["command"] = command
            config["args"] = args if isinstance(args, list) else []
            config["mcp_endpoint"] = "stdio"
        elif entry:
            # Kairon-style entry: e.g. "kronos-mcp" or "kos.mcp.server"
            parts = entry.split(".")
            if len(parts) >= 2 and parts[0] and parts[0] != entry:
                # Qualified python module: kos.mcp.server
                config["command"] = "uv"
                config["args"] = ["run", "--package", parts[0], "python", "-m", entry]
            else:
                # Simple entry point: kronos-mcp
                config["command"] = "uv"
                config["args"] = ["run", "--package", name, entry]
            config["mcp_endpoint"] = "stdio"
        elif install_path:
            config["command"] = install_path
            config["args"] = []
            config["mcp_endpoint"] = "stdio"
        elif tool_type == "node":
            config["command"] = "npx"
            config["args"] = ["-y", name]
            config["mcp_endpoint"] = "stdio"
        elif tool_type == "python":
            # Try pipx if no better config available
            config["command"] = "pipx"
            config["args"] = ["run", name]
            config["mcp_endpoint"] = "stdio"
        elif repo_url:
            logger.warning("build_config_repo_only", name=name, repo_url=repo_url)
            return None
        else:
            logger.warning("build_config_no_entry", name=name, tool_type=tool_type)
            return None

        return config
