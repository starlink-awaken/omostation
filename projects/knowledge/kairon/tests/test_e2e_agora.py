"""Agora E2E tests — MCP tool infrastructure."""

import pytest

pytest.importorskip("agora", reason="requires agora package (cross-project dependency)")


class TestAgora:
    """Test agora bootstrap and service discovery."""

    def test_hermes_mcp(self):
        """Hermes MCP tools module should compile and be importable."""
        from agora.hermes_mcp import HermesToolRegistry  # type: ignore[reportMissingImports]

        assert HermesToolRegistry is not None

    def test_known_services(self):
        """Test known service registry is loadable."""
        from agora.mcp.mcp_bootstrap import KNOWN_SERVICES  # type: ignore[reportMissingImports]

        assert len(KNOWN_SERVICES) >= 1
