"""Task lifecycle management for agentmesh gateway migration.

Handles task creation, assignment, execution, completion, and cancellation.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from agora.types import AgentInvoker, AgentMessage, Error, Task  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task lifecycle from creation through completion or failure."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}
        self._adapter_lookup: Callable[[str], AgentInvoker | None] | None = None

    def set_adapter_lookup(self, lookup: Callable[[str], AgentInvoker | None]) -> None:
        """Set the function to look up agent adapters by ID."""
        self._adapter_lookup = lookup

    def _now(self) -> int:
        return int(time.time() * 1000)

    def _save(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def create_task(self, request: AgentMessage) -> Task:
        """Create a new task in pending state."""
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            status="pending",
            request=request,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self._save(task)
        self._cancel_flags[task_id] = asyncio.Event()
        return task

    def assign_task(self, task_id: str, agent_ids: list[str]) -> Task | None:
        """Assign agents to a task. Returns None if task not found."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.assigned_agents = agent_ids
        task.status = "assigned"
        task.updated_at = self._now()
        self._save(task)
        return task

    def start_task(self, task_id: str) -> Task | None:
        """Mark a task as running. Returns None if task not found."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.status = "running"
        task.updated_at = self._now()
        self._save(task)
        return task

    async def complete_task(self, task_id: str, result: Any) -> Task | None:
        """Mark a task as completed with a result."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.status = "completed"
        task.result = result
        task.updated_at = self._now()
        self._save(task)
        self._cancel_flags.pop(task_id, None)
        return task

    async def fail_task(self, task_id: str, error: Error) -> Task | None:
        """Mark a task as failed with an error."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.status = "failed"
        task.error = error
        task.updated_at = self._now()
        self._save(task)
        self._cancel_flags.pop(task_id, None)
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending/running task. Returns False if not found or already terminal."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status not in ("pending", "assigned", "running"):
            return False
        cancel = self._cancel_flags.get(task_id)
        if cancel is not None:
            cancel.set()
            self._cancel_flags.pop(task_id, None)
        task.status = "failed"
        task.error = Error(code="CANCELLED", message="Task cancelled by user")
        task.updated_at = self._now()
        self._save(task)
        return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a cancellation has been requested for a task."""
        cancel = self._cancel_flags.get(task_id)
        return cancel is not None and cancel.is_set()

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks sorted by creation time (newest first)."""
        return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    def purge_completed(self, older_than_days: int = 7) -> int:
        """Remove completed/failed tasks older than the specified days."""
        cutoff = self._now() - older_than_days * 86400 * 1000
        ids = [
            tid
            for tid, t in self._tasks.items()
            if t.status in ("completed", "failed") and t.updated_at < cutoff
        ]
        for tid in ids:
            self._tasks.pop(tid, None)
            self._cancel_flags.pop(tid, None)
        return len(ids)

    async def process_task(
        self,
        message: AgentMessage,
        route_fn: Callable[[AgentMessage], tuple[list[str], str]],
    ) -> Task:
        """Route, assign, and execute a task. Returns the completed/failed task."""
        task = await self.create_task(message)
        agent_ids, strategy = route_fn(message)
        if not agent_ids:
            await self.fail_task(
                task.id, Error(code="NO_AGENT_AVAILABLE", message="No available agents")
            )
            raise RuntimeError("No available agents")
        self.assign_task(task.id, agent_ids)
        self.start_task(task.id)
        await self._execute(task, agent_ids, strategy)
        return task

    async def _execute(self, task: Task, agent_ids: list[str], strategy: str) -> None:
        if self._adapter_lookup is None:
            await self.fail_task(
                task.id,
                Error(
                    code="NO_ADAPTER_LOOKUP", message="Adapter lookup not configured"
                ),
            )
            return

        results: dict[str, Any] = {}
        request = task.request

        if strategy == "direct" and agent_ids:
            agent_id = agent_ids[0]
            invoker = self._adapter_lookup(agent_id)
            if invoker is None:
                await self.fail_task(
                    task.id,
                    Error(
                        code="AGENT_NOT_FOUND", message=f"Agent {agent_id} not found"
                    ),
                )
                return
            try:
                result = await invoker(request)
                if self.is_cancelled(task.id):
                    return
                await self.complete_task(task.id, result)
            except Exception as e:
                if self.is_cancelled(task.id):
                    return
                await self.fail_task(
                    task.id, Error(code="EXECUTION_ERROR", message=str(e))
                )
        else:

            async def _invoke_one(aid: str) -> None:
                invoker = self._adapter_lookup(aid) if self._adapter_lookup else None
                if invoker is None:
                    results[aid] = {"error": f"Agent {aid} not found"}
                    return
                try:
                    results[aid] = await invoker(request)
                except Exception as e:
                    results[aid] = {"error": str(e)}

            await asyncio.gather(*[_invoke_one(aid) for aid in agent_ids])
            if not self.is_cancelled(task.id):
                await self.complete_task(task.id, results)


task_manager = TaskManager()
