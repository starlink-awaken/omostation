"""Tests for Agora MCP proxy manager and client helpers."""

from agora.mcp_proxy.client import (
    _make_request,
    _make_request_dict,
    _make_tool_call,
    _make_tool_call_dict,
)
from agora.mcp_proxy.manager import ProxyManager
from agora.mcp_proxy.registry import ProxyRegistry


class TestClientHelpers:
    def test_make_request_returns_string(self):
        result = _make_request("tools/list")
        assert isinstance(result, str)
        assert '"method":"tools/list"' in result.replace(" ", "").replace("\n", "")

    def test_make_request_dict_returns_dict(self):
        result = _make_request_dict("tools/list")
        assert isinstance(result, dict)
        assert result["method"] == "tools/list"
        assert result["jsonrpc"] == "2.0"
        assert "id" in result

    def test_make_tool_call_returns_string(self):
        result = _make_tool_call("minerva.research_now", {"query": "test"})
        assert isinstance(result, str)
        assert "minerva.research_now" in result

    def test_make_tool_call_dict_returns_dict(self):
        result = _make_tool_call_dict("minerva.research_now", {"query": "test"})
        assert isinstance(result, dict)
        assert result["method"] == "tools/call"
        assert result["params"]["name"] == "minerva.research_now"


class TestProxyRegistryNoCopy:
    def test_entries_returns_same_dict(self):
        reg = ProxyRegistry()
        entries = reg.entries
        assert entries is reg._entries  # no defensive copy


class TestProxyManager:
    def setup_method(self):
        self.manager = ProxyManager()

    def test_initial_status_idle(self):
        status = self.manager.status()
        assert status["status"] == "idle"
        assert status["tools"] == 0
        assert status["connected_services"] == []

    def test_start_no_services(self):
        import asyncio

        results = asyncio.run(self.manager.start([]))
        assert results == {}

    def test_add_bad_service_returns_error(self):
        import asyncio

        results = asyncio.run(self.manager.start([{"name": "bad-svc", "mcp_endpoint": "http://192.0.2.99:19999"}]))
        assert "bad-svc" in results
        assert "error" in results["bad-svc"] or "ok" in results["bad-svc"]

    def test_status_after_connect(self):
        import asyncio

        asyncio.run(self.manager.start([{"name": "echo-svc", "mcp_endpoint": "http://192.0.2.99:19999"}]))
        status = self.manager.status()
        assert "status" in status

    def test_remove_nonexistent(self):
        import asyncio

        result = asyncio.run(self.manager.remove_service("ghost"))
        assert result == "not_found"


class TestProxyRegistryBasics:
    def test_empty_entries(self):
        from agora.mcp_proxy.registry import ProxyRegistry

        reg = ProxyRegistry()
        assert reg.entries == {}
        assert reg.connected_services == []

    def test_get_entry_nonexistent(self):
        from agora.mcp_proxy.registry import ProxyRegistry

        reg = ProxyRegistry()
        assert reg.get_entry("nonexistent.tool") is None


# ── Phase 2 Tests: usage callback ───────────────────────────────────────


class TestProxyUsageCallback:
    """Tests for the usage callback on ProxyRegistry dispatch."""

    def test_set_usage_callback_stores(self):
        reg = ProxyRegistry()

        async def my_callback(svc, tool, args):
            pass

        reg.set_usage_callback(my_callback)
        assert reg._usage_callbacks == [my_callback]

    def test_set_usage_callback_none_clears(self):
        reg = ProxyRegistry()

        async def my_callback(svc, tool, args):
            pass

        reg.set_usage_callback(my_callback)
        reg.set_usage_callback(None)
        assert reg._usage_callbacks == []

    def test_dispatch_no_callback_no_error(self):
        """Dispatch without callback should work normally."""
        import asyncio

        reg = ProxyRegistry()
        # No callback set — should not raise
        result = asyncio.run(reg.dispatch("nonexistent", {}))
        assert result["status"] == "error"

    def test_proxy_manager_set_usage_callback(self):
        """ProxyManager.set_usage_callback delegates to registry."""
        pm = ProxyManager()

        async def cb(svc, tool, args):
            pass

        pm.set_usage_callback(cb)
        assert pm.registry._usage_callbacks == [cb]
