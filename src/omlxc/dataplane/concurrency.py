"""
In-Flight Concurrency Tracker and Load-Shedding Coordinator for omlxc.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class ConcurrencyTracker:
    """
    Thread-safe and async-safe in-flight request tracker for placements.
    """

    def __init__(self, default_max_concurrency: int = 4) -> None:
        self._default_max_concurrency = default_max_concurrency
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def get_in_flight(self, placement_id: str) -> int:
        """Get current in-flight request count for placement."""
        with self._lock:
            return self._counts.get(placement_id, 0)

    def acquire(self, placement_id: str) -> int:
        """Increment in-flight count and return new count."""
        with self._lock:
            count = self._counts.get(placement_id, 0) + 1
            self._counts[placement_id] = count
            return count

    def release(self, placement_id: str) -> int:
        """Decrement in-flight count (floor 0) and return new count."""
        with self._lock:
            count = max(self._counts.get(placement_id, 1) - 1, 0)
            if count == 0:
                self._counts.pop(placement_id, None)
            else:
                self._counts[placement_id] = count
            return count

    @asynccontextmanager
    async def track(self, placement_id: str) -> AsyncGenerator[int]:
        """Async context manager to safely acquire and release concurrency token."""
        count = self.acquire(placement_id)
        try:
            yield count
        finally:
            self.release(placement_id)

    def is_overloaded(self, placement_id: str, max_concurrent: int | None = None) -> bool:
        """Check if placement has exceeded concurrency limit."""
        limit = max_concurrent if max_concurrent is not None else self._default_max_concurrency
        return self.get_in_flight(placement_id) >= limit

    def clear(self) -> None:
        """Reset all in-flight counters."""
        with self._lock:
            self._counts.clear()
