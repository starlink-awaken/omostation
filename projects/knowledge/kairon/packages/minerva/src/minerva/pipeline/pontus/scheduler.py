"""DAG Scheduler — topological sort and parallel execution of pipeline steps."""

from __future__ import annotations

import asyncio
import inspect
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from minerva.pipeline.pontus.dsl import PipelineDef, StepDef


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""

    status: str  # "success", "partial", "failed"
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class DAGScheduler:
    """Executor that runs pipeline steps respecting DAG dependencies.

    Steps with no unresolved dependencies execute in parallel.
    """

    def execute(self, pipeline: PipelineDef, context: dict[str, Any]) -> PipelineResult:
        """Run the pipeline synchronously, returning a PipelineResult.

        Args:
            pipeline: The validated PipelineDef to execute.
            context: A dict passed to each step's action handler.

        The context dict should contain action callbacks keyed by action name:
            context = {"fetch": async_fn, "transform": async_fn, ...}
        Each callback receives (step: StepDef, results_so_far: dict) and
        returns a value that will be stored under step.id in the final result.
        """
        return asyncio.run(self._execute_async(pipeline, context))

    async def execute_async(self, pipeline: PipelineDef, context: dict[str, Any]) -> PipelineResult:
        """Async version of execute."""
        return await self._execute_async(pipeline, context)

    async def _execute_async(self, pipeline: PipelineDef, context: dict[str, Any]) -> PipelineResult:
        step_map: dict[str, StepDef] = {s.id: s for s in pipeline.steps}

        # Build adjacency: dependency -> dependents
        dependents: dict[str, set[str]] = {s.id: set() for s in pipeline.steps}
        in_degree: dict[str, int] = {}
        for s in pipeline.steps:
            in_degree[s.id] = len(s.depends_on)
            for dep in s.depends_on:
                if dep in dependents:
                    dependents[dep].add(s.id)

        results: dict[str, Any] = {}
        errors: dict[str, str] = {}

        # Ready queue: steps with no pending dependencies
        ready = deque([s.id for s in pipeline.steps if in_degree[s.id] == 0])

        while ready:
            # Execute all ready steps in parallel
            batch = list(ready)
            ready.clear()

            tasks = []
            for sid in batch:
                step = step_map[sid]
                action_fn = context.get(step.action)
                if action_fn is None:
                    errors[sid] = f"No handler registered for action '{step.action}'"
                    continue
                tasks.append(self._run_step(sid, step, action_fn, results))

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for sid, outcome in zip([t for t in batch if t not in errors], batch_results):
                if isinstance(outcome, Exception):
                    errors[sid] = str(outcome)
                else:
                    val, err = outcome  # type: ignore[misc]
                    if err:
                        errors[sid] = err
                    if val is not None:
                        results[sid] = val

            # Enqueue newly unblocked steps
            for sid in batch:
                for downstream in dependents.get(sid, set()):
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        ready.append(downstream)

        # Determine overall status
        if errors and not results:
            status = "failed"
        elif errors:
            status = "partial"
        else:
            status = "success"

        return PipelineResult(status=status, results=results, errors=errors)

    async def _run_step(
        self,
        sid: str,
        step: StepDef,
        action_fn: Any,
        results: dict[str, Any],
    ) -> tuple[Any, str]:
        """Execute a single step and return (value, error_message)."""
        try:
            if inspect.iscoroutinefunction(action_fn):
                val = await action_fn(step, results)
            else:
                val = action_fn(step, results)
            return val, ""
        except Exception as exc:
            return None, str(exc)
