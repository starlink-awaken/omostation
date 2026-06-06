"""Tests for mcp_gateway — central MCP backend registration.

Verifies the gateway starts and stops cleanly without crashes.
Individual downstream service connections may fail if the commands are
not on ``$PATH``; the test only validates that the API surface works.
"""

from __future__ import annotations

import pytest
from agora.auth import mcp_gateway


class TestKnownBackends:
    """KNOWN_BACKENDS should list all expected kairon MCP services."""

    def test_known_backends_has_all_services(self):
        names = [b["name"] for b in mcp_gateway.KNOWN_BACKENDS]
        assert "agent-runtime" in names
        assert "eidos" in names
        assert "iris" in names
        assert "kronos" in names
        assert "metaos" in names
        assert "minerva" in names
        assert "sophia" in names
        assert "cron-service" in names

    def test_known_backends_have_required_keys(self):
        for backend in mcp_gateway.KNOWN_BACKENDS:
            assert "name" in backend
            assert "mcp_endpoint" in backend
            assert "command" in backend
            assert "args" in backend

    def test_known_backends_gateway_format(self):
        """Every backend should use stdio transport (empty mcp_endpoint)."""
        for backend in mcp_gateway.KNOWN_BACKENDS:
            assert backend.get("mcp_endpoint") == "", f"{backend['name']} should use stdio transport"


@pytest.mark.asyncio
class TestGatewayLifecycle:
    """start/stop lifecycle tests."""

    async def test_start_all_creates_manager(self):
        """start_all should create a ProxyManager and return a dict."""
        results = await mcp_gateway.start_all()
        assert isinstance(results, dict)
        assert len(results) == len(mcp_gateway.KNOWN_BACKENDS)
        assert mcp_gateway._gateway_manager is not None
        await mcp_gateway.stop_all()

    async def test_stop_all_cleans_up(self):
        """stop_all should clear the manager."""
        await mcp_gateway.start_all()
        assert mcp_gateway._gateway_manager is not None
        await mcp_gateway.stop_all()
        assert mcp_gateway._gateway_manager is None

    async def test_double_stop_is_safe(self):
        """Calling stop_all twice must not raise."""
        await mcp_gateway.stop_all()
        await mcp_gateway.stop_all()  # second call is a no-op

    async def test_start_returns_results_for_each_backend(self):
        """Every KNOWN_BACKENDS entry should have a result entry."""
        results = await mcp_gateway.start_all()
        for backend in mcp_gateway.KNOWN_BACKENDS:
            name = backend["name"]
            assert name in results, f"Missing result for {name}"
        await mcp_gateway.stop_all()
