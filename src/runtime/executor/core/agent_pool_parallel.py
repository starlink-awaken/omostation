"""Parallel agent pool — TaskScheduler for dependency-aware scheduling.

Migrated from agentmesh agent-pool-parallel.ts (TaskScheduler).

Provides the core scheduling infrastructure. The ResultAggregator and
parallel_run entry point live in ``result_aggregation.py``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any


class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    DEFERRED = 4


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_name: str = ""
    agent_definition: Any = None
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)


class TaskScheduler:
    """Dependency-aware multi-level priority scheduler."""

    def __init__(self) -> None:
        self._queues: dict[TaskPriority, list[ScheduledTask]] = {
            p: [] for p in TaskPriority
        }
        self._running: dict[str, ScheduledTask] = {}
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._dep_edges: dict[str, set[str]] = {}
        self._nodes: dict[str, ScheduledTask] = {}

    def validate_and_enqueue(self, tasks: list[ScheduledTask]) -> None:
        self._nodes = {t.task_id: t for t in tasks}
        self._dep_edges = {}
        for t in tasks:
            self._dep_edges[t.task_id] = set(t.dependencies)
        if self._has_cycle():
            raise ValueError("Circular dependency detected")
        for t in tasks:
            if not t.dependencies:
                t.status = TaskStatus.READY
                self._queues[t.priority].append(t)

    def _has_cycle(self) -> bool:
        visited: set[str] = set()
        stack: set[str] = set()
        def dfs(nid: str) -> bool:
            if nid in stack:
                return True
            if nid in visited:
                return False
            visited.add(nid)
            stack.add(nid)
            for dep in self._dep_edges.get(nid, set()):
                if dep in self._nodes and dfs(dep):
                    return True
            stack.discard(nid)
            return False
        return any(dfs(nid) for nid in self._nodes)

    def get_next_batch(self, max_count: int) -> list[ScheduledTask]:
        batch: list[ScheduledTask] = []
        remaining = max_count - len(self._running)
        if remaining <= 0:
            return batch
        for priority in TaskPriority:
            queue = self._queues[priority]
            still_pending: list[ScheduledTask] = []
            while batch.__len__() < remaining and queue:
                task = queue.pop(0)
                if self._deps_satisfied(task):
                    task.status = TaskStatus.RUNNING
                    self._running[task.task_id] = task
                    batch.append(task)
                else:
                    still_pending.append(task)
            queue.extend(still_pending)
            if batch.__len__() >= remaining:
                break
        return batch

    def mark_complete(self, task_id: str) -> None:
        self._running.pop(task_id, None)
        self._completed.add(task_id)
        for nid in self._nodes:
            if nid not in self._completed and nid not in self._running and nid not in self._failed:
                node = self._nodes[nid]
                if self._deps_satisfied(node) and node.status != TaskStatus.READY:
                    node.status = TaskStatus.READY
                    self._queues[node.priority].append(node)

    def mark_failed(self, task_id: str) -> None:
        self._running.pop(task_id, None)
        self._failed.add(task_id)

    def _deps_satisfied(self, task: ScheduledTask) -> bool:
        return all(d in self._completed for d in task.dependencies)

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def is_done(self) -> bool:
        return len(self._completed) + len(self._failed) == len(self._nodes)

    def queue_status(self) -> dict:
        pending = sum(len(q) for q in self._queues.values())
        return {
            "total": len(self._nodes),
            "pending": pending,
            "running": len(self._running),
            "completed": len(self._completed),
            "failed": len(self._failed),
        }
