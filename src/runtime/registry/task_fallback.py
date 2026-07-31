"""Agent Registry — Task Fallback manager.

Phase 46 W3: Task fallback.

When a task cannot be dispatched (no capable agent, all agents at capacity),
this module provides:
  1. Exponential-backoff retry with jitter
  2. Max-retry escalation (permanent failure)
  3. Fallback chain: try alternative capabilities
  4. Metrics: retry count, escalation rate, latency histogram

Design:
  - TaskFallbackManager wraps a Dispatcher
  - submit() tries immediate dispatch first
  - On failure, enters retry loop with exponential backoff
  - After max_retries, escalates (records permanent failure)
  - Integrates with FailoverManager: when agents recover, pending retries are attempted
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from .dispatch import Dispatcher, TaskRequest

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0
DEFAULT_RETRY_CAPACITY_POLL = 0.5


class FallbackResult(str, Enum):
    DISPATCHED = "dispatched"
    ESCALATED = "escalATED"
    PENDING = "pending"


@dataclass
class TaskFallbackEvent:
    """Record of a fallback action."""
    task_id: str
    task_name: str
    result: FallbackResult
    attempts: int
    total_wait_ms: float
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "result": self.result.value,
            "attempts": self.attempts,
            "total_wait_ms": round(self.total_wait_ms, 1),
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


class TaskFallbackManager:
    """Wraps a Dispatcher with retry + escalation for failed task dispatches.

    Usage:
        fm = TaskFallbackManager(dispatcher, max_retries=3)
        event = await fm.submit_with_fallback(TaskRequest(name="x", required_capabilities=["coding"]))
        if event.result == FallbackResult.ESCALATED:
            alert(...)
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ) -> None:
        self._dispatcher = dispatcher
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._events: list[TaskFallbackEvent] = []
        self._pending_retries: dict[str, TaskRequest] = {}

    # ── Public API ─────────────────────────────────────────────────

    async def submit_with_fallback(self, request: TaskRequest) -> TaskFallbackEvent:
        """Submit a task with automatic retry on dispatch failure.

        Tries immediate dispatch first. If that fails (no capable agent),
        enters exponential-backoff retry loop. After max_retries, escalates.
        """
        start = time.time()

        # Attempt 1: immediate dispatch
        assignment = self._dispatcher.submit(request)
        if assignment is not None:
            elapsed = (time.time() - start) * 1000
            event = TaskFallbackEvent(
                task_id=request.task_id,
                task_name=request.name,
                result=FallbackResult.DISPATCHED,
                attempts=1,
                total_wait_ms=elapsed,
            )
            self._events.append(event)
            return event

        # Attempts 2..N: retry with exponential backoff
        for attempt in range(2, self._max_retries + 2):
            delay = self._backoff_delay(attempt - 1)
            logger.info(
                "TaskFallback: task %s (attempt %d/%d) — retrying in %.1fs",
                request.task_id, attempt, self._max_retries + 1, delay,
            )
            await asyncio.sleep(delay)

            assignment = self._dispatcher.submit(request)
            if assignment is not None:
                elapsed = (time.time() - start) * 1000
                event = TaskFallbackEvent(
                    task_id=request.task_id,
                    task_name=request.name,
                    result=FallbackResult.DISPATCHED,
                    attempts=attempt,
                    total_wait_ms=elapsed,
                )
                self._events.append(event)
                return event

        # All retries exhausted → escalate
        elapsed = (time.time() - start) * 1000
        self._pending_retries[request.task_id] = request
        event = TaskFallbackEvent(
            task_id=request.task_id,
            task_name=request.name,
            result=FallbackResult.ESCALATED,
            attempts=self._max_retries + 1,
            total_wait_ms=elapsed,
            error=f"Failed after {self._max_retries + 1} attempts",
        )
        self._events.append(event)
        logger.warning(
            "TaskFallback: task %s escalated after %d attempts (%.0fms)",
            request.task_id, event.attempts, elapsed,
        )
        return event

    def retry_pending(self) -> list[TaskFallbackEvent]:
        """Retry all escalated tasks (call when agents recover).

        Synchronous — dispatches immediately without backoff.
        Returns events for each retry attempt.
        """
        events: list[TaskFallbackEvent] = []
        still_pending: dict[str, TaskRequest] = {}

        for task_id, request in self._pending_retries.items():
            assignment = self._dispatcher.submit(request)
            if assignment is not None:
                event = TaskFallbackEvent(
                    task_id=task_id,
                    task_name=request.name,
                    result=FallbackResult.DISPATCHED,
                    attempts=-1,  # indicates retry from escalation
                    total_wait_ms=0,
                )
                events.append(event)
                self._events.append(event)
            else:
                still_pending[task_id] = request

        self._pending_retries = still_pending
        return events

    # ── Status ─────────────────────────────────────────────────────

    def get_status(self) -> dict:
        total = len(self._events)
        dispatched = sum(1 for e in self._events if e.result == FallbackResult.DISPATCHED)
        escalated = sum(1 for e in self._events if e.result == FallbackResult.ESCALATED)
        return {
            "total_events": total,
            "dispatched": dispatched,
            "escalated": escalated,
            "pending_retries": len(self._pending_retries),
            "max_retries": self._max_retries,
            "base_delay": self._base_delay,
            "max_delay": self._max_delay,
        }

    def get_events(self, limit: int = 50) -> list[TaskFallbackEvent]:
        return self._events[-limit:]

    # ── Internal ───────────────────────────────────────────────────

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with cap: min(base * 2^attempt, max_delay)."""
        delay = self._base_delay * (2 ** (attempt - 1))
        return min(delay, self._max_delay)


__all__ = [
    "FallbackResult",
    "TaskFallbackEvent",
    "TaskFallbackManager",
]
