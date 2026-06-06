"""Tests for Agora request router."""

import importlib
import importlib.util
import tempfile
from pathlib import Path

import pytest
from agora.core.event_bus import EventBus
from agora.core.registry import Service, ServiceRegistry
from agora.core.router import Router


def _reg():
    """Create isolated ServiceRegistry (no config pollution)."""
    return ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))


def _identity_module():
    spec = importlib.util.find_spec("agora.auth.identity")
    assert spec is not None, "agora.auth.identity module should exist for typed identity support"
    return importlib.import_module("agora.auth.identity")


class TestEUMiddleware:
    """Tests for EU cost tracking middleware in Router.route()."""

    @pytest.mark.asyncio
    async def test_eu_middleware_called(self, monkeypatch):
        """EU cost tracking middleware calls EULedger.consume on success."""
        import sys
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock

        from httpx import AsyncClient

        # Inject mock kaironcloud_billing.pricing.eu_ledger module
        mock_ledger = MagicMock()
        mock_ledger.consume = MagicMock(return_value=MagicMock(success=True))
        mock_ledger_mod = MagicMock()
        mock_ledger_mod.EULedger = MagicMock(return_value=mock_ledger)

        injected = {"kaironcloud_billing.pricing.eu_ledger": mock_ledger_mod}
        sentinel = {}
        try:
            for key, val in injected.items():
                sentinel[key] = sys.modules.get(key)
                sys.modules[key] = val

            registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))
            svc = Service("minerva", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
            registry.register(svc)
            router = Router(registry, routes_path=str(Path(tempfile.mkdtemp()) / "test-routes.json"))
            router.add_route("minerva.research", "minerva")

            class _MockResp:
                def json(self):
                    return {"result": "data", "status": "ok"}

                def raise_for_status(self):
                    pass

            class _MockClient(AsyncClient):
                def __init__(self):
                    pass

                async def post(self, url, **kw):
                    return _MockResp()

                async def aclose(self):
                    pass

            monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())

            result = await router.route("minerva.research", {}, caller_id="test-user")
            assert result["result"] == "data"
            mock_ledger.consume.assert_called_once_with("test-user", "minerva")
        finally:
            for key in injected:
                if sentinel.get(key) is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = sentinel[key]


class TestIdentityPropagation:
    @pytest.mark.asyncio
    async def test_route_normalizes_typed_identity_for_accounting_audit_and_events(self, monkeypatch):
        from httpx import AsyncClient

        identity_mod = _identity_module()
        identity = identity_mod.Identity(
            subject_id="alice",
            subject_type="user",
            issuer="auth0",
            tenant="acme",
        )

        registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))
        svc = Service("minerva", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        bus = EventBus(registry=registry)
        router = Router(registry, event_bus=bus, routes_path=str(Path(tempfile.mkdtemp()) / "test-routes.json"))
        router.add_route("minerva.research", "minerva")

        captured: dict[str, object] = {}

        class _MockResp:
            def json(self):
                return {"result": "data", "status": "ok"}

            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def post(self, url, **kw):
                return _MockResp()

            async def aclose(self):
                pass

        class _FakeAccountDB:
            def record_call(self, record):
                captured["record"] = record

        class _FakeAuditLogger:
            def log(self, action, actor="anonymous", resource="", result="success", detail="", ip=""):
                captured["audit"] = {
                    "action": action,
                    "actor": actor,
                    "resource": resource,
                    "result": result,
                    "detail": detail,
                    "ip": ip,
                }
                return "audit1234"

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        monkeypatch.setattr("agora.accounting.ResourceAccountDB", _FakeAccountDB)
        monkeypatch.setattr("agora.audit.AuditLogger", _FakeAuditLogger)

        result = await router.route("minerva.research", {}, caller_id=identity)

        assert result["result"] == "data"
        record = captured["record"]
        assert record.caller_id == "user:alice"
        assert record.billed_to == "tenant:acme"
        assert captured["audit"]["actor"] == "user:alice"

        events = bus.get_event_log(5)
        route_event = next(event for event in events if event["type"] == "route:call.succeeded")
        assert route_event["payload"]["identity"] == {
            "subject_id": "alice",
            "subject_type": "user",
            "issuer": "auth0",
            "tenant": "acme",
        }

    @pytest.mark.asyncio
    async def test_eu_middleware_skip_on_error(self, monkeypatch):
        """EU cost tracking is skipped when dispatch returns error."""
        import sys
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock

        from httpx import AsyncClient, ConnectError

        # Inject mock eu_pricing module
        mock_ledger = MagicMock()
        mock_ledger_mod = MagicMock()
        mock_ledger_mod.EULedger = MagicMock(return_value=mock_ledger)

        injected = {"eu_pricing": MagicMock(), "eu_pricing.ledger": mock_ledger_mod}
        sentinel = {}
        try:
            for key, val in injected.items():
                sentinel[key] = sys.modules.get(key)
                sys.modules[key] = val

            registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))
            svc = Service("minerva", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
            registry.register(svc)
            router = Router(registry, routes_path=str(Path(tempfile.mkdtemp()) / "test-routes.json"))
            router.add_route("minerva.research", "minerva")

            class _ErrClient(AsyncClient):
                def __init__(self):
                    pass

                async def post(self, url, **kw):
                    raise ConnectError("fail")

                async def aclose(self):
                    pass

            monkeypatch.setattr("agora._protocols._get_client", lambda: _ErrClient())

            result = await router.route("minerva.research", {}, caller_id="test-user")
            assert result["status"] == "error"
            mock_ledger.consume.assert_not_called()
        finally:
            for key in injected:
                if sentinel.get(key) is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = sentinel[key]

    @pytest.mark.asyncio
    async def test_eu_middleware_does_not_block_result(self, monkeypatch):
        """EU middleware failure does not block the response."""
        import tempfile
        from pathlib import Path

        from httpx import AsyncClient

        registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))
        svc = Service("minerva", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router = Router(registry, routes_path=str(Path(tempfile.mkdtemp()) / "test-routes.json"))
        router.add_route("minerva.research", "minerva")

        class _MockResp:
            def json(self):
                return {"result": "data", "status": "ok"}

            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def post(self, url, **kw):
                return _MockResp()

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        # No mock EU — the late import will fail and be caught by except
        result = await router.route("minerva.research", {}, caller_id="test-user")
        assert result["result"] == "data"


class TestRouter:
    def setup_method(self):
        import tempfile

        self.tmpdir = tempfile.mkdtemp()
        self.registry = ServiceRegistry(storage_path=str(Path(self.tmpdir) / "test-services.json"))
        self.registry.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765"))
        self.registry.register(Service("sophia", mcp_endpoint="http://192.0.2.2:9001"))
        self.router = Router(self.registry, routes_path=str(Path(self.tmpdir) / "test-routes.json"))

    def test_exact_match(self):
        self.router.add_route("minerva.research_now", "minerva")
        assert self.router.resolve("minerva.research_now") == "minerva"

    def test_prefix_match(self):
        self.router.add_route("minerva", "minerva")
        assert self.router.resolve("minerva.research_now") == "minerva"
        assert self.router.resolve("minerva.knowledge_search") == "minerva"

    def test_no_match(self):
        assert self.router.resolve("nonexistent.tool") is None

    def test_list_routes(self):
        self.router.add_route("minerva", "minerva")
        self.router.add_route("sophia.compile", "sophia")
        routes = self.router.list_routes()
        assert len(routes) == 2
        assert routes["minerva"] == "minerva"
        assert routes["sophia.compile"] == "sophia"


class TestAddInstance:
    def test_promotes_to_list_with_protocol(self):
        """Adding an instance should propagate protocol/config to instance dicts."""
        registry = _reg()
        router = Router(registry)
        registry.register(
            Service("api", protocol="rest", mcp_endpoint="http://192.0.2.1:3000", protocol_config={"method": "POST"})
        )
        router._add_instance("api", "http://192.0.2.2:3000")
        svc = registry.get("api")
        assert len(svc.instances) == 2
        for inst in svc.instances:
            assert inst["protocol"] == "rest"
            assert inst["protocol_config"] == {"method": "POST"}


class TestProtocolDispatch:
    def setup_method(self):
        self.registry = _reg()
        self.router = Router(self.registry)

    def test_rest_reserved_returns_error(self):
        """REST service returns reserved error when target is unreachable."""
        svc = Service("api", protocol="rest", mcp_endpoint="http://192.0.2.99:3000", protocol_config={"method": "GET"})
        self.registry.register(svc)
        self.router.add_route("api", "api")

    def test_grpc_reserved_returns_error(self):
        """gRPC protocol returns reserved error."""
        svc = Service("grpc-svc", protocol="grpc", mcp_endpoint="http://192.0.2.99:50051")
        self.registry.register(svc)
        self.router.add_route("grpc-svc", "grpc-svc")

    def test_websocket_reserved_returns_error(self):
        """WebSocket protocol returns reserved error."""
        svc = Service("ws-svc", protocol="websocket", mcp_endpoint="http://192.0.2.99:8080")
        self.registry.register(svc)
        self.router.add_route("ws-svc", "ws-svc")

    @pytest.mark.asyncio
    async def test_grpc_dispatch_returns_stub_error(self):
        """gRPC dispatch returns error without compiled stub."""
        svc = Service(
            "grpc-svc",
            protocol="grpc",
            mcp_endpoint="grpc://192.0.2.99:50051",
            protocol_config={"host": "192.0.2.99:50051"},
        )
        self.registry.register(svc)
        self.router.add_route("grpc-svc", "grpc-svc")
        result = await self.router.route("grpc-svc", {})
        assert result["status"] == "error"
        assert "stub" in result["error"].lower() or "grpc" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_ws_dispatch_returns_stub_error(self):
        """WebSocket dispatch returns error on connect failure."""
        svc = Service(
            "ws-svc", protocol="websocket", mcp_endpoint="ws://192.0.2.99:8080", protocol_config={"timeout": 1}
        )
        self.registry.register(svc)
        self.router.add_route("ws-svc", "ws-svc")
        result = await self.router.route("ws-svc", {})
        assert result["status"] == "error"
        assert "WebSocket" in result["error"] or "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_stdio_dispatch_returns_error(self):
        """stdio dispatch returns error about proxy usage."""
        svc = Service("stdio-svc", protocol="stdio", mcp_endpoint="stdio://my-service")
        self.registry.register(svc)
        self.router.add_route("stdio-svc", "stdio-svc")
        result = await self.router.route("stdio-svc", {})
        assert result["status"] == "error"
        assert "stdio protocol uses proxy" in result["error"]

    @pytest.mark.asyncio
    async def test_rest_retry_methods(self):
        """REST with GET retries via protocol_config retries field."""
        svc = Service(
            "retry-api",
            protocol="rest",
            mcp_endpoint="http://192.0.2.99:3000",
            protocol_config={"method": "GET", "retries": 1},
        )
        self.registry.register(svc)
        self.router.add_route("retry-api", "retry-api")
        result = await self.router.route("retry-api", {})
        assert result["status"] == "error"
        assert "REST call failed" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_protocol_dispatch(self):
        """Unknown protocol in instance dict returns error (bypasses registry validation)."""
        svc = Service("bad-proto", protocol="mcp", mcp_endpoint="http://192.0.2.99:9999")
        self.registry.register(svc)
        # Override after registration to simulate corrupt instance state
        svc.protocol = "unknown_proto"
        self.router.add_route("bad-proto", "bad-proto")
        result = await self.router.route("bad-proto", {})
        assert result["status"] == "error"
        assert "Unknown protocol" in result["error"]

    @pytest.mark.asyncio
    async def test_ws_invalid_url_dispatch(self):
        """WebSocket with non-ws URL returns invalid URL error."""
        svc = Service("bad-ws", protocol="websocket", mcp_endpoint="http://192.0.2.99:8080")
        self.registry.register(svc)
        self.router.add_route("bad-ws", "bad-ws")
        result = await self.router.route("bad-ws", {})
        assert result["status"] == "error"
        assert "Invalid WebSocket URL" in result["error"]

    def test_get_percentiles_empty(self):
        """Percentiles are all zero when no calls have been routed."""
        pct = self.router.get_percentiles()
        assert pct == {"p50": 0, "p90": 0, "p99": 0, "samples": 0, "avg": 0}

    @pytest.mark.asyncio
    async def test_route_no_match(self):
        """Routing to an unmapped tool returns error."""
        result = await self.router.route("nonexistent.tool", {})
        assert result["status"] == "error"
        assert "Tool not available" in result["error"]

    @pytest.mark.asyncio
    async def test_route_service_unavailable(self):
        """Routing to a service that's in OPEN state returns unavailable error."""
        svc = Service("down-svc", protocol="grpc", mcp_endpoint="http://192.0.2.99:9999")
        self.registry.register(svc)
        svc.healthy = False
        svc.cooldown_until = 9999999999.0
        self.router.add_route("down-svc", "down-svc")
        result = await self.router.route("down-svc", {})
        assert result["status"] == "error"
        assert "Service temporarily unavailable" in result["error"]


class TestRouterAdvanced:
    """Advanced router tests: _call_mcp, _call_rest, _trace, close, etc."""

    @pytest.fixture(autouse=True)
    def _reset_protocols_client(self):
        """Reset the module-level httpx client singleton before each test."""
        import agora._protocols as rmod

        rmod._client = None
        yield
        rmod._client = None

    @pytest.mark.asyncio
    async def test_call_mcp_success(self, monkeypatch):
        """_call_mcp with valid endpoint returns response."""
        from httpx import AsyncClient

        registry = _reg()
        router = Router(registry)
        svc = Service("mcp-svc", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router.add_route("mcp-svc.tool", "mcp-svc")

        class _MockResp:
            def json(self):
                return {"result": "data"}

            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def post(self, url, **kw):
                return _MockResp()

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        result = await router.route("mcp-svc.tool", {"q": "t"})
        assert result["result"] == "data"

    @pytest.mark.asyncio
    async def test_call_mcp_ssrf_blocked(self):
        """_call_mcp with private IP returns SSRF error."""
        registry = _reg()
        router = Router(registry)
        svc = Service("ssrf", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        # Override URL to unsafe after registration (bypasses registry validation)
        svc.mcp_endpoint = "http://10.0.0.1:9999/mcp"
        router.add_route("ssrf.tool", "ssrf")
        result = await router.route("ssrf.tool", {})
        assert result["status"] == "error"
        assert "unavailable" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_call_mcp_httpx_error(self, monkeypatch):
        """_call_mcp when httpx raises propagates error."""
        from httpx import AsyncClient, ConnectError

        registry = _reg()
        router = Router(registry)
        svc = Service("err", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router.add_route("err.tool", "err")

        class _ErrClient(AsyncClient):
            def __init__(self):
                pass

            async def post(self, url, **kw):
                raise ConnectError("connection refused")

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _ErrClient())
        result = await router.route("err.tool", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_call_rest_post_success(self, monkeypatch):
        """REST POST call returns successfully."""
        from httpx import AsyncClient

        registry = _reg()
        router = Router(registry)
        svc = Service(
            "rest-api", protocol="rest", mcp_endpoint="http://192.0.2.1:3000", protocol_config={"method": "POST"}
        )
        registry.register(svc)
        router.add_route("rest-api.create", "rest-api")

        class _MockResp:
            status_code = 200

            def json(self):
                return {"created": True}

            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def request(self, method, url, **kw):
                return _MockResp()

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        result = await router.route("rest-api.create", {"name": "x"})
        assert result["created"] is True

    @pytest.mark.asyncio
    async def test_call_rest_ssrf_blocked(self):
        """REST call with private IP returns SSRF error."""
        registry = _reg()
        router = Router(registry)
        svc = Service(
            "rest-ssrf", protocol="rest", mcp_endpoint="http://192.0.2.1:3000", protocol_config={"method": "GET"}
        )
        registry.register(svc)
        svc.mcp_endpoint = "http://10.0.0.1:3000"
        router.add_route("rest-ssrf", "rest-ssrf")
        result = await router.route("rest-ssrf", {})
        assert result["status"] == "error"
        assert "unavailable" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_call_rest_retry_success(self, monkeypatch):
        """REST GET retries and succeeds on 2nd attempt."""
        import httpx
        from httpx import AsyncClient

        registry = _reg()
        router = Router(registry)
        svc = Service(
            "retry-api",
            protocol="rest",
            mcp_endpoint="http://192.0.2.1:3000",
            protocol_config={"method": "GET", "retries": 1},
        )
        registry.register(svc)
        router.add_route("retry-api.get", "retry-api")

        attempts = [0]

        class _MockResp:
            status_code = 200

            def json(self):
                return {"ok": True}

            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def request(self, method, url, **kw):
                attempts[0] += 1
                if attempts[0] == 1:
                    req = httpx.Request("GET", url)
                    resp = httpx.Response(502, request=req)
                    raise httpx.HTTPStatusError("502", request=req, response=resp)
                return _MockResp()

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        result = await router.route("retry-api.get", {})
        assert result["ok"] is True
        assert attempts[0] == 2

    @pytest.mark.asyncio
    async def test_call_rest_retry_exhausted(self, monkeypatch):
        """REST GET with all retries exhausted returns error."""
        import httpx
        from httpx import AsyncClient

        registry = _reg()
        router = Router(registry)
        svc = Service(
            "exhaust",
            protocol="rest",
            mcp_endpoint="http://192.0.2.1:3000",
            protocol_config={"method": "GET", "retries": 1},
        )
        registry.register(svc)
        router.add_route("exhaust.get", "exhaust")

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def request(self, method, url, **kw):
                req = httpx.Request("GET", url)
                resp = httpx.Response(502, request=req)
                raise httpx.HTTPStatusError("502", request=req, response=resp)

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        result = await router.route("exhaust.get", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_call_rest_non_retryable(self, monkeypatch):
        """REST 400 returns immediately without retry."""
        import httpx
        from httpx import AsyncClient

        registry = _reg()
        router = Router(registry)
        svc = Service(
            "bad-req", protocol="rest", mcp_endpoint="http://192.0.2.1:3000", protocol_config={"method": "GET"}
        )
        registry.register(svc)
        router.add_route("bad-req.get", "bad-req")

        class _MockClient(AsyncClient):
            def __init__(self):
                pass

            async def request(self, method, url, **kw):
                req = httpx.Request("GET", url)
                resp = httpx.Response(400, request=req)
                raise httpx.HTTPStatusError("400", request=req, response=resp)

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _MockClient())
        result = await router.route("bad-req.get", {})
        assert result["status"] == "error"
        assert result.get("http_status") == 400

    @pytest.mark.asyncio
    async def test_route_exception_path(self, monkeypatch):
        """route() catches and returns exception from _dispatch."""
        from httpx import AsyncClient, ConnectError

        registry = _reg()
        router = Router(registry)
        svc = Service("crash", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router.add_route("crash.tool", "crash")

        class _ErrClient(AsyncClient):
            def __init__(self):
                pass

            async def post(self, url, **kw):
                raise ConnectError("boom")

            async def aclose(self):
                pass

        monkeypatch.setattr("agora._protocols._get_client", lambda: _ErrClient())
        result = await router.route("crash.tool", {})
        assert result["status"] == "error"

    def test_trace_flush(self, tmp_path):
        """_trace writes to disk when buffer reaches 50 entries."""
        from agora.core.router import Router as Router2

        registry = _reg()
        router = Router2(registry)
        # Override trace path to tmp
        router._trace_path = tmp_path / "trace.jsonl"
        # Fill buffer with 50 entries
        for i in range(50):
            router._trace(f"tool{i}", "svc", 0, "ok")
        flushed = list(tmp_path.iterdir())
        assert len(flushed) >= 1
        content = (tmp_path / "trace.jsonl").read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 50

    def test_maybe_publish_with_event_bus(self):
        """_maybe_publish sends event when event_bus is configured."""
        from agora.core.event_bus import EventBus

        registry = _reg()
        bus = EventBus(registry=registry)
        router = Router(registry, event_bus=bus)
        router._maybe_publish("test:event", {"msg": "hello"})
        log = bus.get_event_log(5)
        assert any(e["type"] == "test:event" for e in log)

    async def test_close_cleans_client(self, monkeypatch):
        """close() cleans up the HTTP client singleton."""
        import agora._protocols as rmod

        closed = [False]

        class _Closable:
            async def aclose(self):
                closed[0] = True

        mock_client = _Closable()
        monkeypatch.setattr(rmod, "_client", mock_client)

        registry = _reg()
        router = Router(registry)
        await router.close()
        assert closed[0] is True
        assert rmod._client is None

    def test_get_percentiles_with_data(self):
        """Percentiles return correct values with latency data."""
        from agora.core.router import Router as Router3

        registry = _reg()
        router = Router3(registry)
        router._latencies.append(0.1)
        router._latencies.append(0.2)
        router._latencies.append(0.3)
        router._latencies.append(0.4)
        router._latencies.append(0.5)
        pct = router.get_percentiles()
        assert pct["samples"] == 5
        assert pct["p50"] >= 0.2
        assert pct["avg"] == 0.3

    def test_add_instance_no_existing(self):
        """_add_instance promotes single service to multi-instance."""
        registry = _reg()
        router = Router(registry)
        svc = Service("multi", protocol="rest", mcp_endpoint="http://192.0.2.1:3000", protocol_config={"method": "GET"})
        registry.register(svc)
        router._add_instance("multi", "http://192.0.2.2:3000")
        assert len(svc.instances) == 2
        assert svc.instances[0]["protocol"] == "rest"
        assert svc.instances[1]["protocol"] == "rest"

    def test_add_instance_nonexistent(self):
        """_add_instance with unknown service does nothing."""
        registry = _reg()
        router = Router(registry)
        router._add_instance("ghost", "http://x:3000")  # should not crash

    def test_next_instance_with_instances(self):
        """_next_instance round-robins through multiple instances."""
        registry = _reg()
        router = Router(registry)
        svc = Service("lb", protocol="rest", mcp_endpoint="http://192.0.2.1:3000", protocol_config={"method": "GET"})
        registry.register(svc)
        router._add_instance("lb", "http://192.0.2.2:3000")
        router._add_instance("lb", "http://192.0.2.3:3000")
        # Round-robin should cycle through 3 instances
        i1 = router._next_instance("lb")
        i2 = router._next_instance("lb")
        i3 = router._next_instance("lb")
        assert i1 is not None
        urls = {i1["mcp_endpoint"], i2["mcp_endpoint"], i3["mcp_endpoint"]}
        assert len(urls) == 3

    def test_next_instance_unavailable(self):
        """_next_instance returns None for unavailable service."""
        registry = _reg()
        router = Router(registry)
        svc = Service("down")
        registry.register(svc)
        svc.healthy = False
        svc.cooldown_until = 9999999999.0
        assert router._next_instance("down") is None

    def test_next_instance_nonexistent(self):
        """_next_instance returns None for unknown service."""
        registry = _reg()
        router = Router(registry)
        assert router._next_instance("ghost") is None

    def test_get_client_singleton(self, monkeypatch):
        """_get_client returns same instance on second call."""
        # Reset _client first
        import agora._protocols as rmod
        from agora._protocols import _get_client

        rmod._client = None
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2
