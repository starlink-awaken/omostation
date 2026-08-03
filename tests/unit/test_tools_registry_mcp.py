"""Unit tests for agora.server.tools_registry_mcp — Phase 46 Agent Registry MCP bridge.

Tests:
  1. _request — HTTP client with error handling
  2. _parse_capabilities — JSON and comma-separated parsing
  3. registry_health — health check wrapper
  4. registry_register_agent — registration with capabilities
  5. registry_list_agents — list with filters
  6. registry_find_agent — capability-based find
  7. registry_agent_heartbeat — heartbeat
  8. registry_submit_task — task dispatch
  9. registry_list_tasks — task listing
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agora.server.tools_registry_mcp import (
    _REGISTRY_URL,
    _parse_capabilities,
    registry_agent_heartbeat,
    registry_find_agent,
    registry_health,
    registry_list_agents,
    registry_list_tasks,
    registry_register_agent,
    registry_submit_task,
)

# ── Tests: _parse_capabilities ─────────────────────────────────


class TestParseCapabilities:
    def test_empty_string(self):
        assert _parse_capabilities("") == []

    def test_comma_separated(self):
        result = _parse_capabilities("python, rust, go")
        assert len(result) == 3
        assert result[0] == {"name": "python"}
        assert result[1] == {"name": "rust"}
        assert result[2] == {"name": "go"}

    def test_json_array(self):
        result = _parse_capabilities('[{"name": "ml"}, {"name": "rust"}]')
        assert result == [{"name": "ml"}, {"name": "rust"}]

    def test_invalid_json_falls_back(self):
        result = _parse_capabilities("[invalid json")
        assert result == []


# ── Tests: _request ────────────────────────────────────────────


class TestRequest:
    @pytest.mark.asyncio
    async def test_returns_response_json(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"ok": true}'
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from agora.server.tools_registry_mcp import _request

            result = await _request("GET", "/health")

        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_handles_request_error(self):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request = AsyncMock(side_effect=OSError("Connection refused"))
            mock_client_cls.return_value = mock_client

            from agora.server.tools_registry_mcp import _request

            result = await _request("GET", "/health")

        assert "error" in result


# ── Tests: registry_health ─────────────────────────────────────


class TestRegistryHealth:
    @pytest.mark.asyncio
    async def test_returns_ok_when_reachable(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = {
                "status": "ok",
                "agents": 5,
                "nodes": 2,
                "healthy_agents": 4,
            }
            result = await registry_health()

        assert result["status"] == "ok"
        assert result["registry_status"] == "ok"
        assert result["agents"] == 5
        assert result["healthy_agents"] == 4

    @pytest.mark.asyncio
    async def test_returns_error_when_unreachable(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = {"error": "request_failed", "detail": "timeout"}
            result = await registry_health()

        assert "error" in str(result).lower() or result.get("error") is not None


# ── Tests: registry_register_agent ─────────────────────────────


class TestRegistryRegisterAgent:
    @pytest.mark.asyncio
    async def test_register_with_capabilities(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = {
                "agent_id": "abc123",
                "name": "test-agent",
                "node_id": "node-1",
                "status": "registered",
                "capabilities": [{"name": "python"}],
            }
            result = await registry_register_agent(
                name="test-agent",
                node_id="node-1",
                endpoint="http://localhost:9000",
                capabilities="python,rust",
            )

        assert result["status"] == "registered"
        assert result["agent_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_rejects_invalid_metadata(self):
        result = await registry_register_agent(name="test-agent", metadata="not json")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_non_object_metadata(self):
        result = await registry_register_agent(name="test-agent", metadata="[1,2,3]")
        assert "error" in result


# ── Tests: registry_list_agents ────────────────────────────────


class TestRegistryListAgents:
    @pytest.mark.asyncio
    async def test_list_all(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = [
                {"agent_id": "1", "name": "a"},
                {"agent_id": "2", "name": "b"},
            ]
            result = await registry_list_agents()

        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_list_with_filters(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = [{"agent_id": "1", "name": "a"}]
            await registry_list_agents(capability="python", status="idle")

            call_args = mock_req.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "/agents/find"
            assert call_args[1]["params"]["capability"] == "python"


# ── Tests: registry_find_agent ────────────────────────────────


class TestRegistryFindAgent:
    @pytest.mark.asyncio
    async def test_find_by_capability(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = [{"agent_id": "1", "name": "a"}]
            result = await registry_find_agent("python")

        assert result["capability"] == "python"
        assert result["count"] == 1


# ── Tests: registry_agent_heartbeat ───────────────────────────


class TestRegistryAgentHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = {"ok": True}
            result = await registry_agent_heartbeat("agent-123")

        assert result["status"] == "alive"
        assert result["agent_id"] == "agent-123"


# ── Tests: registry_submit_task ───────────────────────────────


class TestRegistrySubmitTask:
    @pytest.mark.asyncio
    async def test_submit_task(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = {
                "task_id": "t-1",
                "agent_id": "a-1",
                "agent_name": "worker-1",
                "status": "dispatched",
            }
            result = await registry_submit_task(
                name="task-1",
                required_capabilities="python",
                priority=5,
                payload='{"input": "data"}',
            )

        assert result["task_id"] == "t-1"
        assert result["status"] == "dispatched"

    @pytest.mark.asyncio
    async def test_submit_with_invalid_payload(self):
        result = await registry_submit_task(name="task-1", payload="not json")
        assert "error" in result


# ── Tests: registry_list_tasks ────────────────────────────────


class TestRegistryListTasks:
    @pytest.mark.asyncio
    async def test_list_all_tasks(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = [{"task_id": "t-1", "status": "pending"}]
            result = await registry_list_tasks()

        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self):
        with patch("agora.server.tools_registry_mcp._request") as mock_req:
            mock_req.return_value = []
            await registry_list_tasks(status="completed")

            call_args = mock_req.call_args
            assert call_args[1]["params"] == {"status": "completed"}


# ── Tests: configuration ───────────────────────────────────────


class TestConfig:
    def test_default_registry_url(self):
        assert _REGISTRY_URL == "http://localhost:8765"

    def test_registry_url_from_env(self):
        import os

        with patch.dict(os.environ, {"RUNTIME_REGISTRY_URL": "http://custom:9999"}):
            # Re-import to pick up env var
            import importlib

            import agora.server.tools_registry_mcp as mod

            importlib.reload(mod)
            assert mod._REGISTRY_URL == "http://custom:9999"
