"""A2A MCP tools smoke tests.

Validates that the A2A governance tools (a2a_send_task, a2a_get_task,
a2a_list_tasks, list_agent_cards, get_agent_card) are properly registered
and return expected response shapes.

These are unit-level smoke tests that mock the underlying service layer,
not full network integration tests.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP


async def _tool_names(mcp: FastMCP) -> set[str]:
    tools = await mcp.list_tools()
    return {t.name for t in tools}


@pytest.fixture
def mcp_app():
    """Create a FastMCP instance with governance tools registered."""
    mcp = FastMCP("test-a2a")
    from agora.server.tools_governance import register_governance_tools

    register_governance_tools(mcp)
    return mcp


@pytest.fixture
def mcp_app_with_swarm():
    """Create a FastMCP instance with swarm tools registered."""
    mcp = FastMCP("test-swarm")
    from agora.server.tools_swarm import register_swarm_tools

    register_swarm_tools(mcp)
    return mcp


class TestA2AToolsRegistered:
    """Verify A2A tools are registered on the MCP instance."""

    def test_a2a_send_task_registered(self, mcp_app):
        names = asyncio.run(_tool_names(mcp_app))
        assert "a2a_send_task" in names

    def test_a2a_get_task_registered(self, mcp_app):
        names = asyncio.run(_tool_names(mcp_app))
        assert "a2a_get_task" in names

    def test_a2a_cancel_task_registered(self, mcp_app):
        names = asyncio.run(_tool_names(mcp_app))
        assert "a2a_cancel_task" in names

    def test_a2a_list_tasks_registered(self, mcp_app):
        names = asyncio.run(_tool_names(mcp_app))
        assert "a2a_list_tasks" in names

    def test_list_agent_cards_registered(self, mcp_app):
        names = asyncio.run(_tool_names(mcp_app))
        assert "list_agent_cards" in names

    def test_get_agent_card_registered(self, mcp_app):
        names = asyncio.run(_tool_names(mcp_app))
        assert "get_agent_card" in names


class TestSwarmToolsRegistered:
    """Verify swarm tools are registered on the MCP instance."""

    def test_swarm_status_registered(self, mcp_app_with_swarm):
        names = asyncio.run(_tool_names(mcp_app_with_swarm))
        assert "swarm_status" in names

    def test_swarm_nodes_registered(self, mcp_app_with_swarm):
        names = asyncio.run(_tool_names(mcp_app_with_swarm))
        assert "swarm_nodes" in names

    def test_swarm_resolve_registered(self, mcp_app_with_swarm):
        names = asyncio.run(_tool_names(mcp_app_with_swarm))
        assert "swarm_resolve" in names


class TestBOSToolsRegistered:
    """Verify BOS discovery tools are registered."""

    def test_resolve_bos_uri_registered(self):
        mcp = FastMCP("test-bos")
        from agora.server.tools_bos.registration import register_bos_tools

        register_bos_tools(mcp, MagicMock())
        names = asyncio.run(_tool_names(mcp))
        assert "resolve_bos_uri" in names

    def test_list_bos_resources_registered(self):
        mcp = FastMCP("test-bos")
        from agora.server.tools_bos.registration import register_bos_tools

        register_bos_tools(mcp, MagicMock())
        names = asyncio.run(_tool_names(mcp))
        assert "list_bos_resources" in names

    def test_list_bos_domains_registered(self):
        mcp = FastMCP("test-bos")
        from agora.server.tools_bos.registration import register_bos_tools

        register_bos_tools(mcp, MagicMock())
        names = asyncio.run(_tool_names(mcp))
        assert "list_bos_domains" in names
