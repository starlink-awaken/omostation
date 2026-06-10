"""Hermes MCP tools -- bridge between Hermes Console and Agora/Kairon.

Registers console-facing MCP tools: search, agent.list, agent.tasks,
agent.chat, health.services, health.alerts.

Each tool tries real data first, falls back to generated mock data
matching the Hermes Console's expected response format.
"""

from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)


class HermesToolRegistry:
    """Registers Hermes Console MCP tools on a FastMCP server."""

    def __init__(self, mcp_server: Any) -> None:
        self._mcp = mcp_server
        self._setup_tools()

    # ------------------------------------------------------------------
    # Tool: search
    # ------------------------------------------------------------------

    async def _tool_search(self, query: str, max_results: int = 10) -> dict[str, Any]:
        """Search the knowledge graph. Returns results matching SearchResult."""
        results: list[dict[str, Any]] = []
        try:
            from kos.semantic import semantic_search

            raw = semantic_search(query, limit=max_results)
            items = raw.get("results", raw) if isinstance(raw, dict) else raw
            for r in list(items)[:max_results]:
                results.append(
                    {
                        "id": str(getattr(r, "id", r.get("id", ""))),
                        "title": getattr(r, "title", r.get("title", "")),
                        "snippet": str(
                            getattr(
                                r, "snippet", r.get("snippet", r.get("content", ""))
                            )
                        )[:300],
                        "score": float(getattr(r, "score", r.get("score", 0.5))),
                        "source": getattr(r, "source", r.get("source", "kairon")),
                    }
                )
            _log.debug("[hermes] search: %d real results from kos", len(results))
        except ImportError:
            _log.debug("[hermes] search: kos unavailable, using generated data")
            results = self._mock_search(query, max_results)
        except Exception as exc:
            _log.warning("[hermes] search error: %s", exc)
            results = self._mock_search(query, max_results)
        return {"results": results}

    def _mock_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        q = query.lower()
        base = [
            {
                "id": "1",
                "title": "Knowledge Graph Construction Pipeline",
                "snippet": "End-to-end pipeline for extracting entities and relationships from unstructured text using LLM-based entity resolution.",
                "score": 0.94,
                "source": "kairon/kos",
            },
            {
                "id": "2",
                "title": "Multi-Agent Orchestration with Agora",
                "snippet": "Agora provides MCP-compatible gateway routing, service discovery, and circuit breaking for multi-agent coordination.",
                "score": 0.91,
                "source": "kairon/agora",
            },
            {
                "id": "3",
                "title": "Semantic Search over Knowledge Graphs",
                "snippet": "Hybrid vector + keyword search over ontology-grounded knowledge graphs using embedding models.",
                "score": 0.87,
                "source": "kairon/kos",
            },
            {
                "id": "4",
                "title": "Agent Runtime Engine Architecture",
                "snippet": "Agent runtime provides orchestrator, DSL parser, swarm protocol, governance, and capability discovery.",
                "score": 0.83,
                "source": "kairon/agent-runtime",
            },
            {
                "id": "5",
                "title": "Circuit Engine for Fault-Tolerant Workflows",
                "snippet": "YAML-defined circuit DAGs with step-level retry, timeout, and conditional branching.",
                "score": 0.79,
                "source": "kairon/core-models",
            },
            {
                "id": "6",
                "title": "Neural Center Service Registry",
                "snippet": "NeuralCenter provides service registration, health-aware discovery, and signal routing.",
                "score": 0.74,
                "source": "kairon/core-models",
            },
        ]
        matched = [
            r for r in base if q in r["title"].lower() or q in r["snippet"].lower()
        ]  # type: ignore[attr-defined]
        return (matched if matched else base[:3])[:max_results]

    # ------------------------------------------------------------------
    # Tool: agent.list
    # ------------------------------------------------------------------

    async def _tool_agent_list(self) -> dict[str, Any]:
        """List registered agents with status and capabilities."""
        agents: list[dict[str, Any]] = []
        try:
            from agent_runtime.agent_pool import AgentPool  # type: ignore[import-not-found]

            pool = AgentPool()
            for agent in pool.list_all():
                agents.append(
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "status": "online" if agent.status == "idle" else agent.status,
                        "capabilities": agent.capabilities,
                        "lastSeen": int(time.time() * 1000),
                    }
                )
            _log.debug("[hermes] agent.list: %d real agents", len(agents))
        except ImportError:
            _log.debug("[hermes] agent.list: using mock data")
            agents = self._mock_agents()
        return {"agents": agents}

    def _mock_agents(self) -> list[dict[str, Any]]:
        now = int(time.time() * 1000)
        return [
            {
                "id": "a1",
                "name": "Researcher",
                "status": "online",
                "capabilities": ["search", "analyze", "summarize"],
                "lastSeen": now,
            },
            {
                "id": "a2",
                "name": "Code Assistant",
                "status": "busy",
                "capabilities": ["generate", "review", "refactor"],
                "lastSeen": now - 8000,
            },
            {
                "id": "a3",
                "name": "Data Analyst",
                "status": "online",
                "capabilities": ["query", "visualize", "report"],
                "lastSeen": now - 30000,
            },
            {
                "id": "a4",
                "name": "Scheduler",
                "status": "offline",
                "capabilities": ["plan", "dispatch", "monitor"],
                "lastSeen": now - 7200000,
            },
        ]

    # ------------------------------------------------------------------
    # Tool: agent.tasks
    # ------------------------------------------------------------------

    async def _tool_agent_tasks(self) -> dict[str, Any]:
        """List active and recent tasks."""
        tasks: list[dict[str, Any]] = []
        try:
            from agent_runtime.task_scheduler import TaskScheduler  # type: ignore[import-not-found]

            scheduler = TaskScheduler()
            for t in scheduler._tasks.values():
                tasks.append(
                    {
                        "id": t.id,
                        "description": t.action,
                        "status": t.status.value,
                        "agent": t.agent_id,
                        "progress": 1.0
                        if t.status.value == "completed"
                        else (0.5 if t.status.value == "running" else 0.0),
                        "created": int(time.time() * 1000),
                    }
                )
            _log.debug("[hermes] agent.tasks: %d real tasks", len(tasks))
        except (ImportError, AttributeError):
            _log.debug("[hermes] agent.tasks: using mock data")
            tasks = self._mock_tasks()
        return {"tasks": tasks}

    def _mock_tasks(self) -> list[dict[str, Any]]:
        now = int(time.time() * 1000)
        return [
            {
                "id": "t1",
                "description": "Analyze knowledge graph connectivity",
                "status": "running",
                "agent": "Researcher",
                "progress": 0.75,
                "created": now - 600000,
            },
            {
                "id": "t2",
                "description": "Generate quarterly summary report",
                "status": "completed",
                "agent": "Data Analyst",
                "progress": 1.0,
                "created": now - 3600000,
            },
            {
                "id": "t3",
                "description": "Index new document corpus",
                "status": "running",
                "agent": "Scheduler",
                "progress": 0.3,
                "created": now - 120000,
            },
            {
                "id": "t4",
                "description": "Validate ontology schema",
                "status": "pending",
                "agent": "Researcher",
                "progress": 0.0,
                "created": now - 5000,
            },
        ]

    # ------------------------------------------------------------------
    # Tool: agent.chat
    # ------------------------------------------------------------------

    async def _tool_agent_chat(self, message: str) -> dict[str, Any]:
        """Process a chat message and return a response."""
        try:
            from agent_runtime.engine import Engine  # type: ignore[attr-defined, import-not-found]

            engine = Engine()
            result = engine.run_task(message)
            return {
                "response": result.get("response", result.get("output", str(result)))
            }
        except ImportError:
            return {
                "response": f"Received: '{message}'. Connect to agent-runtime for live interaction."
            }

    # ------------------------------------------------------------------
    # Tool: health.services
    # ------------------------------------------------------------------

    async def _tool_health_services(self) -> dict[str, Any]:
        """List service health statuses."""
        services: list[dict[str, Any]] = []
        try:
            from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]

            registry = ServiceRegistry()
            for svc in registry.list_all() if hasattr(registry, "list_all") else []:
                services.append(
                    {
                        "name": svc.name,
                        "status": "healthy" if svc.healthy else "degraded",
                        "lastHeartbeat": int(svc.last_health_check * 1000)
                        if svc.last_health_check
                        else int(time.time() * 1000),
                    }
                )
        except (ImportError, AttributeError):
            services = self._mock_services()
        if not services:
            services = self._mock_services()
        return {"services": services}

    def _mock_services(self) -> list[dict[str, Any]]:
        now = int(time.time() * 1000)
        return [
            {
                "name": "Kairon KOS API",
                "status": "healthy",
                "lastHeartbeat": now - 2000,
            },
            {
                "name": "Agora MCP Gateway",
                "status": "healthy",
                "lastHeartbeat": now - 1000,
            },
            {"name": "Agent Runtime", "status": "healthy", "lastHeartbeat": now - 5000},
            {
                "name": "Knowledge Graph Indexer",
                "status": "healthy",
                "lastHeartbeat": now - 15000,
            },
            {
                "name": "Task Scheduler",
                "status": "degraded",
                "lastHeartbeat": now - 60000,
            },
            {
                "name": "Legacy SharedBrain Bridge",
                "status": "offline",
                "lastHeartbeat": now - 300000,
            },
        ]

    # ------------------------------------------------------------------
    # Tool: health.alerts
    # ------------------------------------------------------------------

    async def _tool_health_alerts(self) -> dict[str, Any]:
        """List system alerts."""
        alerts: list[dict[str, Any]] = []
        try:
            from kairon_observability.alerts import AlertManager

            manager = AlertManager()
            for a in manager.get_active() if hasattr(manager, "get_active") else []:
                alerts.append(
                    {
                        "id": a.get("id", "")
                        if isinstance(a, dict)
                        else getattr(a, "id", ""),
                        "severity": a.get("severity", "info")
                        if isinstance(a, dict)
                        else getattr(a, "severity", "info"),
                        "message": a.get("message", "")
                        if isinstance(a, dict)
                        else getattr(a, "message", ""),
                        "source": a.get("source", "")
                        if isinstance(a, dict)
                        else getattr(a, "source", ""),
                        "timestamp": a.get("timestamp", int(time.time() * 1000))
                        if isinstance(a, dict)
                        else int(time.time() * 1000),
                    }
                )
        except (ImportError, AttributeError):
            alerts = self._mock_alerts()
        if not alerts:
            alerts = self._mock_alerts()
        return {"alerts": alerts}

    def _mock_alerts(self) -> list[dict[str, Any]]:
        now = int(time.time() * 1000)
        return [
            {
                "id": "a1",
                "severity": "warning",
                "message": "Task Scheduler response time exceeds 500ms threshold",
                "source": "Latency Monitor",
                "timestamp": now - 120000,
            },
            {
                "id": "a2",
                "severity": "info",
                "message": "KOS index cycle completed: 12,847 entities indexed",
                "source": "Indexer",
                "timestamp": now - 600000,
            },
            {
                "id": "a3",
                "severity": "info",
                "message": "Researcher agent dispatched to analyze graph connectivity",
                "source": "Agent Runtime",
                "timestamp": now - 900000,
            },
        ]

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _setup_tools(self) -> None:
        """Register all tools with the MCP server, using proper MCP tool names."""
        tools = [
            ("search", self._tool_search, "Search the knowledge graph"),
            ("agent.list", self._tool_agent_list, "List registered agents"),
            ("agent.tasks", self._tool_agent_tasks, "List agent tasks"),
            ("agent.chat", self._tool_agent_chat, "Process a chat message"),
            (
                "health.services",
                self._tool_health_services,
                "List service health status",
            ),
            ("health.alerts", self._tool_health_alerts, "List system alerts"),
        ]
        for name, handler, desc in tools:
            try:
                self._mcp.tool(name=name, description=desc)(handler)
                _log.info("[hermes] registered tool: %s", name)
            except Exception as exc:
                _log.warning("[hermes] tool registration failed for %s: %s", name, exc)


def setup_hermes_tools(mcp_server: Any) -> HermesToolRegistry:
    """Register all Hermes Console MCP tools on the given FastMCP instance."""
    return HermesToolRegistry(mcp_server)
