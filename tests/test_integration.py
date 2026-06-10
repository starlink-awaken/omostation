"""Integration tests: Agora routing to Minerva + Sophia."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from agora.core.registry import Service, ServiceRegistry
from agora.core.router import Router


class TestAgoraIntegration:
    """End-to-end routing tests with real Minerva + Sophia."""

    def setup_method(self):
        # Prevent L0 global routes from leaking into unit test assertions
        self._l0_patch = patch("agora.l0_registry_loader.load_routes", return_value={})
        self._l0_patch.start()
        self.registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))
        self.router = Router(self.registry, routes_path=str(Path(tempfile.mkdtemp()) / "test-routes.json"))

    def teardown_method(self):
        self._l0_patch.stop()

    def test_register_all_services(self):
        self.registry.register(
            Service(
                "minerva",
                "Deep Research Engine",
                mcp_endpoint="http://192.0.2.1:8765",
                health_endpoint="http://192.0.2.1:8765/health",
                port=8765,
                tags=["research", "search"],
            )
        )
        self.registry.register(
            Service(
                "sophia",
                "Paradigm Engine",
                mcp_endpoint="sophia-mcp",
                port=9001,
                tags=["paradigm", "compiler"],
            )
        )
        self.registry.register(
            Service(
                "kos",
                "Knowledge OS",
                mcp_endpoint="kos-mcp-server",
                port=9002,
                tags=["knowledge", "index"],
            )
        )
        assert len(self.registry.list_all()) == 3
        assert len(self.registry.list_healthy()) == 3

    def test_route_resolution(self):
        self.registry.register(Service("minerva", port=8765))
        self.registry.register(Service("sophia", port=9001))
        self.router.add_route("minerva", "minerva")  # prefix
        self.router.add_route("minerva.research_now", "minerva")  # exact
        self.router.add_route("sophia.compile_paradigm", "sophia")
        self.router.add_route("sophia", "sophia")

        assert self.router.resolve("minerva.research_now") == "minerva"
        assert self.router.resolve("minerva.knowledge_search") == "minerva"
        assert self.router.resolve("sophia.compile_paradigm") == "sophia"
        assert self.router.resolve("sophia.list_operations") == "sophia"
        assert self.router.resolve("nonexistent.tool") is None

    def test_unavailable_service(self):
        self.registry.register(Service("offline", port=9999))
        self.registry.mark_failure("offline")
        self.registry.mark_failure("offline")
        self.registry.mark_failure("offline")
        assert not self.registry.get("offline").is_available

    def test_recovery_after_success(self):
        self.registry.register(Service("flaky", port=9999))
        for _ in range(3):
            self.registry.mark_failure("flaky")
        assert not self.registry.get("flaky").is_available
        for _ in range(4):  # Gradual decay: 4 successes → 0 failures
            self.registry.mark_success("flaky")
        assert self.registry.get("flaky").is_available

    def test_service_to_dict_serialization(self):
        self.registry.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765", port=8765))
        self.registry.register(Service("sophia", port=9001))
        d = self.registry.to_dict()
        assert len(d) == 2
        names = {s["name"] for s in d}
        assert names == {"minerva", "sophia"}
        for s in d:
            assert "healthy" in s
            assert "endpoint" in s

    def test_full_route_flow(self):
        """Complete flow: register → route → resolve → check health."""
        # Register
        self.registry.register(
            Service(
                "minerva",
                mcp_endpoint="http://192.0.2.1:8765",
                health_endpoint="http://192.0.2.1:8765/health",
                port=8765,
            )
        )
        self.registry.register(Service("sophia", mcp_endpoint="sophia-mcp", port=9001))

        # Route
        self.router.add_route("minerva", "minerva")
        self.router.add_route("sophia", "sophia")

        # Resolve
        tools = [
            "minerva.research_now",
            "minerva.knowledge_search",
            "minerva.knowledge_ingest",
            "sophia.compile_paradigm",
            "sophia.list_operations",
        ]
        for tool in tools:
            svc = self.router.resolve(tool)
            assert svc is not None, f"No route for {tool}"
            assert self.registry.get(svc) is not None, f"Service {svc} not registered"

        # Verify service count
        assert len(self.registry.list_all()) == 2
        assert len(self.router.list_routes()) == 2
