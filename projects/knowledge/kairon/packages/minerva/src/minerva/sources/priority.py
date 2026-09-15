from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Priority ≡ Module
# 内涵 ≝ {Priority}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Priority)}
# 功能 ⊢ {Init_Priority, Execute_Priority, Validate_Priority}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Priority queue for urgent harvests

Implements priority-based queue system for managing harvest jobs.
Urgent harvests bypass rate limiting and are processed before normal jobs.
"""
import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

_log = logging.getLogger(__name__)


class Priority(IntEnum):
    """Harvest priority levels"""

    URGENT = 0  # Critical: bypass rate limits
    HIGH = 1  # Important: process before normal
    NORMAL = 2  # Standard: respect rate limits
    LOW = 3  # Background: process when idle


@dataclass(order=True)
class PriorityJob:
    """Harvest job with priority"""

    priority: Priority
    timestamp: float  # For FIFO within same priority
    source_id: str
    data: dict[str, Any] = field(compare=False)

    def __init__(self, priority: Priority, source_id: str, data: dict[str, Any]) -> None:
        self.priority = priority
        self.timestamp = datetime.now(UTC).timestamp()
        self.source_id = source_id
        self.data = data


class HarvestPriorityQueue:
    """
    Priority-based harvest queue

    Urgent harvests bypass rate limiting and get processed first.
    High priority jobs are processed before normal jobs.
    """

    def __init__(self, max_size: int = 10000) -> None:
        """
        Initialize priority queue

        Args:
            max_size: Maximum queue size (default: 10000)
        """
        self._queue: list[PriorityJob] = []
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._processing: dict[str, PriorityJob] = {}

    async def enqueue(
        self,
        source_id: str,
        priority: Priority = Priority.NORMAL,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add harvest job to queue

        Args:
            source_id: Source identifier
            priority: Job priority level
            data: Additional job metadata

        Returns:
            True if job enqueued successfully, False if queue full
        """
        async with self._lock:
            if len(self._queue) >= self._max_size:
                _log.warning(f"Queue full, cannot enqueue job for {source_id}")
                return False

            # Check if already queued or processing
            if source_id in self._processing:
                _log.warning(f"Job for {source_id} already in queue/processing")
                return False

            job = PriorityJob(priority, source_id, data or {})

            heapq.heappush(self._queue, job)
            self._processing[source_id] = job

            _log.info(f"Enqueued {source_id} with priority {priority.name}")
            return True

    async def dequeue(self) -> PriorityJob | None:
        """
        Get next job from queue (highest priority first)

        Returns:
            PriorityJob if available, None otherwise
        """
        async with self._lock:
            if not self._queue:
                return None

            job = heapq.heappop(self._queue)

            # Remove from processing map
            if job.source_id in self._processing:
                del self._processing[job.source_id]

            _log.info(f"Dequeued {job.source_id} with priority {job.priority.name}")
            return job

    async def peek(self) -> PriorityJob | None:
        """
        Peek at next job without removing it

        Returns:
            Next PriorityJob if available, None otherwise
        """
        async with self._lock:
            if not self._queue:
                return None

            return self._queue[0]

    async def remove(self, source_id: str) -> bool:
        """
        Remove job from queue

        Args:
            source_id: Source identifier

        Returns:
            True if job was found and removed
        """
        async with self._lock:
            if source_id not in self._processing:
                return False

            # Remove from processing map
            del self._processing[source_id]

            # Remove from heap (rebuild heap without this job)
            self._queue = [job for job in self._queue if job.source_id != source_id]
            heapq.heapify(self._queue)

            _log.info(f"Removed job for {source_id} from queue")
            return True

    async def is_queued(self, source_id: str) -> bool:
        """
        Check if source has pending job

        Args:
            source_id: Source identifier

        Returns:
            True if source is in queue
        """
        return source_id in self._processing

    async def get_queue_size(self) -> dict[Priority, int]:
        """
        Get queue size by priority level

        Returns:
            Dictionary mapping priority to count
        """
        async with self._lock:
            counts = dict.fromkeys(Priority, 0)

            for job in self._queue:
                counts[job.priority] += 1

            return counts

    async def clear(self) -> int:
        """
        Clear all jobs from queue

        Returns:
            Number of jobs cleared
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            self._processing.clear()

            _log.info(f"Cleared {count} jobs from queue")
            return count

    def get_urgent_jobs(self) -> list[PriorityJob]:
        """
        Get all urgent jobs (for bypassing rate limits)

        Returns:
            List of urgent jobs
        """
        return [job for job in self._queue if job.priority == Priority.URGENT]

    async def get_queue_status(self) -> dict[str, int]:
        """
        Get queue status as string-keyed dictionary for testing

        Returns:
            Dictionary with string keys (urgent, high, normal, low)
        """
        size_dict = await self.get_queue_size()
        return {
            "urgent": size_dict[Priority.URGENT],
            "high": size_dict[Priority.HIGH],
            "normal": size_dict[Priority.NORMAL],
            "low": size_dict[Priority.LOW],
        }
