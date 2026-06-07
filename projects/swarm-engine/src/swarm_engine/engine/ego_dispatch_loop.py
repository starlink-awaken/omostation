# ---
# domain: D-Execution
# layer: organ
# status: active
# ---
"""Dispatcher loop wiring EgoEngine → EgoTaskBridge → ExecutionScheduler."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # All collaborators injected at runtime; no cross-organ imports needed.

logger = logging.getLogger(__name__)


class EgoDispatchLoop:
    """Autonomous dispatch loop: EgoEngine tasks → budget validation → scheduler.

    Runs as a periodic ``tick()`` that:
    1. Calls ``EgoEngine.heartbeat()`` to sense new tasks.
    2. Filters / deduplicates against already-submitted tasks.
    3. Validates budget via ``EgoTaskBridge.propose_task()``.
    4. Converts ``AutonomousTask`` → ``ExecutionScheduler.submit_task()`` format.
    5. Tracks dispatch results for feedback to ``EgoEngine``.
    """

    def __init__(
        self,
        ego_engine: Any,
        task_bridge: Any,
        scheduler: Any,
        *,
        max_concurrent: int = 5,
    ) -> None:
        self._ego = ego_engine
        self._bridge = task_bridge
        self._scheduler = scheduler
        self._max_concurrent = max_concurrent
        self._dispatched: dict[str, str] = {}  # ego_task_id → scheduler_task_id
        self._feedback_log: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tick(self) -> list[dict[str, Any]]:
        """Execute one dispatch cycle.

        Returns a list of per-task result dicts with keys:
        ``ego_task_id``, ``scheduler_task_id | None``, ``status``, ``error | None``.
        """
        tasks = self._ego.heartbeat()
        if not tasks:
            return []

        with self._lock:
            active_count = sum(1 for v in self._dispatched.values() if v)
            available_slots = max(0, self._max_concurrent - active_count)

        # Sort highest-priority first (higher float = more urgent).
        tasks_sorted = sorted(tasks, key=lambda t: t.priority, reverse=True)

        results: list[dict[str, Any]] = []
        for task in tasks_sorted:
            if available_slots <= 0:
                break
            if task.task_id in self._dispatched:
                continue
            result = self._dispatch_one(task)
            results.append(result)
            if result["status"] == "dispatched":
                available_slots -= 1
        return results

    def get_dispatch_status(self) -> dict[str, Any]:
        """Return aggregate stats about dispatched tasks."""
        with self._lock:
            active = sum(1 for v in self._dispatched.values() if v)
            return {
                "total_dispatched": len(self._dispatched),
                "active": active,
                "max_concurrent": self._max_concurrent,
                "available_slots": max(0, self._max_concurrent - active),
                "feedback_count": len(self._feedback_log),
            }

    def feedback(self, ego_task_id: str, success: bool, output: str = "") -> None:
        """Feed execution result back to EgoEngine for learning."""
        with self._lock:
            self._feedback_log.append(
                {"ego_task_id": ego_task_id, "success": success, "output": output},
            )
            # Clear active mapping so the slot is freed.
            if ego_task_id in self._dispatched:
                self._dispatched[ego_task_id] = ""

        try:
            self._ego.reward(ego_task_id, success)
        except (RuntimeError, ValueError, AttributeError):
            logger.warning("EgoEngine.reward() failed for %s", ego_task_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch_one(self, task: Any) -> dict[str, Any]:
        """Convert and dispatch a single ``AutonomousTask``."""
        ego_task_id: str = task.task_id

        # 1. Propose to bridge (budget / queue check).
        try:
            bridge_task = self._bridge.propose_task(
                interest=task.source,
                description=f"{task.task_type}: {task.description}",
                priority=int(task.priority),
                estimated_cost=task.metadata.get("estimated_cost", 1.0),
            )
        except ValueError as exc:
            logger.info("Budget rejected ego task %s: %s", ego_task_id, exc)
            return {
                "ego_task_id": ego_task_id,
                "scheduler_task_id": None,
                "status": "budget_rejected",
                "error": str(exc),
            }

        # 2. Submit proposed task through bridge.
        bridge_task_id: str = bridge_task.task_id
        if not self._bridge.submit_task(bridge_task_id):
            return {
                "ego_task_id": ego_task_id,
                "scheduler_task_id": None,
                "status": "bridge_submit_failed",
                "error": "EgoTaskBridge.submit_task returned False",
            }

        # 3. Submit to execution scheduler.
        agent_id = f"ego-{task.source}"
        command = f"{task.task_type}: {task.description}"
        context: dict[str, Any] = {
            "ego_task_id": ego_task_id,
            "source": task.source,
            **task.metadata,
        }
        sched_priority = self._map_priority(task.priority)

        try:
            scheduler_task_id = self._scheduler.submit_task(
                agent_id=agent_id,
                command=command,
                context=context,
                priority=sched_priority,
            )
        except Exception as exc:
            logger.error("Scheduler rejected ego task %s: %s", ego_task_id, exc)
            return {
                "ego_task_id": ego_task_id,
                "scheduler_task_id": None,
                "status": "scheduler_error",
                "error": str(exc),
            }

        # 4. Track mapping.
        with self._lock:
            self._dispatched[ego_task_id] = scheduler_task_id

        logger.info(
            "Dispatched ego task %s → scheduler %s (priority=%d)",
            ego_task_id,
            scheduler_task_id,
            sched_priority,
        )
        return {
            "ego_task_id": ego_task_id,
            "scheduler_task_id": scheduler_task_id,
            "status": "dispatched",
            "error": None,
        }

    @staticmethod
    def _map_priority(ego_priority: float) -> int:
        """Map EgoEngine priority (0-10, higher=urgent) to TaskPriority int (lower=urgent)."""
        if ego_priority >= 8:
            return 1  # HIGH
        if ego_priority >= 5:
            return 2  # NORMAL
        if ego_priority >= 3:
            return 3  # LOW
        return 4  # IDLE
