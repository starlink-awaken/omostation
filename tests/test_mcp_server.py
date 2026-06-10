"""Tests for Agora MCP Server tools — direct function imports."""

import asyncio

from agora.server.mcp import (
    add_route,
    check_health,
    get_event_log,
    list_routes,
    list_services,
    publish_event,
    register_service,
    subscribe_event,
)


class TestRegisterService:
    def test_register_mcp_service(self):
        result = asyncio.run(
            register_service(
                name="mcp-test",
                mcp_endpoint="http://192.0.2.50:8765",
                tags="test,mcp",
            )
        )
        assert result["status"] == "ok"
        assert result["action"] == "registered"
        assert result["name"] == "mcp-test"

    def test_register_rest_service(self):
        result = asyncio.run(
            register_service(
                name="rest-test",
                protocol="rest",
                protocol_config='{"method":"GET"}',
                mcp_endpoint="http://192.0.2.51:3000",
            )
        )
        assert result["status"] == "ok"
        assert result["action"] == "registered"

    def test_register_invalid_protocol(self):
        result = asyncio.run(
            register_service(
                name="bad-proto",
                protocol="invalid",
            )
        )
        assert result["status"] == "error"
        assert "Unknown protocol" in result["error"]

    def test_register_bad_port(self):
        result = asyncio.run(
            register_service(
                name="bad-port",
                port=99999,
            )
        )
        assert result["status"] == "error"

    def test_register_bad_protocol_config(self):
        result = asyncio.run(
            register_service(
                name="bad-cfg",
                protocol_config="not json",
            )
        )
        assert result["status"] == "error"

    def test_register_with_a2a_params(self):
        """register_service accepts A2A metadata parameters."""
        result = asyncio.run(
            register_service(
                name="a2a-param-test",
                mcp_endpoint="http://192.0.2.70:8765",
                has_auth=True,
                has_push_notifications=True,
                has_state_transitions=True,
                provider_info='{"organization":"TestOrg","version":"1.0"}',
                documentation_url="https://docs.example.com",
            )
        )
        assert result["status"] == "ok"
        assert result["name"] == "a2a-param-test"


class TestListServices:
    def test_list_returns_array(self):
        result = list_services()
        assert isinstance(result, dict)
        assert "data" in result
        assert "format_version" in result
        assert isinstance(result["data"], list)

    def test_list_includes_registered(self):
        asyncio.run(register_service(name="list-test", mcp_endpoint="http://192.0.2.60:8765"))
        result = list_services()
        names = [s["name"] for s in result["data"]]
        assert "list-test" in names


class TestHealthCheck:
    def test_health_returns_counts(self):
        import asyncio

        result = asyncio.run(check_health())
        assert "total" in result
        assert "healthy" in result


class TestRoutes:
    def test_add_and_list_routes(self):
        add_route("test.tool", "test-svc")
        routes = list_routes()
        assert "data" in routes
        assert "test.tool" in routes["data"]
        assert routes["data"]["test.tool"] == "test-svc"


class TestEventBus:
    def test_publish_and_read_event(self):
        publish_event("test:mcp", '{"msg":"hello"}', "mcp-test")
        log = get_event_log(limit=5)
        assert isinstance(log, dict)
        assert "data" in log
        assert isinstance(log["data"], list)
        if log["data"]:
            assert log["data"][-1]["type"] == "test:mcp"

    def test_subscribe_event(self):
        result = subscribe_event("test:*")
        assert "subscription_id" in result
        assert result["pattern"] == "test:*"


class TestRouteCall:
    def test_route_call_bad_json(self):
        """route_call with invalid JSON returns error."""
        import asyncio

        from agora.server.mcp import route_call

        result = asyncio.run(route_call("nonexistent", "not json"))
        assert "error" in str(result)

    def test_route_call_passes_structured_identity_to_router(self, monkeypatch):
        import asyncio

        from agora.server.mcp import route_call

        captured = {}

        async def _fake_route(tool_name, arguments, caller_id="unknown", use_cache=True):
            captured["tool_name"] = tool_name
            captured["arguments"] = arguments
            captured["caller_id"] = caller_id
            return {"status": "ok", "result": "routed"}

        monkeypatch.setattr("agora.server.mcp.router.route", _fake_route)

        result = asyncio.run(
            route_call(
                "minerva.research",
                '{"query":"identity"}',
                caller_identity='{"subject_id":"alice","subject_type":"user","issuer":"auth0","tenant":"acme"}',
            )
        )

        assert result["status"] == "ok"
        assert captured["tool_name"] == "minerva.research"
        assert captured["arguments"] == {"query": "identity"}
        assert captured["caller_id"] == {
            "subject_id": "alice",
            "subject_type": "user",
            "issuer": "auth0",
            "tenant": "acme",
        }

    def test_route_call_derives_structured_identity_from_auth_token(self, monkeypatch):
        import asyncio
        from types import SimpleNamespace

        from agora.server.mcp import route_call

        captured = {}

        async def _fake_route(tool_name, arguments, caller_id="unknown", use_cache=True):
            captured["tool_name"] = tool_name
            captured["arguments"] = arguments
            captured["caller_id"] = caller_id
            return {"status": "ok", "result": "routed"}

        monkeypatch.setattr("agora.server.mcp.router.route", _fake_route)
        monkeypatch.setattr(
            "agora.server.mcp.get_access_token",
            lambda: SimpleNamespace(
                client_id="agora-mcp-client",
                resource="tenant-acme",
                scopes=["route:call"],
                claims={"sub": "alice", "iss": "auth0", "tenant": "acme"},
            ),
        )

        result = asyncio.run(route_call("minerva.research", '{"query":"identity"}'))

        assert result["status"] == "ok"
        assert captured["tool_name"] == "minerva.research"
        assert captured["arguments"] == {"query": "identity"}
        assert captured["caller_id"] == {
            "subject_id": "alice",
            "subject_type": "service",
            "issuer": "auth0",
            "tenant": "acme",
        }


class TestProxyTools:
    def test_proxy_status_not_initialized(self):
        """proxy_status without initialization returns error."""
        import asyncio

        from agora.server.mcp import proxy_status

        result = asyncio.run(proxy_status())
        assert result["status"] == "error"
        assert "not initialized" in result.get("error", "").lower()

    def test_proxy_call_not_initialized(self):
        """proxy_call without initialization returns error."""
        import asyncio

        from agora.server.mcp import proxy_call

        result = asyncio.run(proxy_call("test.tool"))
        assert result["status"] == "error"
        assert "not initialized" in result["error"].lower()

    def test_proxy_remove_not_initialized(self):
        """proxy_remove_service without initialization returns error."""
        import asyncio

        from agora.server.mcp import proxy_remove_service

        result = asyncio.run(proxy_remove_service("test"))
        assert result["status"] == "error"
        assert "not initialized" in result.get("error", "").lower()

    def test_add_route_empty(self):
        """add_route with empty name returns error."""
        result = add_route("", "")
        assert result["status"] == "error"
        assert "required" in result["error"].lower()
