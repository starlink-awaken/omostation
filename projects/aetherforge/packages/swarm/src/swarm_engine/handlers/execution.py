from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from .command import Command, get_registry

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class _AgentOrchestratorProtocol(Protocol):
    def receive_vision(self, goal: str, metadata: dict[str, Any] | None = None) -> str: ...
    async def _handle_spawn(self, params: dict[str, Any]) -> dict[str, Any]: ...
    async def _handle_rollback(self, params: dict[str, Any]) -> dict[str, Any]: ...
    def get_status(self) -> dict[str, Any]: ...


class _ToolDispatcherProtocol(Protocol):
    def list_tools(self) -> list[str]: ...


class _ExecutionCompatProtocol(Protocol):
    def task_list(self) -> dict[str, Any]: ...
    def task_status(self, params: dict[str, Any] | None) -> dict[str, Any]: ...
    def results_list(self) -> dict[str, Any]: ...
    def swarm_radar(self) -> dict[str, Any]: ...
    def swarm_governance_action(self, params: dict[str, Any] | None) -> dict[str, Any]: ...
    def log_tail(self, limit: int = 100) -> list[dict[str, Any]]: ...
    def log_size(self) -> int: ...


class _IntentDigestCommand(Command):
    """Handles bos://execution/intent/digest."""

    def __init__(self, agent_orchestrator: _AgentOrchestratorProtocol) -> None:
        self._orchestrator = agent_orchestrator

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        payload = params or {}
        goal = str(payload.get("goal") or payload.get("intent") or "").strip()
        if not goal:
            return {"status": "error", "message": "Intent goal is required"}
        journey_metadata = {
            "journey_id": str(payload.get("journey_id") or "").strip(),
            "journey_display_name": str(payload.get("journey_display_name") or "").strip(),
        }
        journey_metadata = {key: value for key, value in journey_metadata.items() if value}
        try:
            if journey_metadata:
                task_id = self._orchestrator.receive_vision(goal, metadata=journey_metadata)
            else:
                task_id = self._orchestrator.receive_vision(goal)
        except (AttributeError, OSError, ValueError, RuntimeError) as exc:
            return {"status": "error", "message": f"Intent digest failed: {exc}"}
        return {
            "status": "success",
            "data": {
                "task_id": task_id,
                "intent": goal,
                "phase": "Anchoring",
                "progress": 0,
                **journey_metadata,
            },
        }


class _VisionSubmitCommand(Command):
    """Handles bos://execution/vision/submit."""

    def __init__(self, agent_orchestrator: _AgentOrchestratorProtocol) -> None:
        self._orchestrator = agent_orchestrator

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        goal = (params or {}).get("objective")
        if not goal:
            return {"status": "error", "message": "vision objective required"}
        task_id = self._orchestrator.receive_vision(goal)
        return {"status": "success", "task_id": task_id}


class _TaskSpawnCommand(Command):
    """Handles bos://execution/task/spawn."""

    def __init__(self, agent_orchestrator: _AgentOrchestratorProtocol) -> None:
        self._orchestrator = agent_orchestrator

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return await self._orchestrator._handle_spawn(params or {})


class _TaskRollbackCommand(Command):
    """Handles bos://execution/task/rollback."""

    def __init__(self, agent_orchestrator: _AgentOrchestratorProtocol) -> None:
        self._orchestrator = agent_orchestrator

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return await self._orchestrator._handle_rollback(params or {})


class _TaskListCommand(Command):
    """Handles bos://execution/task/list."""

    def __init__(self, compat_helper: _ExecutionCompatProtocol) -> None:
        self._compat_helper = compat_helper

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return self._compat_helper.task_list()


class _TaskStatusCommand(Command):
    """Handles bos://execution/task/status."""

    def __init__(self, compat_helper: _ExecutionCompatProtocol) -> None:
        self._compat_helper = compat_helper

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return self._compat_helper.task_status(params)


class _ResultsListCommand(Command):
    """Handles bos://execution/results/list."""

    def __init__(self, compat_helper: _ExecutionCompatProtocol) -> None:
        self._compat_helper = compat_helper

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return self._compat_helper.results_list()


class _SwarmRadarCommand(Command):
    """Handles bos://execution/swarm/radar."""

    def __init__(self, compat_helper: _ExecutionCompatProtocol) -> None:
        self._compat_helper = compat_helper

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return self._compat_helper.swarm_radar()


class _SwarmGovernanceCommand(Command):
    """Handles bos://execution/swarm/governance_action."""

    def __init__(self, compat_helper: _ExecutionCompatProtocol) -> None:
        self._compat_helper = compat_helper

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        return self._compat_helper.swarm_governance_action(params)


class _AssociationTriggerCommand(Command):
    """Handles bos://execution/association/trigger."""

    async def execute(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        from .association_engine import AssociationEngine

        if not params or "intent" not in params:
            return {"status": "error", "message": "Missing 'intent' in parameters"}
        try:
            engine = AssociationEngine.get_instance()
            complexity = params.get("complexity", 1.0)
            hints = engine.trigger_association(params["intent"], complexity=complexity)
            return {"status": "success", "hints": hints}
        except ImportError:
            return {"status": "error", "message": "AssociationEngine not available"}


class ExecutionCallHandler:
    """Handles the "execution" domain calls.

    Uses Command pattern internally: each resource/action combination is
    mapped to a Command subclass.
    """

    def __init__(
        self,
        agent_orchestrator: _AgentOrchestratorProtocol,
        tool_dispatcher: _ToolDispatcherProtocol,
        compat_helper: _ExecutionCompatProtocol,
    ) -> None:
        self._agent_orchestrator = agent_orchestrator
        self._tool_dispatcher = tool_dispatcher
        self._compat_helper = compat_helper
        self._registry = get_registry()
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all execution-domain commands into the registry."""
        # Intent / Vision
        self._registry.register(
            "execution",
            "intent",
            "digest",
            _IntentDigestCommand(self._agent_orchestrator),
        )
        self._registry.register(
            "execution",
            "vision",
            "submit",
            _VisionSubmitCommand(self._agent_orchestrator),
        )

        # Task lifecycle
        self._registry.register(
            "execution",
            "task",
            "spawn",
            _TaskSpawnCommand(self._agent_orchestrator),
        )
        self._registry.register(
            "execution",
            "task",
            "rollback",
            _TaskRollbackCommand(self._agent_orchestrator),
        )
        self._registry.register(
            "execution",
            "task",
            "list",
            _TaskListCommand(self._compat_helper),
        )
        self._registry.register(
            "execution",
            "task",
            "status",
            _TaskStatusCommand(self._compat_helper),
        )

        # Results
        self._registry.register(
            "execution",
            "results",
            "list",
            _ResultsListCommand(self._compat_helper),
        )

        # Swarm
        self._registry.register(
            "execution",
            "swarm",
            "radar",
            _SwarmRadarCommand(self._compat_helper),
        )
        self._registry.register(
            "execution",
            "swarm",
            "governance_action",
            _SwarmGovernanceCommand(self._compat_helper),
        )

        # Association
        self._registry.register(
            "execution",
            "association",
            "trigger",
            _AssociationTriggerCommand(),
        )

    async def handle(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Handle execution domain calls via Command registry lookup."""
        if resource == "status":
            return self._handle_status()
        if resource == "log":
            limit = params.get("limit", 100) if params else 100
            return {"status": "success", "logs": self._compat_helper.log_tail(limit)}

        command = self._registry.get("execution", resource, action)
        if command is None:
            return {
                "status": "error",
                "message": f"Unknown execution resource: {resource}",
            }
        return await command.execute(resource, action, params)

    def _handle_status(self) -> dict[str, Any]:
        agent_status = self._agent_orchestrator.get_status()
        tool_list = self._tool_dispatcher.list_tools()
        return {
            "status": "success",
            "agents": agent_status,
            "tools": {"total": len(tool_list), "list": tool_list},
            "execution_log_size": self._compat_helper.log_size(),
        }
