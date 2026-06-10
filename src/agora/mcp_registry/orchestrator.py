"""End-to-end orchestration: discover → evaluate → install → load."""

import structlog

from agora.mcp_registry.evaluator import QualityScorer  # type: ignore[import-not-found]
from agora.mcp_registry.lifecycle import LifecycleManager  # type: ignore[import-not-found]
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]
from agora.mcp_registry.sources import search_all  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)


class Orchestrator:
    """Coordinates the full tool discovery-to-loading pipeline.

    Phase 1: External discovery + catalog save only.
    Phase 2: Install, load/unload, dynamic lifecycle, idle timeout,
             health check, usage tracking via proxy callback.
    """

    def __init__(self, catalog: ToolCatalog, lifecycle: LifecycleManager | None = None):
        self._catalog = catalog
        self._lifecycle = lifecycle

    # ── Discovery pipeline ─────────────────────────────────────────

    async def discover_and_save(
        self,
        query: str = "mcp-server",
        sources: list[str] | None = None,
    ) -> list[dict]:
        """Search external sources, evaluate, save to catalog, return results."""
        results = await search_all(query, sources)
        saved = []
        for item in results:
            item["quality_score"] = QualityScorer.evaluate(item)
            try:
                self._catalog.add_tool(item)
                saved.append(item)
            except Exception as e:
                logger.warning(
                    "save_discovered_failed",
                    name=item.get("name"),
                    error=str(e),
                )
        logger.info(
            "discover_and_save_complete",
            query=query,
            total=len(results),
            saved=len(saved),
        )
        return saved

    # ── Full pipeline: discover → install → load ────────────────────

    async def discover_install_load(
        self,
        query: str = "mcp-server",
        sources: list[str] | None = None,
        auto_load: bool = True,
    ) -> dict:
        """Discover, evaluate, install (status only), and optionally load tools.

        Phase 2 full pipeline:
        1. Search external sources (GitHub + registry)
        2. Evaluate and save to catalog
        3. Mark as installed (status transition)
        4. Optionally load via LifecycleManager

        Args:
            query: Search query for external sources.
            sources: Source names (default: all).
            auto_load: If True, automatically load newly discovered tools.

        Returns:
            Dict with ``discovered``, ``installed``, ``loaded`` counts
            and ``tool_names`` list.
        """
        discovered = await self.discover_and_save(query, sources)

        installed_count = 0
        loaded_count = 0
        tool_names: list[str] = []

        for tool in discovered:
            tool_id = tool.get("id") or tool.get("name", "")
            tool_name = tool.get("name", tool_id)
            if not tool_id:
                continue
            tool_names.append(tool_name)

            # Install: mark as installed in catalog
            self._catalog.update_status(tool_id, "installed")
            installed_count += 1

            # Auto-load if requested and lifecycle is available
            if auto_load and self._lifecycle:
                ok = await self._lifecycle.load_tool(tool_id)
                if ok:
                    loaded_count += 1

        logger.info(
            "discover_install_load_complete",
            query=query,
            discovered=len(discovered),
            installed=installed_count,
            loaded=loaded_count,
        )

        return {
            "discovered": len(discovered),
            "installed": installed_count,
            "loaded": loaded_count,
            "tool_names": tool_names,
        }

    # ── Install pipeline ───────────────────────────────────────────

    async def install_tool(self, name: str) -> tuple[bool, str]:
        """Install a discovered tool.

        Phase 2: updates status to 'installed' in catalog.

        Args:
            name: Tool name or ID.

        Returns:
            (success, message) tuple.
        """
        tool = self._catalog.get_tool(name)
        if not tool:
            return False, f"Tool '{name}' not found in catalog. Use discover first."

        current = tool.get("status", "")
        if current in ("installed", "loaded"):
            return True, f"Tool '{name}' already {current}."

        self._catalog.update_status(name, "installed")
        return True, f"Tool '{name}' marked as installed."

    # ── Load/unload pipeline ───────────────────────────────────────

    async def ensure_tool_available(self, name: str) -> tuple[bool, str]:
        """Check if a tool is available, loading it if necessary.

        Phase 2: uses LifecycleManager for dynamic loading.

        Returns (available, status_message).
        """
        tool = self._catalog.get_tool(name)
        if not tool:
            return False, f"Tool '{name}' not found in catalog"

        if tool.get("status") == "loaded":
            return True, f"Tool '{name}' is loaded and ready"

        if tool.get("status") in ("idle", "installed") and self._lifecycle:
            ok = await self._lifecycle.load_tool(name)
            if ok:
                return True, f"Tool '{name}' loaded"
            return False, f"Failed to load tool '{name}'"

        return (
            False,
            f"Tool '{name}' status: {tool.get('status', 'unknown')}. Use 'install' first.",
        )

    async def load_tool(self, name: str) -> tuple[bool, str]:
        """Load a tool via the LifecycleManager.

        Args:
            name: Tool name or ID.

        Returns:
            (success, message) tuple.
        """
        if not self._lifecycle:
            return False, "LifecycleManager not configured (no proxy manager)."

        ok = await self._lifecycle.load_tool(name)
        if ok:
            return True, f"Tool '{name}' loaded."
        return False, f"Failed to load tool '{name}'. Check the tool status."

    async def unload_tool(self, name: str) -> tuple[bool, str]:
        """Unload a tool via the LifecycleManager.

        Args:
            name: Tool name or ID.

        Returns:
            (success, message) tuple.
        """
        if not self._lifecycle:
            return False, "LifecycleManager not configured (no proxy manager)."

        ok = await self._lifecycle.unload_tool(name)
        if ok:
            return True, f"Tool '{name}' unloaded."
        return False, f"Failed to unload tool '{name}'."

    async def reload_tool(self, name: str) -> tuple[bool, str]:
        """Reload a tool: unload then load.

        Useful for reconnection after configuration changes or error recovery.
        If the proxy connection for this tool is stale or broken, the reload
        will force a clean disconnect before reconnecting.

        Args:
            name: Tool name or ID.

        Returns:
            (success, message) tuple.
        """
        unload_ok, unload_msg = await self.unload_tool(name)
        if not unload_ok and "not configured" not in unload_msg:
            logger.warning("reload_unload_issue", name=name, msg=unload_msg)

        # self.unload_tool() above already delegates to self._lifecycle.unload_tool()
        # if configured, so a second direct call is redundant.
        load_ok, load_msg = await self.load_tool(name)
        if load_ok:
            return True, f"Tool '{name}' reloaded."
        return False, f"Failed to reload tool '{name}': {load_msg}"

    async def load_all_idle(self) -> int:
        """Load all idle tools into the proxy."""
        if not self._lifecycle:
            logger.warning("load_all_idle_no_lifecycle")
            return 0
        return await self._lifecycle.load_by_status("idle")

    async def unload_all_loaded(self) -> int:
        """Unload all currently loaded tools."""
        if not self._lifecycle:
            logger.warning("unload_all_no_lifecycle")
            return 0
        return await self._lifecycle.unload_by_status("loaded")

    # ── Lifecycle control ──────────────────────────────────────────

    async def start_idle_watch(self):
        """Start the idle timeout background watcher."""
        if self._lifecycle:
            await self._lifecycle.start_idle_watch()

    async def stop_idle_watch(self):
        """Stop the idle timeout background watcher."""
        if self._lifecycle:
            await self._lifecycle.stop_idle_watch()

    async def start_health_watch(self):
        """Start the health check background watcher."""
        if self._lifecycle:
            await self._lifecycle.start_health_watch()

    async def stop_health_watch(self):
        """Stop the health check background watcher."""
        if self._lifecycle:
            await self._lifecycle.stop_health_watch()

    # ── Status reporting ───────────────────────────────────────────

    def get_status(self) -> dict:
        """Return the current status of the lifecycle and catalog.

        Returns a combined status dict from LifecycleManager and
        catalog counts.
        """
        status: dict = {
            "catalog": {"total": 0, "by_status": {}},
        }

        if self._lifecycle:
            status["lifecycle"] = self._lifecycle.get_status()

        by_status = self._catalog.count_by_status()
        status["catalog"]["by_status"] = by_status
        status["catalog"]["total"] = sum(by_status.values())

        return status

    # ── Usage tracking ─────────────────────────────────────────────

    async def record_usage(self, tool_id: str):
        """Record tool usage, refreshing its idle timeout."""
        if self._lifecycle:
            await self._lifecycle.record_usage(tool_id)
        else:
            self._catalog.record_usage(tool_id)

    # ── Cleanup ────────────────────────────────────────────────────

    async def close(self):
        """Shutdown: close lifecycle (stops watches, unloads all) and close catalog."""
        if self._lifecycle:
            await self._lifecycle.close()
        if self._catalog:
            self._catalog.close()
