"""Agent Registry — capability-based task dispatcher."""

from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import AgentInfo, AgentStatus
from .store import RegistryStore

logger = logging.getLogger(__name__)


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskRequest:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    priority: int = 0
    payload: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TaskAssignment:
    task_id: str
    agent_id: str
    agent_name: str
    assigned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: TaskStatus = TaskStatus.DISPATCHED


class Dispatcher:
    def __init__(self, store: RegistryStore) -> None:
        self._store = store
        self._assignments: dict[str, TaskAssignment] = {}
        self._pending: dict[str, TaskRequest] = {}

    def submit(self, request: TaskRequest) -> TaskAssignment | None:
        candidates = self._find_capable_agents(request.required_capabilities)
        if not candidates:
            self._pending[request.task_id] = request
            return None
        agent = self._select_best(candidates)
        return self._assign(request, agent)

    def dispatch_pending(self) -> list[TaskAssignment]:
        assigned = []
        still_pending = {}
        for task_id, request in self._pending.items():
            candidates = self._find_capable_agents(request.required_capabilities)
            if candidates:
                agent = self._select_best(candidates)
                assigned.append(self._assign(request, agent))
            else:
                still_pending[task_id] = request
        self._pending = still_pending
        return assigned

    def complete(self, task_id: str) -> bool:
        assignment = self._assignments.get(task_id)
        if assignment is None:
            return False
        assignment.status = TaskStatus.COMPLETED
        agent = self._store.get_agent(assignment.agent_id)
        if agent and agent.active_tasks > 0:
            new_count = agent.active_tasks - 1
            self._store.update_agent(agent.agent_id, active_tasks=new_count)
            if new_count == 0:
                self._store.update_agent(agent.agent_id, status=AgentStatus.IDLE)
        return True

    def fail(self, task_id: str) -> bool:
        assignment = self._assignments.get(task_id)
        if assignment is None:
            return False
        assignment.status = TaskStatus.FAILED
        agent = self._store.get_agent(assignment.agent_id)
        if agent and agent.active_tasks > 0:
            self._store.update_agent(agent.agent_id, active_tasks=agent.active_tasks - 1)
        return True

    def get_assignment(self, task_id: str) -> TaskAssignment | None:
        return self._assignments.get(task_id)

    def get_pending(self) -> list[TaskRequest]:
        return list(self._pending.values())

    def get_assignments(self, status: TaskStatus | None = None) -> list[TaskAssignment]:
        result = list(self._assignments.values())
        if status is not None:
            result = [a for a in result if a.status == status]
        return result

    def stats(self) -> dict:
        all_a = list(self._assignments.values())
        return {
            "total_submitted": len(all_a) + len(self._pending),
            "dispatched": len([a for a in all_a if a.status == TaskStatus.DISPATCHED]),
            "completed": len([a for a in all_a if a.status == TaskStatus.COMPLETED]),
            "failed": len([a for a in all_a if a.status == TaskStatus.FAILED]),
            "pending": len(self._pending),
        }

    def _find_capable_agents(self, required: list[str]) -> list[AgentInfo]:
        idle = self._store.find_agents(status=AgentStatus.IDLE)
        busy = self._store.find_agents(status=AgentStatus.BUSY)
        return [a for a in idle + busy if a.can_handle(required) and a.load_ratio < 1.0]

    def _select_best(self, candidates: list[AgentInfo]) -> AgentInfo:
        return min(candidates, key=lambda a: (a.load_ratio, a.active_tasks))

    def _assign(self, request: TaskRequest, agent: AgentInfo) -> TaskAssignment:
        self._store.update_agent(agent.agent_id, active_tasks=agent.active_tasks + 1, status=AgentStatus.BUSY)
        assignment = TaskAssignment(task_id=request.task_id, agent_id=agent.agent_id, agent_name=agent.name)
        self._assignments[request.task_id] = assignment
        return assignment


__all__ = ["Dispatcher", "TaskAssignment", "TaskRequest", "TaskStatus"]
