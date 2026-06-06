"""Tests for Agora degrade mode: local service cache + Agent fallback.

Ensures the system survives Agora being down and properly falls back
to cached service data and direct MCP calls.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from agora.core.router import Router
from agora.core.service_base import Service
from agora.core.service_cache import (
    CACHE_FILE,
    clear_service_cache,
    is_cache_stale,
    load_service_cache,
    save_service_cache,
)

# Ensure agent-runtime is importable for degrade tests
# agent-runtime is a sibling package in the kairon monorepo
_AGENT_RUNTIME_DIR = Path(__file__).resolve().parent.parent.parent / "agent-runtime" / "src"
if _AGENT_RUNTIME_DIR.is_dir() and str(_AGENT_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_RUNTIME_DIR))


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_services() -> list[dict]:
    """A realistic set of cached services."""
    return [
        {
            "name": "minerva",
            "description": "Research agent",
            "protocol": "mcp",
            "protocol_config": {},
            "mcp_endpoint": "http://localhost:8765/mcp",
            "health_endpoint": "http://localhost:8765/health",
            "port": 8765,
            "tags": ["research"],
            "instances": [],
        },
        {
            "name": "kos",
            "description": "Knowledge OS",
            "protocol": "mcp",
            "protocol_config": {},
            "mcp_endpoint": "http://localhost:7420/mcp",
            "health_endpoint": "",
            "port": 7420,
            "tags": ["knowledge"],
            "instances": [],
        },
        {
            "name": "agora",
            "description": "Agora itself",
            "protocol": "mcp",
            "protocol_config": {},
            "mcp_endpoint": "http://localhost:7430/mcp",
            "health_endpoint": "",
            "port": 7430,
            "tags": ["gateway"],
            "instances": [],
        },
    ]


@pytest.fixture
def seeded_cache(sample_services) -> None:
    """Seed the cache with sample services before each test."""
    clear_service_cache()
    save_service_cache(sample_services)
    yield
    clear_service_cache()


@pytest.fixture
def mock_registry() -> MagicMock:
    """A ServiceRegistry mock with no services (simulating Agora being down)."""
    reg = MagicMock()
    reg._storage_path = "/tmp/agora-test-registry.json"
    reg.get.return_value = None
    reg.list_all.return_value = []
    return reg


@pytest.fixture(autouse=True)
def cleanup_test_state():
    """Cleanup after each test."""
    yield
    clear_service_cache()
    try:
        from agent_runtime.tools import reset_agora_degrade_state

        reset_agora_degrade_state()
    except ImportError:
        pass


# ── Async helper ────────────────────────────────────────────────────────────


def _async_route(router: Router, tool_name: str, args: dict, **kwargs) -> dict:
    """Run Router.route() synchronously for tests."""
    return asyncio.run(router.route(tool_name, args, **kwargs))


# ── Tests: service_cache.py ────────────────────────────────────────────────


class TestServiceCache:
    def test_save_and_load(self, sample_services):
        """Save services to cache and verify they load correctly."""
        clear_service_cache()
        assert save_service_cache(sample_services) is True
        assert CACHE_FILE.exists()

        loaded = load_service_cache()
        assert "services" in loaded
        assert "timestamp" in loaded
        assert len(loaded["services"]) == 3
        assert loaded["services"][0]["name"] == "minerva"

    def test_load_empty(self):
        """Loading from a non-existent cache returns empty dict."""
        clear_service_cache()
        assert not CACHE_FILE.exists()
        loaded = load_service_cache()
        assert loaded == {}

    def test_load_corrupted(self):
        """A corrupted cache file returns empty dict gracefully."""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text("not valid json")
        loaded = load_service_cache()
        assert loaded == {}

    def test_is_cache_stale(self):
        """Fresh cache is not stale; old cache is stale."""
        clear_service_cache()
        assert is_cache_stale() is True

        save_service_cache([{"name": "test", "mcp_endpoint": "http://localhost:9999/mcp"}])
        assert is_cache_stale() is False

    def test_clear(self):
        """Clearing removes the cache file."""
        save_service_cache([{"name": "test"}])
        assert CACHE_FILE.exists()
        assert clear_service_cache() is True
        assert not CACHE_FILE.exists()

    def test_clear_non_existent(self):
        """Clearing a non-existent cache returns False."""
        clear_service_cache()
        assert clear_service_cache() is False


# ── Tests: Router cache fallback ────────────────────────────────────────────


class TestRouterCacheFallback:
    def test_route_falls_back_to_cache(self, mock_registry, seeded_cache):
        """When registry is empty, Router falls back to cache."""
        router = Router(registry=mock_registry, event_bus=None)
        router.add_route("research_now", "minerva")
        result = _async_route(router, "research_now", {"query": "test"}, caller_id="test")
        # Without cache we'd get "Service temporarily unavailable"
        # With cache we try to dispatch — but since there's no real server,
        # we get an error from the dispatch. The important thing is it
        # *attempts* to route (doesn't bail with "no_instance").
        assert result is not None
        # It should not be the "no instance" error
        assert result.get("error") != "Service temporarily unavailable"

    def test_route_no_cache(self, mock_registry):
        """With use_cache=False, empty registry returns 'no_instance' error."""

        router = Router(registry=mock_registry, event_bus=None)
        # Register a route so resolve() can find the service name
        router.add_route("research_now", "minerva")
        # But mock_registry.get() returns None (simulating Agora being down)
        result = _async_route(router, "research_now", {"query": "test"}, caller_id="test", use_cache=False)
        assert result["status"] == "error"
        assert "unavailable" in result.get("error", "")

    def test_route_not_found(self, mock_registry):
        """An unresolvable tool returns 'not found' before cache is checked."""
        router = Router(registry=mock_registry, event_bus=None)
        result = _async_route(router, "nonexistent_tool", {}, caller_id="test")
        assert result["status"] == "error"
        assert "not available" in result.get("error", "")

    def test_persist_cache(self, mock_registry, sample_services):
        """persist_cache() saves current registry services to disk."""
        clear_service_cache()
        router = Router(registry=mock_registry, event_bus=None)

        # Make the mock return some services
        svc = Service(
            name="minerva",
            description="Research agent",
            protocol="mcp",
            mcp_endpoint="http://localhost:8765/mcp",
            health_endpoint="http://localhost:8765/health",
            port=8765,
        )
        router.registry.list_all.return_value = [svc]
        router.registry.get.return_value = svc

        assert router.persist_cache() is True
        loaded = load_service_cache()
        assert len(loaded["services"]) == 1
        assert loaded["services"][0]["name"] == "minerva"
        assert loaded["services"][0]["mcp_endpoint"] == "http://localhost:8765/mcp"

    def test_cache_fallback_with_instances(self, mock_registry):
        """Cache fallback works even for services with multi-instance config."""
        clear_service_cache()
        svc_with_instances = [
            {
                "name": "minerva",
                "description": "Research agent",
                "protocol": "mcp",
                "protocol_config": {},
                "mcp_endpoint": "http://localhost:8765/mcp",
                "health_endpoint": "",
                "port": 8765,
                "tags": [],
                "instances": [
                    {"mcp_endpoint": "http://localhost:8765/mcp", "port": 8765},
                    {"mcp_endpoint": "http://localhost:8766/mcp", "port": 8766},
                ],
            }
        ]
        save_service_cache(svc_with_instances)

        router = Router(registry=mock_registry, event_bus=None)
        router.add_route("research_now", "minerva")
        result = _async_route(router, "research_now", {"query": "test"}, caller_id="test")
        assert result is not None
        assert result.get("error") != "Service temporarily unavailable"


# ── Tests: Agent Runtime fallback ──────────────────────────────────────────


class TestAgentRuntimeFallback:
    """Test the agent-runtime MCP call fallback via direct test."""

    @pytest.mark.skip(reason="agent-runtime is deprecated and moved to _archived")
    def test_direct_mcp_call_unknown_server(self):
        """Direct call to unknown server returns error."""
        from agent_runtime.tools import _direct_mcp_call, reset_agora_degrade_state

        reset_agora_degrade_state()
        result = _direct_mcp_call("nonexistent_server", "test_tool", {})
        assert result.get("error", "").startswith("Unknown MCP server")

    @pytest.mark.skip(reason="agent-runtime is deprecated and moved to _archived")
    def test_agora_fallback_state_transitions(self):
        """Verify the degrade state machine: failures -> direct mode -> recovery."""
        from agent_runtime.tools import (
            _is_agora_direct_mode,
            _record_agora_failure,
            _record_agora_success,
            reset_agora_degrade_state,
        )

        reset_agora_degrade_state()
        assert _is_agora_direct_mode() is False

        # First failure: should NOT trigger direct mode yet
        _record_agora_failure()
        assert _is_agora_direct_mode() is False

        # Second failure (consecutive): SHOULD trigger direct mode
        _record_agora_failure()
        assert _is_agora_direct_mode() is True

        # Success: reset counter
        _record_agora_success()
        from agent_runtime.tools import _agora_failure_count

        assert _agora_failure_count == 0

        # Reset function clears both
        reset_agora_degrade_state()
        assert _is_agora_direct_mode() is False


# ── Integration: Simulate Agora being down ────────────────────────────────


class TestDegradeIntegration:
    """End-to-end degrade scenario: Agora down -> cache fallback + direct mode."""

    def test_simulate_agora_down_cache_fallback(self, mock_registry, seeded_cache):
        """Simulate Agora being down: registry empty, cache has data."""
        router = Router(registry=mock_registry, event_bus=None)
        router.add_route("research_now", "minerva")

        # Route a call — should fall back to cache and attempt dispatch
        result = _async_route(router, "research_now", {"query": "test"}, caller_id="degrade-test")
        assert result is not None
        # The dispatch may fail (no real server), but it should NOT
        # immediately return "Service temporarily unavailable"
        assert result.get("error") != "Service temporarily unavailable"

    @pytest.mark.skip(reason="agent-runtime is deprecated and moved to _archived")
    def test_agent_runtime_fallback_imports(self):
        """Verify agent-runtime degrade module imports correctly."""
        from agent_runtime.tools import (
            _direct_mcp_call,
            _is_agora_direct_mode,
            _record_agora_failure,
            _record_agora_success,
            reset_agora_degrade_state,
        )

        assert callable(_direct_mcp_call)
        assert callable(_is_agora_direct_mode)
        assert callable(_record_agora_failure)
        assert callable(_record_agora_success)
        assert callable(reset_agora_degrade_state)

    @pytest.mark.skip(reason="agent-runtime is deprecated and moved to _archived")
    def test_mcp_call_unknown_server(self):
        """mcp_call with unknown server returns error gracefully."""
        from agent_runtime.tools import Tools, reset_agora_degrade_state

        reset_agora_degrade_state()
        result = Tools.mcp_call("nonexistent_server", "test_tool", {})
        # Without Agora configured, it falls through to direct mode
        # Which also doesn't know 'nonexistent_server'
        assert "error" in result
