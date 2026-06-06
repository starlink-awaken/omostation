"""Tests for Phase 2: dynamic load/unload, lazy reconnect, and idle timeout."""

import asyncio
from unittest.mock import patch

from agora.mcp_proxy.client import MCPClient
from agora.mcp_proxy.idle_timeout import IdleTimeoutConfig, IdleTimeoutManager
from agora.mcp_proxy.manager import ProxyManager
from agora.mcp_proxy.registry import ProxyRegistry

# ── Helpers ─────────────────────────────────────────────────────────


class _FakeMCPClient(MCPClient):
    """A fake MCP client that simulates a connected downstream service."""

    def __init__(self, service_name: str, tools: list[dict] | None = None):
        super().__init__(service_name)
        self._tools = tools or [
            {"name": "ping", "description": "Ping tool", "inputSchema": {"type": "object", "properties": {}}},
            {
                "name": "echo",
                "description": "Echo tool",
                "inputSchema": {"type": "object", "properties": {"msg": {"type": "string"}}},
            },
        ]
        self._connected = False
        self.connect_call_count = 0
        self.disconnect_call_count = 0
        self.call_tool_results: dict[str, dict] = {}

    async def connect(self) -> bool:
        self.connect_call_count += 1
        self._connected = True
        return True

    async def disconnect(self):
        self.disconnect_call_count += 1
        self._connected = False

    async def list_tools(self) -> list[dict]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict):
        if name in self.call_tool_results:
            return self.call_tool_results[name]
        return {"status": "ok", "data": f"{name} called with {arguments}"}

    async def list_resources(self) -> list[dict]:
        return []

    async def read_resource(self, uri: str) -> str | bytes:
        return ""


def _make_registry() -> ProxyRegistry:
    return ProxyRegistry()


def _make_manager() -> ProxyManager:
    return ProxyManager()


# ═════════════════════════════════════════════════════════════════════
# IdleTimeoutManager Tests
# ═════════════════════════════════════════════════════════════════════


class TestIdleTimeoutConfig:
    def test_default_timeout(self):
        cfg = IdleTimeoutConfig()
        assert cfg.default_timeout == 300.0
        assert cfg.sweep_interval == 60.0

    def test_get_timeout_default(self):
        cfg = IdleTimeoutConfig(default_timeout=120.0)
        assert cfg.get_timeout("any_service") == 120.0

    def test_get_timeout_per_service(self):
        cfg = IdleTimeoutConfig(
            default_timeout=300.0,
            per_service_timeout={"kos": 60.0, "iris": 120.0},
        )
        assert cfg.get_timeout("kos") == 60.0
        assert cfg.get_timeout("iris") == 120.0
        assert cfg.get_timeout("eidos") == 300.0  # falls back to default


class TestIdleTimeoutManager:
    def test_initial_state(self):
        manager = IdleTimeoutManager()
        assert manager.last_used == {}
        assert manager.config.sweep_interval == 60.0

    def test_refresh_records_timestamp(self):
        manager = IdleTimeoutManager()
        manager.refresh("kos")
        assert "kos" in manager.last_used
        assert manager.last_used["kos"] > 0

    def test_mark_unloaded_removes_tracking(self):
        manager = IdleTimeoutManager()
        manager.refresh("kos")
        assert "kos" in manager.last_used
        manager.mark_unloaded("kos")
        assert "kos" not in manager.last_used

    def test_idle_services_empty_when_recently_used(self):
        manager = IdleTimeoutManager(config=IdleTimeoutConfig(default_timeout=60.0))
        manager.refresh("kos")
        # now=0, last_used ≈ time.monotonic() which is >> 0, so idle_services returns []
        idle = manager.idle_services(now=0.0)
        assert idle == []

    def test_idle_services_detects_expired(self):
        manager = IdleTimeoutManager(config=IdleTimeoutConfig(default_timeout=10.0))
        # Use a known old timestamp
        manager._last_used["zombie"] = 0.0
        manager._last_used["active"] = 100.0

        idle = manager.idle_services(now=20.0)
        assert "zombie" in idle
        assert "active" not in idle

    def test_idle_services_respects_per_service_timeout(self):
        cfg = IdleTimeoutConfig(
            default_timeout=100.0,
            per_service_timeout={"fast-timeout": 5.0},
        )
        manager = IdleTimeoutManager(config=cfg)
        manager._last_used["fast-timeout"] = 0.0
        manager._last_used["normal"] = 0.0

        idle = manager.idle_services(now=10.0)
        assert "fast-timeout" in idle
        assert "normal" not in idle  # 100s default not yet expired

    def test_start_stop_lifecycle(self):
        async def _run():
            manager = IdleTimeoutManager()
            assert manager._sweep_task is None

            manager.start()
            assert manager._sweep_task is not None
            assert not manager._sweep_task.done()

            await manager.stop()
            assert manager._sweep_task is None  # cleared after stop

        asyncio.run(_run())

    def test_double_start_is_noop(self):
        async def _run():
            manager = IdleTimeoutManager()
            manager.start()
            task1 = manager._sweep_task
            manager.start()  # second start should be no-op
            assert manager._sweep_task is task1
            await manager.stop()

        asyncio.run(_run())

    def test_sweep_once_invokes_on_idle(self):
        """_sweep_once should invoke on_idle for idle services."""

        async def _run():
            unloaded = []

            async def on_idle(name: str):
                unloaded.append(name)

            manager = IdleTimeoutManager(
                config=IdleTimeoutConfig(default_timeout=5.0),
                on_idle=on_idle,
            )
            manager._last_used["zombie"] = 0.0
            manager._last_used["active"] = 100.0

            await manager._sweep_once(now=50.0)
            assert "zombie" in unloaded
            assert "active" not in unloaded
            assert "zombie" not in manager._last_used  # cleaned up

        asyncio.run(_run())

    def test_sweep_once_no_callback_no_error(self):
        """_sweep_once should not raise if on_idle is None."""
        manager = IdleTimeoutManager()
        manager._last_used["zombie"] = 0.0
        # Should not raise
        asyncio.run(manager._sweep_once())

    def test_sweep_once_callback_error_logged(self):
        """_sweep_once should catch and log callback errors, not raise."""

        async def failing_cb(name: str):
            raise RuntimeError(f"oops: {name}")

        manager = IdleTimeoutManager(
            config=IdleTimeoutConfig(default_timeout=5.0),
            on_idle=failing_cb,
        )
        manager._last_used["zombie"] = 0.0
        # Should not raise despite callback error
        asyncio.run(manager._sweep_once())
        assert "zombie" not in manager._last_used  # still cleaned up

    def test_config_property(self):
        cfg = IdleTimeoutConfig(default_timeout=42.0)
        manager = IdleTimeoutManager(config=cfg)
        assert manager.config is cfg

    def test_mark_unloaded_nonexistent_no_error(self):
        manager = IdleTimeoutManager()
        manager.mark_unloaded("ghost")  # should not raise


# ═════════════════════════════════════════════════════════════════════
# ProxyRegistry — Reference Counting / Dynamic Config Tests
# ═════════════════════════════════════════════════════════════════════


class TestProxyRegistryRefCounting:
    def test_acquire_increments_ref(self):
        reg = _make_registry()
        assert reg.acquire("kos") == 1
        assert reg.acquire("kos") == 2
        assert reg.ref_counts["kos"] == 2

    def test_release_decrements_ref(self):
        reg = _make_registry()
        reg.acquire("kos")
        reg.acquire("kos")
        assert reg.release("kos") == 1
        assert reg.release("kos") == 0
        assert "kos" not in reg._ref_counts

    def test_release_below_zero_returns_zero(self):
        reg = _make_registry()
        assert reg.release("ghost") == 0

    def test_release_at_zero_triggers_unload_callback(self):
        reg = _make_registry()
        unloaded = []

        async def on_unload(name: str):
            unloaded.append(name)

        async def _run():
            reg.set_unload_callback(on_unload)
            reg.acquire("kos")
            reg.release("kos")

        asyncio.run(_run())
        assert "kos" in unloaded

    def test_release_positive_does_not_trigger_unload(self):
        reg = _make_registry()
        unloaded = []

        async def on_unload(name: str):
            unloaded.append(name)

        reg.set_unload_callback(on_unload)
        reg.acquire("kos")
        reg.acquire("kos")
        reg.release("kos")  # still 1 ref
        assert unloaded == []

    def test_ref_counts_property_returns_copy(self):
        reg = _make_registry()
        reg.acquire("kos")
        rc = reg.ref_counts
        assert rc == {"kos": 1}
        # Modifying the copy should not affect internal state
        rc["kos"] = 99
        assert reg._ref_counts["kos"] == 1


class TestProxyRegistrySavedConfig:
    def test_save_and_has_config(self):
        reg = _make_registry()
        assert reg.has_saved_config("kos") is False
        reg.save_config("kos", {"command": "uv", "args": ["run"]})
        assert reg.has_saved_config("kos") is True

    def test_get_saved_config(self):
        reg = _make_registry()
        config = {"command": "uv", "args": ["run", "--package", "kos", "kos-mcp"]}
        reg.save_config("kos", config)
        assert reg.get_saved_config("kos") == config

    def test_forget_config_removes_and_clears_refs(self):
        reg = _make_registry()
        reg.save_config("kos", {"command": "uv"})
        reg.acquire("kos")
        assert reg.has_saved_config("kos") is True
        assert "kos" in reg._ref_counts
        reg.forget_config("kos")
        assert reg.has_saved_config("kos") is False
        assert "kos" not in reg._ref_counts

    def test_known_services_includes_all(self):
        reg = _make_registry()
        # Connected services
        reg._clients["kos"] = _FakeMCPClient("kos")
        # Saved config only (no client)
        reg.save_config("iris", {"command": "iris"})
        known = reg.known_services
        assert "kos" in known
        assert "iris" in known

    def test_is_connected(self):
        reg = _make_registry()
        assert reg.is_connected("kos") is False
        client = _FakeMCPClient("kos")
        asyncio.run(client.connect())
        reg._clients["kos"] = client
        assert reg.is_connected("kos") is True


class TestProxyRegistryLazyConnect:
    def test_lazy_connect_no_config_returns_false(self):
        reg = _make_registry()
        result = asyncio.run(reg.lazy_connect("ghost"))
        assert result is False

    def test_lazy_connect_already_connected_returns_true(self):
        reg = _make_registry()
        client = _FakeMCPClient("kos")
        asyncio.run(client.connect())
        reg._clients["kos"] = client
        reg.save_config("kos", {"mcp_endpoint": "stdio"})
        result = asyncio.run(reg.lazy_connect("kos"))
        assert result is True

    def test_lazy_connect_success(self):
        """lazy_connect should create a new client using saved config and register it."""
        reg = _make_registry()
        reg.save_config(
            "kos",
            {
                "mcp_endpoint": "stdio",
                "command": "uv",
                "args": ["run", "--package", "kos", "kos-mcp"],
            },
        )

        # Mock create_client to return a fake client
        fake_client = _FakeMCPClient("kos")
        with patch("agora.mcp_proxy.registry.create_client", return_value=fake_client):
            result = asyncio.run(reg.lazy_connect("kos"))

        assert result is True
        assert reg.is_connected("kos")
        assert "kos" in reg._clients

    def test_lazy_connect_create_failure_returns_false(self):
        """lazy_connect should return False if create_client raises ValueError."""
        reg = _make_registry()
        reg.save_config("kos", {"mcp_endpoint": "stdio", "command": ""})

        with patch("agora.mcp_proxy.registry.create_client", side_effect=ValueError("bad config")):
            result = asyncio.run(reg.lazy_connect("kos"))

        assert result is False


class TestProxyRegistryDispatchWithLazyReconnect:
    def test_dispatch_reconnects_disconnected_service(self):
        """Dispatch should auto-reconnect if the client is disconnected."""
        reg = _make_registry()
        fake_client = _FakeMCPClient("kos")
        asyncio.run(fake_client.connect())
        reg.save_config("kos", {"mcp_endpoint": "stdio", "command": "uv", "args": []})

        # Register the client first, then disconnect it
        asyncio.run(reg.register_service("kos", fake_client))
        assert reg.is_connected("kos")

        # Manually disconnect
        asyncio.run(fake_client.disconnect())
        assert not reg.is_connected("kos")

        # Dispatch should try lazy reconnect
        with patch("agora.mcp_proxy.registry.create_client", return_value=_FakeMCPClient("kos")):
            result = asyncio.run(reg.dispatch("kos.ping", {}))

        assert "error" not in result.get("status", ""), f"Unexpected error: {result}"

    def test_dispatch_lazy_reconnect_failure_returns_error(self):
        """Dispatch should return error if lazy reconnect fails."""
        reg = _make_registry()
        fake_client = _FakeMCPClient("kos")
        asyncio.run(fake_client.connect())
        reg.save_config("kos", {"mcp_endpoint": "stdio", "command": "uv", "args": []})
        asyncio.run(reg.register_service("kos", fake_client))
        asyncio.run(fake_client.disconnect())

        # Simulate reconnect failure
        with patch("agora.mcp_proxy.registry.create_client", side_effect=ValueError("fail")):
            result = asyncio.run(reg.dispatch("kos.ping", {}))

        assert result["status"] == "error"
        assert "reconnect failed" in result["error"]

    def test_dispatch_unknown_tool_returns_error(self):
        reg = _make_registry()
        result = asyncio.run(reg.dispatch("nonexistent.tool", {}))
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_unregister_and_forget_clears_everything(self):
        reg = _make_registry()
        fake_client = _FakeMCPClient("kos")
        reg.save_config("kos", {"command": "uv"})
        reg.acquire("kos")
        asyncio.run(reg.register_service("kos", fake_client))
        assert reg.is_connected("kos")
        assert reg.has_saved_config("kos")
        assert "kos" in reg._ref_counts

        asyncio.run(reg.unregister_and_forget("kos"))
        assert not reg.is_connected("kos")
        assert not reg.has_saved_config("kos")
        assert "kos" not in reg._ref_counts


# ═════════════════════════════════════════════════════════════════════
# ProxyManager — Dynamic / Idle Timeout Integration Tests
# ═════════════════════════════════════════════════════════════════════


class TestProxyManagerDynamic:
    def test_manager_acquire_release(self):
        pm = _make_manager()
        assert pm.acquire("kos") == 1
        assert pm.acquire("kos") == 2
        assert pm.release("kos") == 1
        assert pm.release("kos") == 0

    def test_ensure_connected_no_config_returns_false(self):
        pm = _make_manager()
        result = asyncio.run(pm.ensure_connected("ghost"))
        assert result is False

    def test_ensure_connected_lazy(self):
        async def _run():
            pm = _make_manager()
            svc = {
                "name": "kos",
                "mcp_endpoint": "stdio",
                "command": "uv",
                "args": ["run", "--package", "kos", "kos-mcp"],
            }
            with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
                await pm.add_service(svc)
            assert pm.registry.is_connected("kos")

            # Disconnect (simulating idle timeout)
            await pm.registry.unregister_service("kos")
            assert not pm.registry.is_connected("kos")
            assert pm.registry.has_saved_config("kos")  # config preserved

            # ensure_connected should re-establish
            with patch("agora.mcp_proxy.registry.create_client", return_value=_FakeMCPClient("kos")):
                result = await pm.ensure_connected("kos")

            assert result is True
            assert pm.registry.is_connected("kos")

        asyncio.run(_run())

    def test_reload_service_reconnects(self):
        pm = _make_manager()
        svc = {"name": "kos", "mcp_endpoint": "stdio", "command": "uv", "args": []}
        with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
            asyncio.run(pm.add_service(svc))

        # Disconnect
        asyncio.run(pm.registry.unregister_service("kos"))
        assert not pm.registry.is_connected("kos")

        # Reload
        with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
            result = asyncio.run(pm.reload_service("kos"))

        assert "ok" in result
        assert pm.registry.is_connected("kos")

    def test_reload_nonexistent_returns_not_found(self):
        pm = _make_manager()
        result = asyncio.run(pm.reload_service("ghost"))
        assert result == "not_found"

    def test_remove_service_preserves_config_if_only_disconnected(self):
        """remove_service should not fail if service was already disconnected."""
        pm = _make_manager()
        result = asyncio.run(pm.remove_service("ghost"))
        assert result == "not_found"

    def test_remove_service_clears_config(self):
        pm = _make_manager()
        svc = {"name": "kos", "mcp_endpoint": "stdio", "command": "uv", "args": []}
        with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
            asyncio.run(pm.add_service(svc))
        assert pm.registry.has_saved_config("kos")

        asyncio.run(pm.remove_service("kos"))
        assert not pm.registry.has_saved_config("kos")


class TestProxyManagerIdleTimeout:
    def test_idle_timeout_disabled_by_default(self):
        pm = _make_manager()
        assert pm.is_idle_timeout_enabled() is False

    def test_enable_idle_timeout_starts_manager(self):
        async def _run():
            pm = _make_manager()
            assert not pm.is_idle_timeout_enabled()

            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0))
            assert pm.is_idle_timeout_enabled()
            assert pm._idle_manager is not None

            await pm.disable_idle_timeout()
            assert not pm.is_idle_timeout_enabled()

        asyncio.run(_run())

    def test_enable_idle_timeout_wires_callbacks(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0))

            # Usage callback should be set
            assert len(pm.registry._usage_callbacks) == 1
            # Unload callback should be set
            assert len(pm.registry._unload_callbacks) == 1

            await pm.disable_idle_timeout()

        asyncio.run(_run())

    def test_idle_timeout_status_when_disabled(self):
        pm = _make_manager()
        status = pm.get_idle_timeout_status()
        assert status["enabled"] is False

    def test_idle_timeout_status_when_enabled(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0, default_timeout=300.0))
            status = pm.get_idle_timeout_status()
            assert status["enabled"] is True
            assert status["sweep_interval"] == 9999.0
            assert status["default_timeout"] == 300.0

            await pm.disable_idle_timeout()

        asyncio.run(_run())

    def test_shutdown_stops_idle_timeout(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0))
            assert pm.is_idle_timeout_enabled()

            await pm.shutdown()
            assert not pm.is_idle_timeout_enabled()
            assert pm._configs == {}

        asyncio.run(_run())


class TestProxyManagerStatus:
    def test_status_with_known_services(self):
        pm = _make_manager()
        svc = {"name": "kos", "mcp_endpoint": "stdio", "command": "uv", "args": []}
        with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
            asyncio.run(pm.add_service(svc))

        status = pm.status()
        assert status["status"] == "running"
        assert "kos" in status["connected_services"]
        assert status["tools"] == 2  # from _FakeMCPClient
        assert "kos" in status["services"]
        assert "known_services" in status
        assert "ref_counts" in status

    def test_status_with_disconnected_service(self):
        pm = _make_manager()
        svc = {"name": "kos", "mcp_endpoint": "stdio", "command": "uv", "args": []}
        with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
            asyncio.run(pm.add_service(svc))
        asyncio.run(pm.registry.unregister_service("kos"))  # disconnect

        status = pm.status()
        assert status["status"] == "running"  # still has known_services
        assert "kos" not in status["connected_services"]
        assert "kos" in status["known_services"]
        assert status["services"]["kos"]["connected"] is False
        assert status["services"]["kos"]["has_config"] is True

    def test_status_empty(self):
        pm = _make_manager()
        status = pm.status()
        assert status["status"] == "idle"
        assert status["tools"] == 0
        assert status["connected_services"] == []

    def test_status_includes_idle_timeout_when_enabled(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0))
            status = pm.status()
            assert "idle_timeout" in status
            await pm.disable_idle_timeout()

        asyncio.run(_run())

    def test_status_includes_ref_counts(self):
        pm = _make_manager()
        pm.acquire("kos")
        pm.acquire("iris")
        pm.release("iris")
        status = pm.status()
        assert status["ref_counts"] == {"kos": 1}


class TestProxyManagerIdleTimeoutWithServices:
    """Integration: idle timeout manager should unregister services via proxy manager."""

    def test_usage_callback_refreshes_idle_timer(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0))

            # Simulate a dispatch
            cb = pm._idle_manager  # type: ignore
            cb.refresh("kos")
            assert "kos" in cb.last_used

            # The usage callback should refresh the timer
            await pm._on_usage("kos", "ping", {})
            assert "kos" in cb.last_used

            await pm.disable_idle_timeout()

        asyncio.run(_run())

    def test_unload_callback_marks_service_unloaded(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout(IdleTimeoutConfig(sweep_interval=9999.0))
            cb = pm._idle_manager  # type: ignore
            cb.refresh("kos")
            assert "kos" in cb.last_used

            await pm._on_unloaded("kos")
            assert "kos" not in cb.last_used

            await pm.disable_idle_timeout()

        asyncio.run(_run())

    def test_shutdown_disconnects_all_and_stops_timeout(self):
        async def _run():
            pm = _make_manager()
            pm.enable_idle_timeout()
            svc = {"name": "kos", "mcp_endpoint": "stdio", "command": "uv", "args": []}
            with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
                await pm.add_service(svc)

            assert pm.registry.is_connected("kos")
            await pm.shutdown()
            assert not pm.is_idle_timeout_enabled()
            assert not pm.registry.is_connected("kos")

        asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════
# Edge Cases & Error Handling
# ═════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_acquire_release_balanced_lifecycle(self):
        """Multiple acquire/release cycles should work correctly."""
        reg = _make_registry()
        for _ in range(5):
            reg.acquire("svc")
        assert reg.ref_counts["svc"] == 5
        for _ in range(5):
            reg.release("svc")
        assert "svc" not in reg._ref_counts

    def test_release_after_reacquire(self):
        """After release to zero, acquire again should start at 1."""
        reg = _make_registry()
        reg.acquire("svc")
        reg.release("svc")
        assert reg.acquire("svc") == 1

    def test_sweep_with_mixed_state(self):
        """Sweep should handle connected, idle, and active services correctly."""
        unloaded = []

        async def on_idle(name: str):
            unloaded.append(name)

        manager = IdleTimeoutManager(
            config=IdleTimeoutConfig(
                default_timeout=30.0,
                per_service_timeout={"fast": 5.0},
            ),
            on_idle=on_idle,
        )
        # fast: 0s old, should be idle (5s timeout)
        manager._last_used["fast"] = 0.0
        # slow: 0s old, but has 30s timeout → not idle yet
        manager._last_used["slow"] = 0.0
        # active: 25s old, but 30s timeout → not idle yet
        manager._last_used["active"] = 10.0

        asyncio.run(manager._sweep_once(now=15.0))
        assert "fast" in unloaded
        assert "slow" not in unloaded
        assert "active" not in unloaded

    def test_dispatch_with_usage_callback_updates_idle_timer(self):
        """Integration: dispatch should trigger usage callback that refreshes idle timer."""
        reg = _make_registry()
        fake = _FakeMCPClient("kos")
        asyncio.run(fake.connect())
        reg.save_config("kos", {"mcp_endpoint": "stdio", "command": "uv"})
        asyncio.run(reg.register_service("kos", fake))

        timer_refreshes = []

        async def usage_cb(svc, tool, args):
            timer_refreshes.append((svc, tool))

        reg.set_usage_callback(usage_cb)
        asyncio.run(reg.dispatch("kos.ping", {}))

        assert len(timer_refreshes) == 1
        assert timer_refreshes[0] == ("kos", "ping")

    def test_disconnect_all_clears_refs_and_configs(self):
        reg = _make_registry()
        fake = _FakeMCPClient("kos")
        asyncio.run(fake.connect())
        reg.save_config("kos", {"command": "uv"})
        reg.acquire("kos")
        asyncio.run(reg.register_service("kos", fake))

        asyncio.run(reg.disconnect_all())
        assert reg._entries == {}
        assert reg._clients == {}
        assert reg._ref_counts == {}
        assert reg._saved_configs == {}

    def test_acquire_and_ensure_connected_flow(self):
        """Full flow: save config → acquire → ensure_connected → dispatch → release."""
        pm = _make_manager()
        svc = {"name": "kos", "mcp_endpoint": "stdio", "command": "uv", "args": []}
        with patch("agora.mcp_proxy.manager.create_client", return_value=_FakeMCPClient("kos")):
            asyncio.run(pm.add_service(svc))

        # Simulate idle timeout disconnect
        asyncio.run(pm.registry.unregister_service("kos"))
        assert not pm.registry.is_connected("kos")

        # Acquire reference
        pm.acquire("kos")

        # Ensure connected (lazy reconnect)
        with patch("agora.mcp_proxy.registry.create_client", return_value=_FakeMCPClient("kos")):
            ok = asyncio.run(pm.ensure_connected("kos"))

        assert ok is True

        # Dispatch
        result = asyncio.run(pm.dispatch("kos.ping", {}))
        assert "error" not in result.get("status", "")

        # Release
        pm.release("kos")
        assert "kos" not in pm.registry._ref_counts
