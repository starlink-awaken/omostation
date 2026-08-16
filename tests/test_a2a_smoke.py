"""A2A MCP tools smoke tests.

Validates that the A2A governance tools (a2a_send_task, a2a_get_task,
a2a_list_tasks, list_agent_cards, get_agent_card) are properly registered
and return expected response shapes.

These are unit-level smoke tests that mock the underlying service layer,
not full network integration tests.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

# metaos 是 optional 依赖 (admission extra): cascading CI 的裸 uv sync 不装 → 跳过本模块。
# 与 test_forge_loader.py 的 importorskip 模式对齐 (kairon/forge 先例)。
pytest.importorskip(
    "metaos.a2a.task_manager",
    reason="metaos 不可用 (admission optional extra, 非 agora 核心依赖)",
)
from metaos.a2a.task_manager import TaskManager  # noqa: E402


async def _tool_names(mcp: FastMCP) -> set[str]:
    tools = await mcp.list_tools()
    return {t.name for t in tools}


async def _call_tool(mcp: FastMCP, name: str, arguments: dict) -> dict:
    result = await mcp.call_tool(name, arguments)
    return json.loads(result.content[0].text)


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

    @pytest.mark.asyncio
    async def test_deferred_send_can_be_queried_then_canceled(
        self, mcp_app, monkeypatch, tmp_path
    ):
        manager = TaskManager(MagicMock(), storage_path=str(tmp_path / "tasks.json"))
        monkeypatch.setattr(
            "agora.server.tools_governance._get_task_manager", lambda: manager
        )

        sent = await _call_tool(
            mcp_app,
            "a2a_send_task",
            {
                "tool_name": "g1.smoke.noop",
                "arguments": "{}",
                "session_id": "g1-sr03",
                "execute_immediately": False,
            },
        )
        task_id = sent["task"]["id"]
        assert sent["status"] == "ok"
        assert sent["task"]["status"] == "submitted"

        queried = await _call_tool(mcp_app, "a2a_get_task", {"task_id": task_id})
        assert queried["task"]["id"] == task_id
        assert queried["task"]["status"] == "submitted"

        canceled = await _call_tool(mcp_app, "a2a_cancel_task", {"task_id": task_id})
        assert canceled["status"] == "ok"
        assert canceled["task_id"] == task_id
        assert canceled["task"]["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_default_send_executes_and_completed_task_cannot_be_canceled(
        self, mcp_app, monkeypatch, tmp_path
    ):
        router = MagicMock()
        router.route = AsyncMock(return_value={"data": {"result": "ok"}})
        manager = TaskManager(router, storage_path=str(tmp_path / "tasks.json"))
        monkeypatch.setattr(
            "agora.server.tools_governance._get_task_manager", lambda: manager
        )

        sent = await _call_tool(
            mcp_app,
            "a2a_send_task",
            {"tool_name": "g1.smoke.noop", "arguments": "{}"},
        )
        task_id = sent["task"]["id"]
        assert sent["status"] == "ok"
        assert sent["task"]["status"] == "completed"
        router.route.assert_awaited_once()

        canceled = await _call_tool(mcp_app, "a2a_cancel_task", {"task_id": task_id})
        assert canceled["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_task_get_and_cancel_fail_closed(
        self, mcp_app, monkeypatch, tmp_path
    ):
        manager = TaskManager(MagicMock(), storage_path=str(tmp_path / "tasks.json"))
        monkeypatch.setattr(
            "agora.server.tools_governance._get_task_manager", lambda: manager
        )

        queried = await _call_tool(mcp_app, "a2a_get_task", {"task_id": "missing"})
        canceled = await _call_tool(mcp_app, "a2a_cancel_task", {"task_id": "missing"})
        assert queried["status"] == "error"
        assert canceled["status"] == "error"

    @pytest.mark.asyncio
    async def test_invalid_arguments_do_not_create_task(
        self, mcp_app, monkeypatch, tmp_path
    ):
        manager = TaskManager(MagicMock(), storage_path=str(tmp_path / "tasks.json"))
        monkeypatch.setattr(
            "agora.server.tools_governance._get_task_manager", lambda: manager
        )

        result = await _call_tool(
            mcp_app,
            "a2a_send_task",
            {"tool_name": "g1.smoke.noop", "arguments": "{"},
        )
        assert result["status"] == "error"
        assert manager.list_tasks() == []


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
