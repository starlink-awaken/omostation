from __future__ import annotations

"""
Priority queue for D-Harvest source scheduling.

Provides ``HarvestPriorityQueue`` and ``Priority`` enum for ordering
harvest jobs by urgency.
"""

import enum
from dataclasses import dataclass, field


class Priority(enum.IntEnum):
    """Harvest job priority levels (higher = more urgent)."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass(order=True)
class HarvestJob:
    """A single item in the harvest priority queue."""

    priority: Priority = field(compare=True)
    source_id: str = field(compare=False)


class HarvestPriorityQueue:
    """Priority queue for scheduling harvest jobs.

    Jobs are dequeued in strict priority order (URGENT first).  Within the
    same priority level, FIFO ordering is maintained.
    """

    def __init__(self) -> None:
        self._jobs: list[HarvestJob] = []

    async def enqueue(self, source_id: str, priority: Priority = Priority.NORMAL) -> None:
        """Add a job to the queue."""
        self._jobs.append(HarvestJob(priority=priority, source_id=source_id))
        self._jobs.sort(reverse=True)  # highest priority first

    async def dequeue(self) -> HarvestJob | None:
        """Remove and return the highest-priority job, or ``None`` if empty."""
        if not self._jobs:
            return None
        return self._jobs.pop(0)

    async def get_queue_status(self) -> dict[str, int]:
        """Return a count of jobs grouped by priority level."""
        counts: dict[str, int] = {}
        for job in self._jobs:
            key = job.priority.name.lower()
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def peek(self) -> HarvestJob | None:
        """Return the highest-priority job without removing it, or ``None``."""
        if not self._jobs:
            return None
        return self._jobs[0]

    @property
    def size(self) -> int:
        """Number of jobs currently in the queue."""
        return len(self._jobs)

    def clear(self) -> None:
        """Remove all jobs from the queue."""
        self._jobs.clear()
