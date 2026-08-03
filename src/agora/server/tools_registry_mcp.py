"""Agent Registry MCP tools — expose Agent Registry as agora MCP tools.

Phase 46 W1: Bridges the runtime FastAPI registry server with agora MCP,
allowing agents and operators to register/discover agents, send heartbeats,
and submit tasks through standardized MCP tools.

Configuration:
    RUNTIME_REGISTRY_URL: registry server base URL (default: http://localhost:8765)

Endpoints wrapped:
    GET  /health
    POST /agents              register_agent
    GET  /agents              list_agents
    GET  /agents/find         find_agents
    GET  /agents/{id}         get_agent
    POST /agents/{id}/heartbeat  agent_heartbeat
    DELETE /agents/{id}       deregister_agent
    POST /tasks               submit_task
    GET  /tasks               list_tasks
"""

from __future__ import annotations

import os

import structlog
from fastmcp import FastMCP

from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)

_REGISTRY_URL = os.environ.get("RUNTIME_REGISTRY_URL", "http://localhost:8765")


async def _request(
    method: str, path: str, json_body: dict | None = None, params: dict | None = None
) -> dict:
    """Async HTTP client for registry API."""
    import httpx

    url = f"{_REGISTRY_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(method, url, json=json_body, params=params)
            response.raise_for_status()
            return response.json() if response.content else {"ok": True}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "detail": str(e)}
    except (httpx.RequestError, OSError) as e:
        return {"error": "request_failed", "detail": str(e)}


def _parse_capabilities(caps_str: str) -> list[dict]:
    """Parse JSON or comma-separated capabilities string."""
    import json

    if not caps_str:
        return []
    if caps_str.startswith("["):
        try:
            parsed = json.loads(caps_str)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    return [{"name": c.strip()} for c in caps_str.split(",") if c.strip()]


# ═══════════════════════════════════════════════════════════════
# Tool Implementations
# ═══════════════════════════════════════════════════════════════


async def registry_health() -> dict:
    """Check Agent Registry server health."""
    result = await _request("GET", "/health")
    if "error" in result:
        return _error(f"Registry unreachable: {result.get('detail', result['error'])}")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "registry_status": result.get("status", "unknown"),
            "agents": result.get("agents", 0),
            "nodes": result.get("nodes", 0),
            "healthy_agents": result.get("healthy_agents", 0),
            "registry_url": _REGISTRY_URL,
        }
    )


async def registry_register_agent(
    name: str,
    node_id: str = "",
    endpoint: str = "",
    capabilities: str = "",
    max_concurrency: int = 1,
    metadata: str = "{}",
) -> dict:
    """Register a new agent with the Agent Registry.

    Args:
        name: Agent name (required)
        node_id: Optional node identifier
        endpoint: Optional agent endpoint URL
        capabilities: Comma-separated names or JSON list, e.g. "python,rust" or [{"name":"python"}]
        max_concurrency: Max concurrent tasks (default 1)
        metadata: JSON string of metadata dict
    """
    import json

    try:
        metadata_dict = json.loads(metadata) if metadata else {}
        if not isinstance(metadata_dict, dict):
            return _error("metadata must be a JSON object")
    except (json.JSONDecodeError, ValueError):
        return _error("metadata must be valid JSON")

    body = {
        "name": name,
        "node_id": node_id,
        "endpoint": endpoint,
        "capabilities": _parse_capabilities(capabilities),
        "max_concurrency": max_concurrency,
        "metadata": metadata_dict,
    }
    result = await _request("POST", "/agents", json_body=body)
    if "error" in result:
        return _error(f"Registration failed: {result.get('detail', result['error'])}")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "agent_id": result.get("agent_id", ""),
            "name": result.get("name", name),
            "node_id": result.get("node_id", node_id),
            "status": result.get("status", "registered"),
            "capabilities": result.get("capabilities", []),
        }
    )


async def registry_list_agents(
    capability: str = "", status: str = "", node_id: str = ""
) -> dict:
    """List agents in the registry, with optional filters.

    Args:
        capability: Filter by capability name
        status: Filter by status (idle/busy/offline/error/draining)
        node_id: Filter by node identifier
    """
    params: dict[str, str] = {}
    if capability:
        params["capability"] = capability
    if status:
        params["status"] = status
    if node_id:
        params["node_id"] = node_id

    if params:
        result = await _request("GET", "/agents/find", params=params)
    else:
        result = await _request("GET", "/agents")

    if isinstance(result, dict) and "error" in result:
        return _error(f"List failed: {result.get('detail', result['error'])}")

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "agents": result if isinstance(result, list) else [],
            "count": len(result) if isinstance(result, list) else 0,
        }
    )


async def registry_find_agent(capability: str) -> dict:
    """Find agents with a specific capability.

    Args:
        capability: Capability name to search for
    """
    result = await _request("GET", "/agents/find", params={"capability": capability})
    if isinstance(result, dict) and "error" in result:
        return _error(f"Find failed: {result.get('detail', result['error'])}")

    agents = result if isinstance(result, list) else []
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "capability": capability,
            "agents": agents,
            "count": len(agents),
        }
    )


async def registry_agent_heartbeat(agent_id: str) -> dict:
    """Send a heartbeat for a registered agent.

    Args:
        agent_id: Agent identifier to refresh
    """
    result = await _request("POST", f"/agents/{agent_id}/heartbeat")
    if "error" in result:
        return _error(f"Heartbeat failed: {result.get('detail', result['error'])}")
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "agent_id": agent_id,
            "status": "alive",
        }
    )


async def registry_submit_task(
    name: str,
    required_capabilities: str = "",
    priority: int = 0,
    payload: str = "{}",
) -> dict:
    """Submit a task to the dispatcher for routing to a capable agent.

    Args:
        name: Task name (required)
        required_capabilities: Comma-separated list of required capability names
        priority: Task priority (default 0, higher = more urgent)
        payload: JSON string of task payload
    """
    import json

    try:
        payload_dict = json.loads(payload) if payload else {}
        if not isinstance(payload_dict, dict):
            return _error("payload must be a JSON object")
    except (json.JSONDecodeError, ValueError):
        return _error("payload must be valid JSON")

    caps = [c.strip() for c in required_capabilities.split(",") if c.strip()]

    body = {
        "name": name,
        "required_capabilities": caps,
        "priority": priority,
        "payload": payload_dict,
    }
    result = await _request("POST", "/tasks", json_body=body)
    if "error" in result:
        return _error(f"Submit failed: {result.get('detail', result['error'])}")

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "task_id": result.get("task_id", ""),
            "agent_id": result.get("agent_id", ""),
            "agent_name": result.get("agent_name", ""),
            "status": result.get("status", "pending"),
        }
    )


async def registry_list_tasks(status: str = "") -> dict:
    """List tasks in the dispatcher.

    Args:
        status: Filter by status (pending/dispatched/completed/failed)
    """
    params = {"status": status} if status else None
    result = await _request("GET", "/tasks", params=params)
    if isinstance(result, dict) and "error" in result:
        return _error(f"List failed: {result.get('detail', result['error'])}")

    tasks = result if isinstance(result, list) else []
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "tasks": tasks,
            "count": len(tasks),
        }
    )


# ═══════════════════════════════════════════════════════════════
# Tool Registration
# ═══════════════════════════════════════════════════════════════


def register_registry_mcp_tools(mcp: FastMCP) -> None:
    """Register all Agent Registry MCP tools (Phase 46 W1)."""

    @mcp.tool()
    async def registry_health_tool() -> dict:
        """Check Agent Registry server health.

        Returns registry status, agent/node counts, and healthy agent count.
        Useful as a fast liveness probe before invoking other registry tools.
        """
        return await registry_health()

    @mcp.tool()
    async def registry_register_agent_tool(
        name: str,
        node_id: str = "",
        endpoint: str = "",
        capabilities: str = "",
        max_concurrency: int = 1,
        metadata: str = "{}",
    ) -> dict:
        """Register a new agent with the Agent Registry.

        Args:
            name: Agent name (required)
            node_id: Optional node identifier
            endpoint: Optional agent endpoint URL
            capabilities: Comma-separated names or JSON list
            max_concurrency: Max concurrent tasks (default 1)
            metadata: JSON string of metadata dict
        """
        return await registry_register_agent(
            name=name,
            node_id=node_id,
            endpoint=endpoint,
            capabilities=capabilities,
            max_concurrency=max_concurrency,
            metadata=metadata,
        )

    @mcp.tool()
    async def registry_list_agents_tool(
        capability: str = "",
        status: str = "",
        node_id: str = "",
    ) -> dict:
        """List agents with optional filters.

        Args:
            capability: Filter by capability name
            status: Filter by status
            node_id: Filter by node identifier
        """
        return await registry_list_agents(
            capability=capability, status=status, node_id=node_id
        )

    @mcp.tool()
    async def registry_find_agent_tool(capability: str) -> dict:
        """Find agents with a specific capability.

        Args:
            capability: Capability name to search for
        """
        return await registry_find_agent(capability=capability)

    @mcp.tool()
    async def registry_heartbeat_tool(agent_id: str) -> dict:
        """Send a heartbeat for a registered agent.

        Args:
            agent_id: Agent identifier to refresh
        """
        return await registry_agent_heartbeat(agent_id=agent_id)

    @mcp.tool()
    async def registry_submit_task_tool(
        name: str,
        required_capabilities: str = "",
        priority: int = 0,
        payload: str = "{}",
    ) -> dict:
        """Submit a task to the dispatcher for routing.

        Args:
            name: Task name (required)
            required_capabilities: Comma-separated required capabilities
            priority: Task priority (higher = more urgent)
            payload: JSON string of task payload
        """
        return await registry_submit_task(
            name=name,
            required_capabilities=required_capabilities,
            priority=priority,
            payload=payload,
        )

    @mcp.tool()
    async def registry_list_tasks_tool(status: str = "") -> dict:
        """List tasks in the dispatcher.

        Args:
            status: Filter by status (pending/dispatched/completed/failed)
        """
        return await registry_list_tasks(status=status)
