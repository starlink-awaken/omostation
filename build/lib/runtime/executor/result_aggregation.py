"""Result aggregator and parallel run entry for parallel agent execution.

Migrated from agentmesh agent-pool-parallel.ts (ResultAggregator + parallelRun).

Provides multi-mode result aggregation and the top-level parallel_run
entry point.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from runtime.executor.core.agent_pool_parallel import ScheduledTask, TaskScheduler


class AggregationMode(StrEnum):
    WAIT_ALL = "wait_all"
    WAIT_QUORUM = "wait_quorum"
    WAIT_ANY = "wait_any"
    TIMEOUT_BASED = "timeout_based"


@dataclass
class PartialResult:
    task_id: str = ""
    agent_name: str = ""
    status: str = ""
    data: Any = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AggregatedResult:
    execution_id: str = ""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    results: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class AggregationConfig:
    mode: AggregationMode = AggregationMode.WAIT_ALL
    timeout_ms: float = 30_000.0
    quorum_size: int | None = None


DEFAULT_TIMEOUT_MS = 30_000.0


class ResultAggregator:
    """Multi-mode result aggregator."""

    def __init__(self, expected: int, config: AggregationConfig) -> None:
        self._expected = expected
        self._config = config
        self._results: dict[str, PartialResult] = {}
        self._errors: dict[str, str] = {}
        self._start = time.monotonic()

    def add_result(self, task_id: str, result: PartialResult) -> None:
        self._results[task_id] = result
        if result.status in ("failed", "FAILED"):
            self._errors[task_id] = str(result.data) if result.data else "unknown"

    def is_complete(self) -> bool:
        received = len(self._results)
        success = received - len(self._errors)
        if self._config.mode == AggregationMode.WAIT_ALL:
            return received >= self._expected
        elif self._config.mode == AggregationMode.WAIT_QUORUM:
            qs = self._config.quorum_size or math.ceil(self._expected * 0.5)
            return success >= qs
        elif self._config.mode == AggregationMode.WAIT_ANY:
            return received >= 1
        elif self._config.mode == AggregationMode.TIMEOUT_BASED:
            elapsed = (time.monotonic() - self._start) * 1000
            return elapsed >= self._config.timeout_ms
        return received >= self._expected

    def get_result(self) -> AggregatedResult:
        end = time.monotonic()
        vals = list(self._results.values())
        completed = sum(1 for v in vals if v.status in ("completed", "COMPLETED"))
        return AggregatedResult(
            total_tasks=self._expected,
            completed_tasks=completed,
            failed_tasks=len(self._errors),
            results={tid: r.data for tid, r in self._results.items() if r.status in ("completed", "COMPLETED")},
            duration_ms=(end - self._start) * 1000,
        )


async def parallel_run(
    tasks: list[ScheduledTask],
    execute_fn: Callable[[ScheduledTask], Any],
    max_concurrent: int = 10,
    aggregation_mode: AggregationMode = AggregationMode.WAIT_ALL,
    timeout_ms: float = DEFAULT_TIMEOUT_MS,
) -> AggregatedResult:
    """Execute tasks in parallel with dependency-aware scheduling."""
    config = AggregationConfig(mode=aggregation_mode, timeout_ms=timeout_ms)
    scheduler = TaskScheduler()
    aggregator = ResultAggregator(len(tasks), config)
    scheduler.validate_and_enqueue(tasks)
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run(task_: ScheduledTask) -> None:
        async with semaphore:
            try:
                result = await execute_fn(task_) if asyncio.iscoroutinefunction(execute_fn) else execute_fn(task_)
                pr = result if isinstance(result, PartialResult) else PartialResult(task_id=task_.task_id, agent_name=task_.agent_name, status="completed")
                aggregator.add_result(task_.task_id, pr)
                scheduler.mark_complete(task_.task_id)
            except Exception as exc:
                pr = PartialResult(task_id=task_.task_id, agent_name=task_.agent_name, status="failed", data=str(exc))
                aggregator.add_result(task_.task_id, pr)
                scheduler.mark_failed(task_.task_id)

    while not scheduler.is_done:
        batch = scheduler.get_next_batch(max_concurrent)
        if batch:
            await asyncio.gather(*(_run(t) for t in batch))
        elif scheduler.running_count == 0:
            break
        else:
            await asyncio.sleep(0.01)
        if aggregator.is_complete():
            break
    return aggregator.get_result()
