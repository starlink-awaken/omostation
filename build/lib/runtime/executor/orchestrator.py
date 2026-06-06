"""Orchestrator — task orchestration engine with DAG scheduling, parallel execution, and state management."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from runtime.executor.core.agent_runner import AgentDefinition, AgentPool, AgentRunner

# ---------------------------------------------------------------------------
# Enums & Types
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    INIT = "init"
    RESEARCH = "research"
    DECISION = "decision"
    EXECUTION = "execution"
    FEEDBACK = "feedback"
    DELIVERY = "delivery"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class DecisionPath(StrEnum):
    EXPRESS = "express"
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"
    FULL = "full"


class EngineEvent(StrEnum):
    PROJECT_CREATED = "project:created"
    PROJECT_STARTED = "project:started"
    PROJECT_COMPLETED = "project:completed"
    PROJECT_FAILED = "project:failed"
    PROJECT_PAUSED = "project:paused"
    PHASE_ENTERED = "phase:entered"
    PHASE_COMPLETED = "phase:completed"
    PHASE_FAILED = "phase:failed"
    AGENT_STARTED = "agent:started"
    AGENT_COMPLETED = "agent:completed"
    AGENT_FAILED = "agent:failed"
    CHECKPOINT_CREATED = "checkpoint:created"
    CHECKPOINT_RESTORED = "checkpoint:restored"
    DECISION_MADE = "decision:made"


@dataclass
class Task:
    """A unit of work with dependency tracking."""

    task_id: str
    name: str
    agent_name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    result: Any = None
    error: str | None = None


@dataclass
class ProjectConfig:
    name: str
    description: str = ""
    archetype: str = "custom"
    complexity: str = "standard"
    goals: list[str] = field(default_factory=list)
    token_budget: int = 300_000
    max_concurrent: int = 6


@dataclass
class ProjectState:
    project_id: str
    project_name: str
    current_phase: str = Phase.INIT.value
    phase_history: list[dict[str, Any]] = field(default_factory=list)
    total_token_usage: int = 0
    token_budget: int = 300_000
    created_at: float = 0.0
    updated_at: float = 0.0
    active_tasks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """Manages project lifecycle, phase transitions, and parallel agent execution."""

    def __init__(self, agent_pool: AgentPool | None = None) -> None:
        self._agent_pool = agent_pool or AgentPool()
        self._runner: AgentRunner = self._agent_pool.get_runner()
        self._project_state: ProjectState | None = None
        self._event_handlers: dict[str, list[Any]] = {}
        self._tasks: dict[str, Task] = {}

    # -- Project lifecycle ---------------------------------------------------

    def create_project(self, config: ProjectConfig) -> ProjectState:
        now = time.time()
        state = ProjectState(
            project_id=uuid.uuid4().hex[:16],
            project_name=config.name,
            current_phase=Phase.INIT.value,
            token_budget=config.token_budget,
            created_at=now,
            updated_at=now,
        )
        self._project_state = state
        self._emit(EngineEvent.PROJECT_CREATED, {"project_id": state.project_id, "name": config.name})
        return state

    async def start_project(self, config: ProjectConfig | None = None) -> None:
        if config and self._project_state is None:
            self.create_project(config)
        if self._project_state is None:
            msg = "No project. Call create_project() first."
            raise RuntimeError(msg)

        self._project_state.updated_at = time.time()
        self._emit(EngineEvent.PROJECT_STARTED, {"project_id": self._project_state.project_id})

        await self._transition_to(Phase.RESEARCH)

    async def run_current_phase(self) -> None:
        if self._project_state is None:
            msg = "No active project"
            raise RuntimeError(msg)

        phase = Phase(self._project_state.current_phase)
        self._emit(EngineEvent.PHASE_ENTERED, {"project_id": self._project_state.project_id, "phase": phase.value})

        try:
            layer = self._layer_for_phase(phase)
            if layer:
                await self._run_agents_for_phase(phase)

            self._emit(EngineEvent.PHASE_COMPLETED, {"project_id": self._project_state.project_id, "phase": phase.value})

            next_phase = self._next_phase(phase)
            if next_phase and next_phase != Phase.COMPLETED:
                await self._transition_to(next_phase)
                await self.run_current_phase()
            elif next_phase == Phase.COMPLETED:
                self._project_state.current_phase = Phase.COMPLETED.value
                self._emit(EngineEvent.PROJECT_COMPLETED, {"project_id": self._project_state.project_id})

        except Exception as exc:
            self._project_state.current_phase = Phase.FAILED.value
            self._emit(EngineEvent.PHASE_FAILED, {"project_id": self._project_state.project_id, "error": str(exc)})
            self._emit(EngineEvent.PROJECT_FAILED, {"project_id": self._project_state.project_id})

    def pause_project(self, reason: str = "") -> None:
        if self._project_state is None:
            msg = "No active project"
            raise RuntimeError(msg)
        self._project_state.current_phase = Phase.PAUSED.value
        self._project_state.updated_at = time.time()
        self._emit(EngineEvent.PROJECT_PAUSED, {"reason": reason})

    def resume_project(self) -> None:
        if self._project_state is None or self._project_state.current_phase != Phase.PAUSED.value:
            msg = "Project not paused"
            raise RuntimeError(msg)
        self._project_state.current_phase = Phase.INIT.value
        self._project_state.updated_at = time.time()

    # -- DAG scheduling ------------------------------------------------------

    def add_task(self, task: Task) -> None:
        self._tasks[task.task_id] = task

    def get_topological_batches(self) -> list[list[Task]]:
        in_degree: dict[str, int] = {}
        for t in self._tasks.values():
            in_degree.setdefault(t.task_id, 0)
            for dep_id in t.dependencies:
                in_degree[t.task_id] = in_degree.get(t.task_id, 0) + 1

        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        batches: list[list[Task]] = []
        processed: set[str] = set()

        while queue:
            batch: list[Task] = []
            for _ in range(len(queue)):
                tid = queue.popleft()
                if tid in processed:
                    continue
                processed.add(tid)
                batch.append(self._tasks[tid])
            if batch:
                batches.append(batch)

            for task in self._tasks.values():
                if task.task_id in processed:
                    continue
                task.status = TaskStatus.BLOCKED
                deps_met = all(d in processed for d in task.dependencies)
                if deps_met:
                    task.status = TaskStatus.READY
                    queue.append(task.task_id)

        return batches

    # -- Event system --------------------------------------------------------

    def on(self, event: EngineEvent, handler: Any) -> callable:  # type: ignore[valid-type]
        key = event.value
        self._event_handlers.setdefault(key, []).append(handler)

        def unsubscribe() -> None:
            handlers = self._event_handlers.get(key, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def _emit(self, event: EngineEvent, data: dict[str, Any]) -> None:
        handlers = self._event_handlers.get(event.value, [])
        payload = {"event": event.value, "timestamp": time.time(), "data": data}
        for h in handlers:
            try:
                result = h(payload)
                if hasattr(result, "__await__"):
                    import asyncio as _asyncio

                    _asyncio.ensure_future(result)
            except Exception:
                pass

    # -- Internals -----------------------------------------------------------

    async def _transition_to(self, target: Phase) -> None:
        if self._project_state is None:
            return
        self._project_state.current_phase = target.value
        self._project_state.phase_history.append({"from": self._project_state.current_phase, "to": target.value, "timestamp": time.time()})
        self._project_state.updated_at = time.time()

    async def _run_agents_for_phase(self, phase: Phase) -> None:
        if self._project_state is None:
            return
        layer = self._layer_for_phase(phase)
        if layer is None:
            return

        agents = self._agent_pool.get_active(self._project_state.current_phase)  # type: ignore[attr-defined]
        layer_agents = [a for a in agents if a.layer == layer]
        if not layer_agents:
            return

        max_conc = 4
        for i in range(0, len(layer_agents), max_conc):
            batch = layer_agents[i : i + max_conc]
            results = await asyncio.gather(*[self._run_single(a) for a in batch], return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    continue

    async def _run_single(self, definition: AgentDefinition) -> None:
        if self._project_state is None:
            return
        self._emit(EngineEvent.AGENT_STARTED, {"agent_name": definition.name})

        try:
            state = await self._runner.run(definition, "Execute current phase")  # type: ignore[attr-defined]
            self._project_state.total_token_usage += state.token_usage
            if state.status.value == "completed":
                self._emit(EngineEvent.AGENT_COMPLETED, {"agent_name": definition.name, "tokens": state.token_usage})
            else:
                self._emit(EngineEvent.AGENT_FAILED, {"agent_name": definition.name, "error": state.last_error})
        except Exception as exc:
            self._emit(EngineEvent.AGENT_FAILED, {"agent_name": definition.name, "error": str(exc)})

    @staticmethod
    def _layer_for_phase(phase: Phase) -> str | None:
        mapping = {
            Phase.RESEARCH: "L1",
            Phase.DECISION: "L2",
            Phase.EXECUTION: "L3",
            Phase.FEEDBACK: "L4",
        }
        return mapping.get(phase)

    @staticmethod
    def _next_phase(phase: Phase) -> Phase | None:
        sequence = [
            Phase.INIT,
            Phase.RESEARCH,
            Phase.DECISION,
            Phase.EXECUTION,
            Phase.FEEDBACK,
            Phase.DELIVERY,
            Phase.COMPLETED,
        ]
        try:
            idx = sequence.index(phase)
            return sequence[idx + 1] if idx + 1 < len(sequence) else None
        except ValueError:
            return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "phase": self._project_state.current_phase if self._project_state else None,
            "token_usage": self._project_state.total_token_usage if self._project_state else 0,
            "tasks": len(self._tasks),
            "active_agents": len(self._agent_pool.list_all()),
        }
