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
# Slo Scheduler ≡ Module
# 内涵 ≝ {Slo, Scheduler}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SloScheduler)}
# 功能 ⊢ {Slo_Scheduler, Init_Slo, Validate_Scheduler}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class TaskSLO:
    """Service-level objective for a task."""

    task_id: str
    deadline_ms: int
    priority: int
    preemptible: bool = False


@dataclass
class ScheduleResult:
    """Result of scheduling a task."""

    task_id: str
    assigned_at: float
    estimated_completion: float
    slo_met: bool


class SLOScheduler:
    """Scheduler that respects service-level objectives (deadline + priority).

    Tasks are scheduled by earliest deadline first, with priority as tiebreaker.
    Tracks actual completion times against SLO deadlines for metrics.
    """

    def __init__(self) -> None:
        self.status = "active"
        self._pending: dict[str, TaskSLO] = {}
        self._running: dict[str, tuple[TaskSLO, float]] = {}  # task_id -> (slo, start_time)
        self._completed: list[dict[str, Any]] = []
        self._base_processing_ms: float = 50.0  # simulated base processing time

    def submit(self, task_id: str, slo: TaskSLO) -> None:
        """Submit a task with its SLO constraints."""
        self._pending[task_id] = slo

    def schedule(self) -> list[ScheduleResult]:
        """Schedule all pending tasks ordered by deadline (ascending), then priority (descending)."""
        now = time.monotonic() * 1000
        sorted_tasks = sorted(
            self._pending.values(),
            key=lambda s: (s.deadline_ms, -s.priority),
        )
        results: list[ScheduleResult] = []
        cumulative_ms = 0.0
        for slo in sorted_tasks:
            assigned_at = now + cumulative_ms
            estimated_completion = assigned_at + self._base_processing_ms
            slo_met = estimated_completion <= (now + slo.deadline_ms)
            result = ScheduleResult(
                task_id=slo.task_id,
                assigned_at=assigned_at,
                estimated_completion=estimated_completion,
                slo_met=slo_met,
            )
            results.append(result)
            self._running[slo.task_id] = (slo, assigned_at)
            cumulative_ms += self._base_processing_ms

        self._pending.clear()
        return results

    def get_at_risk(self) -> list[str]:
        """Return task IDs of running tasks likely to miss their SLO."""
        now = time.monotonic() * 1000
        at_risk = []
        for task_id, (slo, start_time) in self._running.items():
            deadline_absolute = start_time + slo.deadline_ms
            if now + self._base_processing_ms > deadline_absolute:
                at_risk.append(task_id)
        return at_risk

    def preempt(self, task_id: str) -> bool:
        """Preempt a running task if it is marked preemptible."""
        if task_id not in self._running:
            return False
        slo, _ = self._running[task_id]
        if not slo.preemptible:
            return False
        del self._running[task_id]
        self._pending[task_id] = slo
        return True

    def complete(self, task_id: str) -> None:
        """Mark a task as complete and record metrics."""
        if task_id not in self._running:
            raise KeyError(f"Task '{task_id}' is not running")
        slo, start_time = self._running.pop(task_id)
        now = time.monotonic() * 1000
        actual_ms = now - start_time
        self._completed.append(
            {
                "task_id": task_id,
                "slo_deadline_ms": slo.deadline_ms,
                "actual_ms": actual_ms,
                "slo_met": actual_ms <= slo.deadline_ms,
                "priority": slo.priority,
            }
        )

    def get_metrics(self) -> dict:
        """Return SLO performance metrics."""
        if not self._completed:
            return {
                "total_completed": 0,
                "slo_hit_rate": 0.0,
                "avg_latency_ms": 0.0,
                "pending_count": len(self._pending),
                "running_count": len(self._running),
            }
        hits = sum(1 for c in self._completed if c["slo_met"])
        avg_latency = sum(c["actual_ms"] for c in self._completed) / len(self._completed)
        return {
            "total_completed": len(self._completed),
            "slo_hit_rate": hits / len(self._completed),
            "avg_latency_ms": avg_latency,
            "pending_count": len(self._pending),
            "running_count": len(self._running),
        }
