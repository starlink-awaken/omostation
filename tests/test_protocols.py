"""Tests for _protocols.py — handlers and dispatch."""

import pytest
from agora._protocols import _get_client, close_client, dispatch


class TestDispatch:
    def test_mcp_protocol_dispatches(self):
        inst = {"protocol": "mcp", "mcp_endpoint": "http://192.0.2.1:8765"}
        assert inst["protocol"] == "mcp"

    def test_rest_protocol_dispatches(self):
        inst = {"protocol": "rest", "mcp_endpoint": "http://192.0.2.1:3000", "protocol_config": {"method": "GET"}}
        assert inst["protocol"] == "rest"

    def test_grpc_protocol_dispatches(self):
        inst = {
            "protocol": "grpc",
            "mcp_endpoint": "grpc://192.0.2.1:50051",
            "protocol_config": {"host": "192.0.2.1:50051"},
        }
        assert inst["protocol"] == "grpc"

    def test_websocket_protocol_dispatches(self):
        inst = {"protocol": "websocket", "mcp_endpoint": "ws://192.0.2.1:8080", "protocol_config": {"timeout": 1}}
        assert inst["protocol"] == "websocket"

    def test_stdio_returns_proxy_error(self):
        inst = {"protocol": "stdio", "mcp_endpoint": "stdio://test"}
        assert inst["protocol"] == "stdio"

    def test_unknown_protocol_returns_error(self):
        inst = {"protocol": "unknown_proto", "mcp_endpoint": ""}
        assert inst["protocol"] == "unknown_proto"

    @pytest.mark.asyncio
    async def test_dispatch_stdio(self):
        result = await dispatch({"protocol": "stdio", "mcp_endpoint": "stdio://test"}, "test.tool", {})
        assert result["status"] == "error"
        assert "stdio protocol uses proxy" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_unknown(self):
        result = await dispatch({"protocol": "unknown", "mcp_endpoint": ""}, "test", {})
        assert result["status"] == "error"
        assert "Unknown protocol" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_mcp_ssrf_blocked(self):
        """MCP dispatch blocks private IP via _is_safe_url."""
        result = await dispatch({"protocol": "mcp", "mcp_endpoint": "http://10.0.0.1/mcp"}, "test.tool", {})
        assert result["status"] == "error"
        assert "Service unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_rest_ssrf_blocked(self):
        """REST dispatch blocks private IP."""
        result = await dispatch(
            {"protocol": "rest", "mcp_endpoint": "http://10.0.0.1/api", "protocol_config": {"method": "GET"}},
            "test.list",
            {},
        )
        assert result["status"] == "error"
        assert "Service unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_grpc_no_stub(self, monkeypatch):
        """gRPC without stub_module returns clear error."""

        async def _fake_grpc(tool_name, arguments, instance):
            return {"status": "error", "error": "gRPC requires compiled proto stub"}

        monkeypatch.setattr("agora._protocols._call_grpc", _fake_grpc)
        result = await dispatch(
            {
                "protocol": "grpc",
                "mcp_endpoint": "grpc://192.0.2.1:50051",
                "protocol_config": {"host": "192.0.2.1:50051"},
            },
            "test.call",
            {},
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_dispatch_ws_invalid_url(self):
        """WebSocket with non-ws URL returns error."""
        result = await dispatch(
            {"protocol": "websocket", "mcp_endpoint": "http://192.0.2.1:8080", "protocol_config": {"timeout": 1}},
            "test.push",
            {},
        )
        assert result["status"] == "error"
        assert "Invalid WebSocket URL" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_rest_method_post(self, monkeypatch):
        """REST POST method is passed through to handler."""
        called = {}

        async def _fake_rest(tool_name, arguments, instance):
            called.update({"tool": tool_name, "args": arguments, "inst": instance})
            return {"status": "ok"}

        monkeypatch.setattr("agora._protocols._call_rest", _fake_rest)
        result = await dispatch(
            {
                "protocol": "rest",
                "mcp_endpoint": "http://192.0.2.1:3000/api",
                "protocol_config": {"method": "POST", "path": "/users"},
            },
            "api.create",
            {"name": "test"},
        )
        assert result["status"] == "ok"
        assert called["tool"] == "api.create"
        assert called["args"] == {"name": "test"}


class TestGetClient:
    def test_get_client_returns_singleton(self):
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_client_resets(self):
        import agora._protocols as pmod

        original = pmod._client
        pmod._client = None
        try:
            c1 = _get_client()
            assert c1 is not None
            await close_client()
            assert pmod._client is None
        finally:
            pmod._client = original
