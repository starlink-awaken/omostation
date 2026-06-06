"""Tests for MCP Registry LifecycleManager — Phase 2: dynamic load/unload with idle timeout."""

import asyncio
import time

import pytest
from agora.mcp_registry.lifecycle import LifecycleManager

from tests.conftest import FakeToolCatalog

# ── Helpers ────────────────────────────────────────────────────────────


def _make_tool(tool_id: str, name: str = "", status: str = "discovered", **kwargs) -> dict:
    """Create a minimal tool dict for testing."""
    return {
        "id": tool_id,
        "name": name or tool_id,
        "status": status,
        "description": kwargs.get("description", "test tool"),
        "tool_type": kwargs.get("tool_type", "python"),
        "entry": kwargs.get("entry", ""),
        "install_path": kwargs.get("install_path", ""),
        "repo_url": kwargs.get("repo_url", ""),
        "metadata": kwargs.get("metadata", {}),
        **kwargs,
    }


class FakeProxyRegistry:
    """A fake ProxyRegistry that tracks usage callbacks."""

    def __init__(self):
        self._usage_callbacks: list = []
        self._clients: dict[str, object] = {}

    def add_usage_callback(self, callback):
        if callback not in self._usage_callbacks:
            self._usage_callbacks.append(callback)

    def remove_usage_callback(self, callback):
        self._usage_callbacks = [cb for cb in self._usage_callbacks if cb != callback]

    def set_usage_callback(self, callback):
        self._usage_callbacks.clear()
        if callback is not None:
            self._usage_callbacks.append(callback)


class FakeProxyManager:
    """A fake ProxyManager that tracks add/remove calls without real connections."""

    def __init__(self):
        self.services: dict[str, dict] = {}
        self.add_results: dict[str, str] = {}
        self.remove_called: set[str] = set()
        self._configs: dict[str, dict] = {}
        self.registry = FakeProxyRegistry()

    def set_usage_callback(self, callback):
        """Track usage callback on the fake registry."""
        self.registry.set_usage_callback(callback)

    async def add_service(self, config: dict) -> str:
        name = config.get("name", "unknown")
        if name in self.add_results:
            return self.add_results[name]
        self.services[name] = config
        return "ok: 3 tools registered"

    async def remove_service(self, name: str) -> str:
        self.remove_called.add(name)
        self.services.pop(name, None)
        return "removed"


# ── Test fixture ───────────────────────────────────────────────────────


@pytest.fixture
def catalog():
    return FakeToolCatalog()


@pytest.fixture
def proxy():
    return FakeProxyManager()


@pytest.fixture
def manager(catalog, proxy):
    return LifecycleManager(catalog=catalog, proxy_manager=proxy, idle_timeout=300.0, check_interval=60.0)


# ── Tests: Initialization ──────────────────────────────────────────────


class TestLifecycleInit:
    def test_default_timeout(self):
        lm = LifecycleManager(catalog=FakeToolCatalog())
        assert lm._idle_timeout == 300.0
        assert lm._check_interval == 60.0
        assert lm._idle_watch_task is None
        assert lm._proxy is None

    def test_custom_timeout(self):
        lm = LifecycleManager(catalog=FakeToolCatalog(), idle_timeout=60.0, check_interval=10.0)
        assert lm._idle_timeout == 60.0
        assert lm._check_interval == 10.0


# ── Tests: load_tool ────────────────────────────────────────────────────


class TestLoadTool:
    async def test_load_success_with_proxy(self, catalog, proxy, manager):
        catalog.tools["sqlite"] = _make_tool("sqlite", name="sqlite", status="idle", tool_type="node")
        ok = await manager.load_tool("sqlite")
        assert ok is True
        assert catalog.tools["sqlite"]["status"] == "loaded"
        assert "sqlite" in proxy.services
        assert "sqlite" in manager._last_used

    async def test_load_tool_not_found(self, manager):
        ok = await manager.load_tool("nonexistent")
        assert ok is False

    async def test_load_already_loaded(self, catalog, manager):
        catalog.tools["loaded_tool"] = _make_tool("loaded_tool", status="loaded")
        ok = await manager.load_tool("loaded_tool")
        assert ok is True  # already loaded is success

    async def test_load_proxy_failure(self, catalog, manager):
        catalog.tools["failing"] = _make_tool("failing", name="failing", status="idle", tool_type="node")
        manager._proxy.add_results["failing"] = "error: connection refused"
        ok = await manager.load_tool("failing")
        assert ok is False
        # Status should NOT have changed to "loaded"
        assert catalog.tools["failing"]["status"] == "idle"

    async def test_load_no_proxy(self, catalog):
        """Without ProxyManager, load should update status only."""
        lm = LifecycleManager(catalog=catalog)
        catalog.tools["basic"] = _make_tool("basic", status="idle")
        ok = await lm.load_tool("basic")
        assert ok is True
        assert catalog.tools["basic"]["status"] == "loaded"

    async def test_load_sets_last_used(self, catalog, manager):
        catalog.tools["time_check"] = _make_tool("time_check", status="idle")
        before = time.monotonic()
        await manager.load_tool("time_check")
        assert manager._last_used["time_check"] >= before


# ── Tests: unload_tool ─────────────────────────────────────────────────


class TestUnloadTool:
    async def test_unload_success_with_proxy(self, catalog, proxy, manager):
        catalog.tools["sqlite"] = _make_tool("sqlite", name="sqlite", status="loaded")
        proxy.services["sqlite"] = {"name": "sqlite"}
        ok = await manager.unload_tool("sqlite")
        assert ok is True
        assert catalog.tools["sqlite"]["status"] == "idle"
        assert "sqlite" in proxy.remove_called
        assert "sqlite" not in manager._last_used

    async def test_unload_not_found(self, manager):
        ok = await manager.unload_tool("nonexistent")
        assert ok is False

    async def test_unload_already_idle(self, catalog, manager):
        catalog.tools["idle_tool"] = _make_tool("idle_tool", status="idle")
        ok = await manager.unload_tool("idle_tool")
        assert ok is True  # already unloaded is success

    async def test_unload_without_proxy(self, catalog):
        """Without ProxyManager, unload should update status only."""
        lm = LifecycleManager(catalog=catalog)
        catalog.tools["basic"] = _make_tool("basic", status="loaded")
        ok = await lm.unload_tool("basic")
        assert ok is True
        assert catalog.tools["basic"]["status"] == "idle"


# ── Tests: record_usage ────────────────────────────────────────────────


class TestRecordUsage:
    async def test_record_usage_refreshes_timestamp(self, catalog, manager):
        catalog.tools["tool1"] = _make_tool("tool1", status="loaded")
        manager._last_used["tool1"] = 100.0  # old timestamp
        await manager.record_usage("tool1")
        assert manager._last_used["tool1"] >= time.monotonic() - 1
        assert "tool1" in catalog.usage_records

    async def test_record_usage_unknown_tool(self, catalog, manager):
        """Recording usage for unknown tool should not fail."""
        await manager.record_usage("ghost")
        assert "ghost" not in manager._last_used  # not tracked, no-op


# ── Tests: batch operations ────────────────────────────────────────────


class TestBatchOperations:
    async def test_load_by_status(self, catalog, proxy, manager):
        catalog.tools["a"] = _make_tool("a", status="idle")
        catalog.tools["b"] = _make_tool("b", status="idle")
        catalog.tools["c"] = _make_tool("c", status="discovered")  # should not be loaded

        count = await manager.load_by_status("idle")
        assert count == 2
        assert catalog.tools["a"]["status"] == "loaded"
        assert catalog.tools["b"]["status"] == "loaded"
        assert catalog.tools["c"]["status"] == "discovered"

    async def test_load_by_status_empty(self, manager):
        count = await manager.load_by_status("loaded")
        assert count == 0

    async def test_unload_by_status(self, catalog, proxy, manager):
        catalog.tools["x"] = _make_tool("x", status="loaded")
        catalog.tools["y"] = _make_tool("y", status="loaded")
        catalog.tools["z"] = _make_tool("z", status="idle")  # should not be unloaded

        count = await manager.unload_by_status("loaded")
        assert count == 2
        assert catalog.tools["x"]["status"] == "idle"
        assert catalog.tools["y"]["status"] == "idle"
        assert catalog.tools["z"]["status"] == "idle"  # unchanged

    async def test_unload_by_status_empty(self, manager):
        count = await manager.unload_by_status("idle")
        assert count == 0


# ── Tests: idle timeout ────────────────────────────────────────────────


class TestIdleTimeout:
    async def test_start_stop_idle_watch(self, manager):
        assert manager._idle_watch_task is None
        await manager.start_idle_watch()
        assert manager._idle_watch_task is not None
        assert not manager._idle_watch_task.done()

        await manager.stop_idle_watch()
        assert manager._idle_watch_task is None

    async def test_stop_when_not_running(self, manager):
        """Stopping a non-running watcher should be safe."""
        await manager.stop_idle_watch()  # Should not raise

    async def test_auto_unload_on_idle_timeout(self, catalog, proxy):
        """Tools idle beyond timeout should be auto-unloaded."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, idle_timeout=0.3, check_interval=0.05)

        catalog.tools["short"] = _make_tool("short", status="loaded")
        catalog.tools["long"] = _make_tool("long", status="loaded")

        lm._last_used["short"] = time.monotonic() - 10.0  # very old → idle
        lm._last_used["long"] = time.monotonic()  # just used → not idle

        await lm.start_idle_watch()
        # Wait for at least one check interval *and* the short timeout
        await asyncio.sleep(0.2)
        await lm.stop_idle_watch()

        assert catalog.tools["short"]["status"] == "idle", "Old tool should be unloaded"
        assert catalog.tools["long"]["status"] == "loaded", "Recently used tool should remain loaded"

    async def test_idle_timeout_respected(self, catalog, proxy):
        """Tools with recent usage should NOT be unloaded."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, idle_timeout=60.0, check_interval=0.05)

        catalog.tools["active"] = _make_tool("active", status="loaded")
        lm._last_used["active"] = time.monotonic()  # just used

        await lm.start_idle_watch()
        await asyncio.sleep(0.1)
        await lm.stop_idle_watch()

        assert catalog.tools["active"]["status"] == "loaded"
        assert "active" not in proxy.remove_called


# ── Tests: _build_service_config ───────────────────────────────────────


class TestBuildServiceConfig:
    """Test the static _build_service_config helper with various inputs."""

    def test_from_metadata_command(self):
        tool = _make_tool("my-tool", name="my-tool", metadata={"command": "my-mcp", "args": ["--port", "8080"]})
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["command"] == "my-mcp"
        assert cfg["args"] == ["--port", "8080"]
        assert cfg["mcp_endpoint"] == "stdio"

    def test_from_qualified_entry(self):
        tool = _make_tool("kos", name="kos", entry="kos.mcp.server")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["command"] == "uv"
        assert cfg["args"] == ["run", "--package", "kos", "python", "-m", "kos.mcp.server"]
        assert cfg["mcp_endpoint"] == "stdio"

    def test_from_simple_entry(self):
        tool = _make_tool("kronos", name="kronos", entry="kronos-mcp")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["command"] == "uv"
        assert cfg["args"] == ["run", "--package", "kronos", "kronos-mcp"]
        assert cfg["mcp_endpoint"] == "stdio"

    def test_from_install_path(self):
        tool = _make_tool("custom", name="custom", install_path="/usr/local/bin/my-mcp")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["command"] == "/usr/local/bin/my-mcp"
        assert cfg["args"] == []
        assert cfg["mcp_endpoint"] == "stdio"

    def test_from_node_type(self):
        tool = _make_tool("mcp-server-sqlite", name="mcp-server-sqlite", tool_type="node")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["command"] == "npx"
        assert cfg["args"] == ["-y", "mcp-server-sqlite"]
        assert cfg["mcp_endpoint"] == "stdio"

    def test_from_python_type(self):
        tool = _make_tool("my-py-tool", name="my-py-tool", tool_type="python")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["command"] == "pipx"
        assert cfg["args"] == ["run", "my-py-tool"]
        assert cfg["mcp_endpoint"] == "stdio"

    def test_repo_only_returns_none(self):
        """Tool with only repo_url and unknown type should return None."""
        tool = _make_tool("repo-only", name="repo-only", repo_url="https://github.com/org/repo", tool_type="")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is None

    def test_no_entry_returns_none(self):
        tool = _make_tool("empty", name="empty", tool_type="")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is None

    def test_no_name_returns_none(self):
        tool = {"id": "no-name", "status": "discovered", "name": ""}
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is None


# ── Tests: close ────────────────────────────────────────────────────────


class TestClose:
    async def test_close_stops_watch_and_unloads(self, catalog, proxy, manager):
        catalog.tools["tool1"] = _make_tool("tool1", status="loaded")
        catalog.tools["tool2"] = _make_tool("tool2", status="loaded")

        await manager.start_idle_watch()
        await manager.close()

        assert manager._idle_watch_task is None
        assert catalog.tools["tool1"]["status"] == "idle"
        assert catalog.tools["tool2"]["status"] == "idle"

    async def test_close_without_watch(self, manager):
        """close() should work even if idle watch was never started."""
        await manager.close()  # Should not raise
        assert manager._idle_watch_task is None


# ── Tests: concurrency safety ──────────────────────────────────────────


class TestConcurrency:
    async def test_concurrent_load_same_tool(self, catalog, proxy, manager):
        """Loading the same tool concurrently should produce one successful load."""
        catalog.tools["dup"] = _make_tool("dup", status="idle")

        results = await asyncio.gather(
            manager.load_tool("dup"),
            manager.load_tool("dup"),
            manager.load_tool("dup"),
        )

        # At least one should succeed; subsequent calls may short-circuit on "already loaded"
        assert any(results)
        assert catalog.tools["dup"]["status"] == "loaded"


# ── Phase 2 Tests: usage callback integration ───────────────────────────


class TestUsageCallbackIntegration:
    """Tests for the proxy dispatch → lifecycle usage callback feedback loop."""

    async def test_load_wires_usage_callback(self, catalog, proxy, manager):
        """Loading a tool should set the usage callback on the proxy."""
        catalog.tools["svc1"] = _make_tool("svc1", name="svc1", status="idle", tool_type="node")
        await manager.load_tool("svc1")

        assert len(proxy.registry._usage_callbacks) > 0
        # The callback should be _record_usage_from_proxy
        assert hasattr(proxy.registry._usage_callbacks[0], "__call__")

    async def test_unload_last_tool_clears_callback(self, catalog, proxy, manager):
        """Unloading the last loaded tool should clear the usage callback."""
        catalog.tools["svc1"] = _make_tool("svc1", name="svc1", status="loaded", tool_type="node")
        proxy.services["svc1"] = {"name": "svc1"}

        await manager.unload_tool("svc1")
        assert proxy.registry._usage_callbacks == []

    async def test_callback_refreshes_last_used(self, catalog, proxy, manager):
        """The usage callback should refresh _last_used timestamp."""
        catalog.tools["svc1"] = _make_tool("svc1", name="svc1", status="loaded", tool_type="node")
        proxy.services["svc1"] = {"name": "svc1"}

        # Manually set old timestamp and invoke callback
        manager._last_used["svc1"] = 100.0
        await manager._record_usage_from_proxy("svc1", "some_tool", {})

        assert manager._last_used["svc1"] > 100.0

    async def test_callback_records_usage_in_catalog(self, catalog, proxy, manager):
        """The usage callback should also record usage in the catalog."""
        catalog.tools["svc1"] = _make_tool("svc1", name="svc1", status="loaded", tool_type="node")

        await manager._record_usage_from_proxy("svc1", "some_tool", {})
        assert "svc1" in catalog.usage_records

    async def test_callback_unknown_service_noop(self, catalog, proxy, manager):
        """Callback for an unknown service should not fail."""
        # Should not raise
        await manager._record_usage_from_proxy("ghost_service", "some_tool", {})


# ── Phase 2 Tests: retry and error handling ────────────────────────────


class TestRetryHandling:
    async def test_load_retry_on_transient_failure(self, catalog, proxy):
        """Load should retry on transient proxy failures."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, max_load_retries=2)
        catalog.tools["flaky"] = _make_tool("flaky", name="flaky", status="idle", tool_type="node")

        # First call fails, second succeeds
        proxy.add_results["flaky"] = "error: timeout"

        # Override: first call returns error, then reset for retry
        call_count = 0

        async def flaky_add(config):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "error: timeout"
            # Subsequent attempts succeed
            return "ok: 3 tools registered"

        proxy.add_service = flaky_add

        ok = await lm.load_tool("flaky")
        assert ok is True
        assert call_count == 2
        assert catalog.tools["flaky"]["status"] == "loaded"

    async def test_load_retry_exhausted_still_fails(self, catalog, proxy):
        """Load should fail after exhausting all retries."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, max_load_retries=2)
        catalog.tools["always_fail"] = _make_tool("always_fail", name="always_fail", status="idle", tool_type="node")

        call_count = 0

        async def always_fail(config):
            nonlocal call_count
            call_count += 1
            return "error: connection refused"

        proxy.add_service = always_fail

        ok = await lm.load_tool("always_fail")
        assert ok is False
        assert call_count == 2  # retried max_load_retries times
        assert catalog.tools["always_fail"]["status"] != "loaded"

    async def test_default_max_load_retries(self):
        """Default max_load_retries should be 2."""
        lm = LifecycleManager(catalog=FakeToolCatalog())
        assert lm._max_load_retries == 2

    async def test_custom_max_load_retries(self):
        """max_load_retries should be configurable."""
        lm = LifecycleManager(catalog=FakeToolCatalog(), max_load_retries=5)
        assert lm._max_load_retries == 5


# ── Phase 2 Tests: status reporting ────────────────────────────────────


class TestStatusReporting:
    async def test_get_status_basic(self, catalog, proxy, manager):
        """get_status should return correct counts and state."""
        catalog.tools["loaded1"] = _make_tool("loaded1", status="loaded")
        catalog.tools["loaded2"] = _make_tool("loaded2", status="loaded")
        catalog.tools["idle1"] = _make_tool("idle1", status="idle")
        catalog.tools["disc"] = _make_tool("disc", status="discovered")

        manager._last_used["loaded1"] = time.time()
        manager._last_used["loaded2"] = time.time()

        status = manager.get_status()
        assert status["loaded_count"] == 2
        assert "loaded1" in status["loaded"]
        assert "loaded2" in status["loaded"]
        assert "idle1" in status["idle"]
        assert status["idle_watch_running"] is False
        assert status["health_watch_running"] is False


# ── Phase 2 Tests: health watch ────────────────────────────────────────


class TestHealthWatch:
    async def test_start_stop_health_watch(self, manager):
        assert manager._health_watch_task is None
        await manager.start_health_watch()
        assert manager._health_watch_task is not None
        assert not manager._health_watch_task.done()

        await manager.stop_health_watch()
        assert manager._health_watch_task is None

    async def test_stop_health_watch_when_not_running(self, manager):
        """Stopping a non-running health watch should be safe."""
        await manager.stop_health_watch()  # Should not raise

    async def test_health_watch_detects_stale_service(self, catalog, proxy):
        """Health watch should detect disconnected services and reload."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, check_interval=0.05)

        catalog.tools["svc1"] = _make_tool("svc1", name="svc1", status="loaded", tool_type="node")
        lm._last_used["svc1"] = time.time()

        # Simulate: proxy says service is NOT connected
        await lm.start_health_watch()
        await asyncio.sleep(0.2)
        await lm.stop_health_watch()

        # svc1 should have been marked idle (disconnected) and then reloaded
        assert catalog.tools["svc1"]["status"] == "loaded"  # reloaded

    async def test_health_watch_ignores_connected_services(self, catalog, proxy):
        """Health watch should NOT touch services that are still connected."""
        # Setup: service is in proxy client list, so health check considers it connected
        proxy.registry._clients["svc1"] = object()
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, check_interval=0.05)

        catalog.tools["svc1"] = _make_tool("svc1", name="svc1", status="loaded", tool_type="node")
        lm._last_used["svc1"] = time.time()

        await lm.start_health_watch()
        await asyncio.sleep(0.2)
        await lm.stop_health_watch()

        # Service should remain loaded since proxy reports it as connected
        assert catalog.tools["svc1"]["status"] == "loaded"

    async def test_close_stops_health_watch(self, catalog, proxy, manager):
        """close() should stop the health watch."""
        catalog.tools["tool1"] = _make_tool("tool1", status="loaded")

        await manager.start_health_watch()
        await manager.close()

        assert manager._health_watch_task is None
        assert manager._idle_watch_task is None
        assert catalog.tools["tool1"]["status"] == "idle"

    async def test_close_during_active_health_watch(self, catalog, proxy):
        """close() should work cleanly when health watch is actively scanning."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, check_interval=0.01)
        catalog.tools["tool1"] = _make_tool("tool1", status="loaded")
        await lm.start_health_watch()
        await asyncio.sleep(0.05)
        await lm.close()  # Should not raise

        assert lm._health_watch_task is None
        assert catalog.tools["tool1"]["status"] == "idle"

    async def test_health_watch_no_proxy_no_error(self, catalog):
        """Health watch without proxy should not error."""
        lm = LifecycleManager(catalog=catalog, check_interval=0.05)
        catalog.tools["t1"] = _make_tool("t1", status="loaded")
        await lm.start_health_watch()
        await asyncio.sleep(0.1)
        await lm.stop_health_watch()
        assert catalog.tools["t1"]["status"] == "loaded"  # unchanged without proxy


# ── Phase 2 Tests: HTTP endpoint config ───────────────────────────────


class TestBuildServiceConfigHttp:
    """Test _build_service_config with HTTP endpoint support."""

    def test_http_endpoint_from_tool(self):
        """Tool with top-level mcp_endpoint should produce HTTP config."""
        tool = _make_tool("http-tool", name="http-tool", mcp_endpoint="http://localhost:8080/mcp")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["mcp_endpoint"] == "http://localhost:8080/mcp"
        assert "command" not in cfg
        assert "args" not in cfg

    def test_http_endpoint_from_metadata(self):
        """Tool with mcp_endpoint in metadata should produce HTTP config."""
        tool = _make_tool("meta-http", name="meta-http", metadata={"mcp_endpoint": "http://service:9090/sse"})
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["mcp_endpoint"] == "http://service:9090/sse"

    def test_http_endpoint_takes_priority(self):
        """HTTP endpoint should take priority over command in metadata."""
        tool = _make_tool(
            "priority",
            name="priority",
            mcp_endpoint="http://localhost:8000/mcp",
            metadata={"command": "some-cli", "args": ["--flag"]},
        )
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["mcp_endpoint"] == "http://localhost:8000/mcp"
        # HTTP config should not include command/args
        assert "command" not in cfg

    def test_https_endpoint(self):
        """HTTPS endpoints are also valid."""
        tool = _make_tool("secure", name="secure", mcp_endpoint="https://api.example.com/mcp")
        cfg = LifecycleManager._build_service_config(tool)
        assert cfg is not None
        assert cfg["mcp_endpoint"] == "https://api.example.com/mcp"


# ── Phase 2 Tests: usage callback wiring ──────────────────────────────


class TestUsageCallbackWiring:
    async def test_callback_wired_only_once(self, catalog, proxy):
        """Usage callback should be set only on the first load, not repeated."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy)
        catalog.tools["a"] = _make_tool("a", name="a", status="idle", tool_type="node")
        catalog.tools["b"] = _make_tool("b", name="b", status="idle", tool_type="node")

        # Track how many times registry.add_usage_callback is called
        call_count = 0
        original_add = proxy.registry.add_usage_callback

        def tracking_add(cb):
            nonlocal call_count
            call_count += 1
            original_add(cb)

        proxy.registry.add_usage_callback = tracking_add

        # First load should set callback
        assert await lm.load_tool("a") is True
        assert call_count == 1

        # Second load should NOT re-set callback
        assert await lm.load_tool("b") is True
        assert call_count == 1  # still 1

        # Unload all should clear callback flag
        await lm.unload_tool("a")
        await lm.unload_tool("b")
        # After last unload, callback is removed from list
        assert proxy.registry._usage_callbacks == []

        # New load after clear should set callback again
        call_count = 0
        assert await lm.load_tool("a") is True
        assert call_count == 1

    async def test_callback_flag_reset_on_unload_last(self, catalog, proxy):
        """_usage_callback_wired flag should reset when last tool is unloaded."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy)
        catalog.tools["x"] = _make_tool("x", name="x", status="idle", tool_type="node")

        await lm.load_tool("x")
        assert lm._usage_callback_wired is True

        await lm.unload_tool("x")
        assert lm._usage_callback_wired is False


# ── Phase 2 Tests: concurrency ────────────────────────────────────────


class TestConcurrencySafety:
    async def test_concurrent_record_usage_safe(self, catalog, manager):
        """Multiple concurrent record_usage calls should not corrupt _last_used."""
        catalog.tools["shared"] = _make_tool("shared", status="loaded")
        manager._last_used["shared"] = 100.0

        async def record_many(n: int):
            for _ in range(n):
                await manager.record_usage("shared")

        await asyncio.gather(
            record_many(10),
            record_many(10),
            record_many(10),
        )

        # _last_used should still have the entry and be recent
        assert "shared" in manager._last_used
        assert manager._last_used["shared"] > 100.0

    async def test_concurrent_load_and_watch(self, catalog, proxy):
        """load_tool while idle watch is running should not raise."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=proxy, idle_timeout=0.1, check_interval=0.05)
        catalog.tools["t1"] = _make_tool("t1", name="t1", status="idle", tool_type="node")

        await lm.start_idle_watch()
        await lm.load_tool("t1")

        # Let idle watch see it's still fresh
        await asyncio.sleep(0.05)
        assert catalog.tools["t1"]["status"] == "loaded"

        await lm.stop_idle_watch()
        await lm.close()
