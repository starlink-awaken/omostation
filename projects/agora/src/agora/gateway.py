"""Main Gateway class for agentmesh gateway migration.

Orchestrates routing, task management, context, scheduling, and event bus.
"""

from __future__ import annotations

# Module-level singleton references — typed Any because the actual singletons
# may or may not be exported by their respective modules at runtime.
import importlib as _importlib
import logging
import time
from collections.abc import Callable
from typing import Any

from agora.context import context_manager  # type: ignore[import-not-found]
from agora.core.config import load_config  # type: ignore[import-not-found]
from agora.core.scheduler import scheduler  # type: ignore[import-not-found]
from agora.task_manager import task_manager  # type: ignore[import-not-found]
from agora.types import Agent, AgentMessage, GatewayConfig, Task  # type: ignore[import-not-found]

gateway_agent_registry: Any = _importlib.import_module("agora.agent_registry").gateway_agent_registry
gateway_event_bus: Any = _importlib.import_module("agora.event_bus").gateway_event_bus
gateway_pipeline: Any = _importlib.import_module("agora.pipeline").gateway_pipeline
gateway_router: Any = _importlib.import_module("agora.router").gateway_router

logger = logging.getLogger(__name__)

_instance: Gateway | None = None


def set_gateway(instance: Gateway) -> None:
    """Set the global Gateway singleton."""
    global _instance
    _instance = instance


def get_gateway() -> Gateway | None:
    """Get the global Gateway singleton."""
    return _instance


class Gateway:
    """Main gateway container — lifecycle management and component wiring."""

    def __init__(self, config: GatewayConfig | None = None) -> None:
        self.config = config or load_config()
        self.event_bus = gateway_event_bus
        self.router = gateway_router
        self.agent_registry = gateway_agent_registry
        self.task_manager = task_manager
        self.context_manager = context_manager
        self.scheduler = scheduler
        self.pipeline = gateway_pipeline
        self._started = False
        self._start_time: int = 0

        # Wire task manager to agent registry for adapter lookup
        self.task_manager.set_adapter_lookup(self.agent_registry.get)

    async def initialize(self) -> None:
        """Initialize all gateway components."""
        if self._started:
            return
        if self.config.routing:
            self.router.configure(self.config.routing.rules, self.config.routing.default_agent)
        for agent_cfg in self.config.agents:
            agent = Agent(
                id=agent_cfg.id,
                name=agent_cfg.name,
                type=agent_cfg.type,
                capabilities=list(agent_cfg.capabilities),
            )
            self.router.register_agent(agent)
        self.scheduler.start()
        self._started = True
        self._start_time = int(time.time() * 1000)
        logger.info("Gateway initialized")

    @property
    def uptime_seconds(self) -> int:
        """Seconds since gateway started."""
        if not self._started:
            return 0
        return int((time.time() * 1000 - self._start_time) / 1000)

    def health(self) -> dict[str, Any]:
        """Return a health status snapshot."""
        all_agents = self.router.get_all_agents()
        online_agents = self.router.get_online_agents()
        all_tasks = self.task_manager.get_all_tasks()

        def _count(status: str) -> int:
            return sum(1 for t in all_tasks if t.status == status)

        return {
            "status": "ok" if self._started else "starting",
            "uptime_seconds": self.uptime_seconds,
            "agents": {"total": len(all_agents), "online": len(online_agents)},
            "models": {"total": len(self.config.agents)},
            "tasks": {
                "pending": _count("pending"),
                "running": _count("running"),
                "completed": _count("completed"),
                "failed": _count("failed"),
            },
        }

    def _route_fn(self, message: AgentMessage) -> tuple[list[str], str]:
        return self.router.route(message)

    async def submit_task(self, message: AgentMessage) -> Task:
        """Submit a message as a task for routing and execution."""
        return await self.task_manager.process_task(message, self._route_fn)

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return self.task_manager.get_task(task_id)

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks."""
        return self.task_manager.get_all_tasks()

    def get_online_agents(self) -> list[Agent]:
        """Get currently online agents."""
        return self.router.get_online_agents()

    def get_all_agents(self) -> list[Agent]:
        """Get all registered agents."""
        return self.router.get_all_agents()

    async def create_space(self, metadata: dict[str, Any] | None = None) -> str:
        """Create a new shared context space."""
        return await self.context_manager.create_shared_space(metadata)

    def on_event(self, event_type: str, handler: Callable) -> Callable[[], None]:
        """Subscribe to an event type. Returns an unsubscribe function."""
        return self.event_bus.subscribe(event_type, handler)

    async def dispose(self) -> None:
        """Gracefully shut down all gateway components."""
        self.scheduler.stop()
        self.task_manager.purge_completed(30)
        self.event_bus.remove_all_listeners()
        self._started = False
        logger.info("Gateway disposed")
