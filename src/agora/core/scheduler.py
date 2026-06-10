"""Simple in-memory scheduler for agentmesh gateway migration."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A task scheduled for future execution."""

    id: str
    callback: Callable[[], Any] | None = None
    interval: float = 0.0
    cron_expr: str | None = None
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_run: float = 0.0
    next_run: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class Scheduler:
    """Simple in-memory scheduler with periodic task support."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._worker: asyncio.Task[None] | None = None

    def add_task(self, task: ScheduledTask) -> None:
        """Register a scheduled task."""
        self._tasks[task.id] = task
        logger.info("Scheduled task added: %s", task.id)

    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task by ID."""
        return self._tasks.pop(task_id, None) is not None

    def get_task(self, task_id: str) -> ScheduledTask | None:
        """Get a scheduled task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[ScheduledTask]:
        """List all scheduled tasks."""
        return list(self._tasks.values())

    def start(self) -> None:
        """Start the scheduler worker loop."""
        if self._running:
            return
        self._running = True
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler worker loop."""
        self._running = False
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None
        logger.info("Scheduler stopped")

    @property
    def task_count(self) -> int:
        return len(self._tasks)


scheduler = Scheduler()
