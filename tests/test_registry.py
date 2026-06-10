"""Tests for Agora service registry."""

import tempfile
from pathlib import Path

import pytest
from agora.core.registry import KNOWN_PROTOCOLS, Service, ServiceRegistry
from agora.core.service_base import parse_protocol_config, parse_tags


def _new_registry():
    """Create a fresh registry with temp storage (no persistence cross-contamination)."""
    return ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))


class TestParseTags:
    def test_single_tag(self):
        assert parse_tags("research") == ["research"]

    def test_multiple_tags(self):
        assert parse_tags("research, search,knowledge") == ["research", "search", "knowledge"]

    def test_empty(self):
        assert parse_tags("") == []

    def test_whitespace_only(self):
        assert parse_tags("  ,  , ") == []


class TestParseProtocolConfig:
    def test_dict_passthrough(self):
        cfg, err = parse_protocol_config({"key": "val"})
        assert cfg == {"key": "val"}
        assert err is None

    def test_valid_json(self):
        cfg, err = parse_protocol_config('{"method":"GET"}')
        assert cfg == {"method": "GET"}
        assert err is None

    def test_invalid_json(self):
        cfg, err = parse_protocol_config("not json")
        assert cfg == {}
        assert err is not None

    def test_empty_default(self):
        cfg, err = parse_protocol_config("{}")
        assert cfg == {}
        assert err is None


class TestKnownProtocols:
    def test_all_known(self):
        assert "mcp" in KNOWN_PROTOCOLS
        assert "rest" in KNOWN_PROTOCOLS
        assert "grpc" in KNOWN_PROTOCOLS
        assert "stdio" in KNOWN_PROTOCOLS
        assert "websocket" in KNOWN_PROTOCOLS

    def test_is_frozenset(self):
        assert isinstance(KNOWN_PROTOCOLS, frozenset)


class TestService:
    def test_service_creation(self):
        s = Service("minerva", mcp_endpoint="http://192.0.2.1:8765", port=8765)
        assert s.name == "minerva"
        assert s.healthy is True
        assert s.is_available is True

    def test_circuit_breaker(self):
        s = Service("test")
        s.failure_count = 2
        assert s.is_available is True
        s.failure_count = 3
        s.healthy = False
        s.cooldown_until = 9999999999.0
        assert s.is_available is False

    def test_default_protocol(self):
        s = Service("test")
        assert s.protocol == "mcp"
        assert s.protocol_config == {}

    def test_rest_protocol(self):
        s = Service("my-api", protocol="rest", protocol_config={"method": "POST"})
        assert s.protocol == "rest"
        assert s.protocol_config == {"method": "POST"}

    def test_to_dict_includes_protocol(self):
        s = Service("test", protocol="rest", protocol_config={"path": "/api"})
        d = s.to_dict()
        assert d["protocol"] == "rest"
        assert d["protocol_config"] == {"path": "/api"}


class TestServiceRegistry:
    def test_register_and_get(self):
        r = _new_registry()
        r.register(Service("minerva", port=8765))
        r.register(Service("sophia", port=9001))
        assert len(r.list_all()) == 2
        assert r.get("minerva").port == 8765
        assert r.get("nonexistent") is None

    def test_list_healthy(self):
        r = _new_registry()
        r.register(Service("minerva", port=8765))
        r.register(Service("sophia", port=9001))
        assert len(r.list_healthy()) == 2
        r.mark_failure("minerva")
        r.mark_failure("minerva")
        r.mark_failure("minerva")
        assert len(r.list_healthy()) == 1

    def test_mark_success_recovery(self):
        r = _new_registry()
        r.register(Service("test"))
        r.mark_failure("test")
        r.mark_failure("test")
        r.mark_failure("test")
        assert not r.get("test").is_available
        r.mark_success("test")
        r.mark_success("test")
        r.mark_success("test")
        assert r.get("test").is_available  # 3 successes gradually decay to 0

    def test_unregister(self):
        r = _new_registry()
        r.register(Service("test"))
        r.unregister("test")
        assert r.get("test") is None

    def test_to_dict(self):
        r = _new_registry()
        r.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765"))
        d = r.to_dict()
        assert len(d) == 1
        assert d[0]["name"] == "minerva"
        assert "healthy" in d[0]

    def test_register_valid_protocol(self):
        r = _new_registry()
        r.register(Service("api", protocol="rest", mcp_endpoint="http://192.0.2.1:3000"))
        assert r.get("api").protocol == "rest"

    def test_register_invalid_protocol(self):
        r = _new_registry()
        with pytest.raises(ValueError, match="Unknown protocol"):
            r.register(Service("bad", protocol="invalid_proto"))

    def test_clear_all(self):
        r = _new_registry()
        r.register(Service("a"))
        r.register(Service("b"))
        r.register(Service("c"))
        count = r.clear_all()
        assert count == 3
        assert r.list_all() == []

    def test_clear_all_empty(self):
        r = _new_registry()
        count = r.clear_all()
        assert count == 0
        assert r.list_all() == []

    def test_register_heartbeat_updates_identity_and_timestamp(self):
        r = _new_registry()
        r.register(Service("worker-1"))

        result = r.register_heartbeat("worker-1", {"role": "indexer"}, now=100.0)

        svc = r.get("worker-1")
        assert result == {"name": "worker-1", "status": "heartbeat_registered", "last_heartbeat": 100.0}
        assert svc is not None
        assert svc.healthy is True
        assert svc.last_health_check == 100.0
        assert svc.provider_info == {"role": "indexer"}

    def test_stale_heartbeats_detects_zombie_services(self):
        r = _new_registry()
        r.register(Service("fresh"))
        r.register(Service("zombie"))
        r.register_heartbeat("fresh", now=190.0)
        r.register_heartbeat("zombie", now=10.0)

        stale = r.stale_heartbeats(max_age_seconds=60.0, now=200.0)

        assert [item["name"] for item in stale] == ["zombie"]
        assert stale[0]["age_seconds"] == 190.0

    def test_cache_snapshot_restores_services_when_registry_is_unavailable(self):
        cache_path = Path(tempfile.mkdtemp()) / "service-cache.json"
        r = _new_registry()
        r.register(Service("cached-worker", protocol="stdio", mcp_endpoint="stdio:worker"))
        r.register_heartbeat("cached-worker", {"role": "worker"}, now=123.0)
        r.save_cache_snapshot(str(cache_path))

        restored = ServiceRegistry.load_cache_snapshot(str(cache_path), max_age_seconds=3600.0, now=124.0)

        assert len(restored) == 1
        assert restored[0].name == "cached-worker"
        assert restored[0].provider_info == {"role": "worker"}


class TestGrpcHealthCheck:
    def test_grpc_returns_healthy(self):
        """gRPC protocol service returns True (TCP fails, falls back to healthy=True)."""
        r = _new_registry()
        svc = Service("grpc-svc", protocol="grpc", mcp_endpoint="http://192.0.2.1:50051")
        r.register(svc)
        # TCP connect to 192.0.2.1 fails; falls back to svc.healthy (True)
        assert r.grpc_health_check("grpc-svc") is True

    def test_non_grpc_returns_false(self):
        """Non-gRPC service returns False from grpc_health_check."""
        r = _new_registry()
        r.register(Service("rest-svc", protocol="rest", mcp_endpoint="http://192.0.2.1:3000"))
        assert r.grpc_health_check("rest-svc") is False

    def test_nonexistent_returns_false(self):
        """Nonexistent service returns False from grpc_health_check."""
        r = _new_registry()
        assert r.grpc_health_check("nonexistent") is False

    def test_grpc_health_check_unhealthy(self):
        """gRPC service marked unhealthy returns False (TCP fails, falls back to healthy=False)."""
        r = _new_registry()
        svc = Service("grpc-svc", protocol="grpc", mcp_endpoint="http://192.0.2.1:50051")
        r.register(svc)
        svc.healthy = False
        assert r.grpc_health_check("grpc-svc") is False

    def test_grpc_no_endpoint_returns_false(self):
        """gRPC service without mcp_endpoint returns False."""
        r = _new_registry()
        r.register(Service("no-ep", protocol="grpc"))
        assert r.grpc_health_check("no-ep") is False


class TestParseGrpcEndpoint:
    def test_http_url(self):
        host, port = ServiceRegistry._parse_grpc_endpoint("http://example.com:50051")
        assert host == "example.com"
        assert port == 50051

    def test_plain_host_port(self):
        host, port = ServiceRegistry._parse_grpc_endpoint("example.com:50051")
        assert host == "example.com"
        assert port == 50051

    def test_empty_returns_none(self):
        assert ServiceRegistry._parse_grpc_endpoint("") is None

    def test_no_port_returns_none(self):
        assert ServiceRegistry._parse_grpc_endpoint("http://example.com") is None

    def test_https_url(self):
        host, port = ServiceRegistry._parse_grpc_endpoint("https://my-server:443")
        assert host == "my-server"
        assert port == 443


class TestCircuitStatus:
    def test_get_circuit_status(self):
        """Circuit status returns detailed breaker state."""
        r = _new_registry()
        r.register(Service("minerva", port=8765))
        status = r.get_circuit_status("minerva")
        assert status["name"] == "minerva"
        assert status["state"] == "CLOSED"
        assert status["healthy"] is True
        assert status["failure_count"] == 0

    def test_get_circuit_status_nonexistent(self):
        """Circuit status for unknown service returns empty dict."""
        r = _new_registry()
        assert r.get_circuit_status("ghost") == {}

    def test_get_circuit_status_open(self):
        """Circuit status shows OPEN after tripping breaker."""
        r = _new_registry()
        r.register(Service("test"))
        for _ in range(3):
            r.mark_failure("test")
        status = r.get_circuit_status("test")
        assert status["state"] == "OPEN"
        assert status["failure_count"] == 3
