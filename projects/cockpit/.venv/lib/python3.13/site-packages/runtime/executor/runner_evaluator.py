"""Agent execution runner + result evaluator.

Migrated from agentmesh agent-runner.ts (AgentRunner) + evaluator
patterns.

Provides:
- AgentRunner: full lifecycle management for agent execution
- RunEvaluator: evaluate execution results against quality gates
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AgentStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class EvaluationResult(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    WARN = "warn"


@dataclass
class AgentDefinition:
    name: str
    description: str
    layer: str = "L3"
    agent_type: str = "worker"
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    prompt_body: str = ""
    max_retries: int = 3
    token_budget: int = 100_000


@dataclass
class RunnerState:
    agent_name: str
    status: AgentStatus = AgentStatus.IDLE
    task: str = ""
    output: str | None = None
    error: str | None = None
    retry_count: int = 0
    token_usage: int = 0
    started_at: float = 0.0
    completed_at: float | None = None


@dataclass
class EvaluationCriteria:
    id: str
    name: str
    description: str = ""
    mandatory: bool = True
    threshold: float | None = None


@dataclass
class EvaluationReport:
    criteria_id: str
    criteria_name: str
    result: EvaluationResult
    detail: str = ""
    actual_value: float | None = None
    threshold: float | None = None


class AgentRunner:
    """Manages agent lifecycle: spawn, execute, monitor, terminate."""

    def __init__(self) -> None:
        self._states: dict[str, RunnerState] = {}
        self._definitions: dict[str, AgentDefinition] = {}
        self._exec_fn: Callable[..., Any] | None = None

    def set_executor(self, fn: Callable[..., Any]) -> None:
        self._exec_fn = fn

    def register_definition(self, definition: AgentDefinition) -> None:
        self._definitions[definition.name] = definition

    def get_definition(self, name: str) -> AgentDefinition | None:
        return self._definitions.get(name)

    async def run_agent(
        self,
        definition: AgentDefinition,
        task: str,
        context: str | None = None,
    ) -> RunnerState:
        state = RunnerState(
            agent_name=definition.name,
            status=AgentStatus.RUNNING,
            task=task,
            started_at=time.time(),
        )
        self._states[definition.name] = state
        max_retries = definition.max_retries
        for attempt in range(max_retries + 1):
            if attempt > 0:
                state.status = AgentStatus.RETRYING
                state.retry_count = attempt
                delay = 1000 * (2 ** (attempt - 1))
                await asyncio.sleep(delay / 1000)
            try:
                if self._exec_fn is not None:
                    result = await self._exec_fn(definition, task, context)
                else:
                    result = self._simulate(definition, task, context)
                state.output = result.get("output", "")
                state.token_usage = result.get("tokens", 0)
                state.status = AgentStatus.COMPLETED
                state.completed_at = time.time()
                state.error = None
                self._states[definition.name] = state
                return state
            except Exception as exc:
                state.error = str(exc)
                if attempt >= max_retries:
                    state.status = AgentStatus.FAILED
                    state.completed_at = time.time()
                    self._states[definition.name] = state
                    return state
        state.status = AgentStatus.FAILED
        state.completed_at = time.time()
        self._states[definition.name] = state
        return state

    def get_state(self, agent_name: str) -> RunnerState | None:
        return self._states.get(agent_name)

    def list_states(self) -> list[RunnerState]:
        return list(self._states.values())

    def cancel(self, agent_name: str) -> bool:
        state = self._states.get(agent_name)
        if state is None or state.status not in (AgentStatus.RUNNING, AgentStatus.RETRYING):
            return False
        state.status = AgentStatus.FAILED
        state.completed_at = time.time()
        return True

    @staticmethod
    def _simulate(
        definition: AgentDefinition,
        task: str,
        context: str | None = None,
    ) -> dict:
        return {
            "output": f'[Simulated] Agent "{definition.name}" executed.\nTask: {task}\nStatus: completed',
            "tokens": 50,
        }


class RunEvaluator:
    """Evaluate agent execution results against criteria."""

    def __init__(self) -> None:
        self._criteria: dict[str, EvaluationCriteria] = {}

    def add_criterion(self, criterion: EvaluationCriteria) -> None:
        self._criteria[criterion.id] = criterion

    def add_criteria(self, criteria: list[EvaluationCriteria]) -> None:
        for c in criteria:
            self._criteria[c.id] = c

    async def evaluate(
        self,
        state: RunnerState,
        definition: AgentDefinition | None = None,
    ) -> list[EvaluationReport]:
        reports: list[EvaluationReport] = []
        for criterion in self._criteria.values():
            result = await self._check_criterion(criterion, state, definition)
            reports.append(result)
        return reports

    async def evaluate_output(
        self,
        output: str,
        expected_pattern: str | None = None,
    ) -> EvaluationReport:
        criteria = EvaluationCriteria(
            id="output_check",
            name="Output Check",
            description="Verify output is non-empty",
        )
        passed = bool(output.strip())
        if expected_pattern and passed:
            passed = expected_pattern in output
        return EvaluationReport(
            criteria_id=criteria.id,
            criteria_name=criteria.name,
            result=EvaluationResult.PASS if passed else EvaluationResult.FAIL,
            detail="Output is valid" if passed else "Output is empty or missing expected pattern",
        )

    async def _check_criterion(
        self,
        criterion: EvaluationCriteria,
        state: RunnerState,
        definition: AgentDefinition | None,
    ) -> EvaluationReport:
        if criterion.id == "status":
            ok = state.status == AgentStatus.COMPLETED
            return EvaluationReport(
                criteria_id=criterion.id,
                criteria_name=criterion.name,
                result=EvaluationResult.PASS if ok else EvaluationResult.FAIL,
                detail=f"Status: {state.status.value}",
            )
        if criterion.id == "output_nonempty":
            ok = bool(state.output and state.output.strip())
            return EvaluationReport(
                criteria_id=criterion.id,
                criteria_name=criterion.name,
                result=EvaluationResult.PASS if ok else EvaluationResult.FAIL,
                detail="Output exists" if ok else "Output is empty",
            )
        if criterion.id == "no_error":
            ok = state.error is None
            return EvaluationReport(
                criteria_id=criterion.id,
                criteria_name=criterion.name,
                result=EvaluationResult.PASS if ok else EvaluationResult.FAIL,
                detail="No errors" if ok else f"Error: {state.error}",
            )
        return EvaluationReport(
            criteria_id=criterion.id,
            criteria_name=criterion.name,
            result=EvaluationResult.PASS,
            detail="Unknown criterion — passed by default",
        )
