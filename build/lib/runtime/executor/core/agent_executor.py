"""Individual agent execution lifecycle — spawn, run, monitor, terminate.

Migrated from agentmesh agent-execution.ts (benchmarks/simulated) + core
execution lifecycle patterns from agent-runner.ts.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AgentExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentExecutionState:
    """Runtime state for a single agent execution."""

    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_name: str = ""
    status: AgentExecutionStatus = AgentExecutionStatus.PENDING
    task: str = ""
    output: str | None = None
    error: str | None = None
    retry_count: int = 0
    token_usage: int = 0
    started_at: float = 0.0
    completed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Context passed to the execution function."""

    agent_name: str
    task: str
    context: str | None = None
    retry_attempt: int = 0
    state: AgentExecutionState | None = None


ExecuteFunc = Callable[[ExecutionContext], Any]


class AgentExecutor:
    """Orchestrate a single agent's execution lifecycle with retry support."""

    def __init__(
        self,
        execute_fn: ExecuteFunc,
        max_retries: int = 3,
        base_backoff_ms: float = 1000,
    ) -> None:
        self._execute_fn = execute_fn
        self._max_retries = max_retries
        self._base_backoff_ms = base_backoff_ms

    async def execute(
        self,
        agent_name: str,
        task: str,
        context: str | None = None,
    ) -> AgentExecutionState:
        state = AgentExecutionState(
            agent_name=agent_name,
            status=AgentExecutionStatus.RUNNING,
            task=task,
            started_at=time.time(),
        )
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                state.status = AgentExecutionStatus.RETRYING
                state.retry_count = attempt
                await asyncio.sleep(self._backoff(attempt) / 1000)
            try:
                exec_ctx = ExecutionContext(
                    agent_name=agent_name,
                    task=task,
                    context=context,
                    retry_attempt=attempt,
                    state=state,
                )
                result = await self._execute_fn(exec_ctx) if asyncio.iscoroutinefunction(self._execute_fn) else self._execute_fn(exec_ctx)
                state.output = result.get("output") if isinstance(result, dict) else str(result)
                state.token_usage = result.get("tokens", 0) if isinstance(result, dict) else 0
                state.status = AgentExecutionStatus.COMPLETED
                state.completed_at = time.time()
                state.error = None
                return state
            except Exception as exc:
                state.error = str(exc)
                if attempt >= self._max_retries:
                    state.status = AgentExecutionStatus.FAILED
                    state.completed_at = time.time()
                    return state
        state.status = AgentExecutionStatus.FAILED
        state.completed_at = time.time()
        return state

    def _backoff(self, attempt: int) -> float:
        return self._base_backoff_ms * (2 ** (attempt - 1))

    def cancel(self, state: AgentExecutionState) -> bool:
        if state.status not in (AgentExecutionStatus.RUNNING, AgentExecutionStatus.RETRYING):
            return False
        state.status = AgentExecutionStatus.CANCELLED
        state.completed_at = time.time()
        return True
