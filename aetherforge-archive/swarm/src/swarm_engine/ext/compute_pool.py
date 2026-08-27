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
# Compute Pool ≡ Module
# 内涵 ≝ {Compute, Pool}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ComputePool)}
# 功能 ⊢ {Compute_Pool, Init_Compute, Validate_Pool}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import threading
import time
from dataclasses import dataclass, field
from enum import Enum


class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    SCALING_UP = "scaling_up"
    DRAINING = "draining"
    TERMINATED = "terminated"


@dataclass
class PoolWorker:
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    capacity: float = 1.0
    current_load: float = 0.0
    tasks_completed: int = 0
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


@dataclass
class ScalingDecision:
    action: str  # "scale_up", "scale_down", "none"
    current_workers: int = 0
    target_workers: int = 0
    reason: str = ""


class ComputePool:
    """Dynamic compute pool with auto-scaling based on demand."""

    def __init__(
        self,
        min_workers: int = 1,
        max_workers: int = 10,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.2,
        idle_timeout: float = 60.0,
    ) -> None:
        self._min_workers = min_workers
        self._max_workers = max_workers
        self._scale_up_threshold = scale_up_threshold
        self._scale_down_threshold = scale_down_threshold
        self._idle_timeout = idle_timeout
        self._workers: dict[str, PoolWorker] = {}
        self._worker_counter = 0
        self._lock = threading.Lock()
        self._scaling_history: list[ScalingDecision] = []
        # Initialize with min workers
        for _ in range(min_workers):
            self._add_worker_locked()

    def _add_worker_locked(self) -> PoolWorker:
        self._worker_counter += 1
        wid = f"worker-{self._worker_counter}"
        w = PoolWorker(worker_id=wid)
        self._workers[wid] = w
        return w

    def add_worker(self) -> PoolWorker | None:
        with self._lock:
            active = self._active_count_locked()
            if active >= self._max_workers:
                return None
            return self._add_worker_locked()

    def remove_worker(self, worker_id: str) -> bool:
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None or w.status == WorkerStatus.TERMINATED:
                return False
            active = self._active_count_locked()
            if active <= self._min_workers:
                return False
            w.status = WorkerStatus.TERMINATED
            return True

    def assign_task(self, worker_id: str, load: float = 1.0) -> bool:
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None or w.status not in (WorkerStatus.IDLE, WorkerStatus.BUSY):
                return False
            if w.current_load + load > w.capacity:
                return False
            w.current_load += load
            w.status = WorkerStatus.BUSY
            w.last_active = time.time()
            return True

    def release_task(self, worker_id: str, load: float = 1.0) -> bool:
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None:
                return False
            w.current_load = max(0, w.current_load - load)
            w.tasks_completed += 1
            if w.current_load == 0:
                w.status = WorkerStatus.IDLE
            w.last_active = time.time()
            return True

    def get_idle_worker(self) -> str | None:
        with self._lock:
            for w in self._workers.values():
                if w.status == WorkerStatus.IDLE:
                    return w.worker_id
            return None

    def evaluate_scaling(self) -> ScalingDecision:
        with self._lock:
            active = self._active_count_locked()
            if active == 0:
                return ScalingDecision(
                    action="scale_up",
                    current_workers=0,
                    target_workers=1,
                    reason="No active workers",
                )
            total_load = sum(w.current_load for w in self._workers.values() if w.status != WorkerStatus.TERMINATED)
            total_capacity = sum(w.capacity for w in self._workers.values() if w.status != WorkerStatus.TERMINATED)
            utilization = total_load / total_capacity if total_capacity > 0 else 0

            if utilization > self._scale_up_threshold and active < self._max_workers:
                decision = ScalingDecision(
                    action="scale_up",
                    current_workers=active,
                    target_workers=min(active + 1, self._max_workers),
                    reason=f"Utilization {utilization:.0%} > {self._scale_up_threshold:.0%}",
                )
            elif utilization < self._scale_down_threshold and active > self._min_workers:
                decision = ScalingDecision(
                    action="scale_down",
                    current_workers=active,
                    target_workers=max(active - 1, self._min_workers),
                    reason=f"Utilization {utilization:.0%} < {self._scale_down_threshold:.0%}",
                )
            else:
                decision = ScalingDecision(
                    action="none",
                    current_workers=active,
                    target_workers=active,
                    reason="Within thresholds",
                )
            self._scaling_history.append(decision)
            return decision

    def auto_scale(self) -> ScalingDecision:
        decision = self.evaluate_scaling()
        if decision.action == "scale_up":
            self.add_worker()
        elif decision.action == "scale_down":
            idle = self._find_idle_worker_to_remove()
            if idle:
                self.remove_worker(idle)
        return decision

    def _find_idle_worker_to_remove(self) -> str | None:
        with self._lock:
            idle_workers = [w for w in self._workers.values() if w.status == WorkerStatus.IDLE]
            if not idle_workers:
                return None
            return min(idle_workers, key=lambda w: w.last_active).worker_id

    def _active_count_locked(self) -> int:
        return sum(1 for w in self._workers.values() if w.status != WorkerStatus.TERMINATED)

    def get_stats(self) -> dict:
        with self._lock:
            active = [w for w in self._workers.values() if w.status != WorkerStatus.TERMINATED]
            return {
                "total_workers": len(active),
                "idle": sum(1 for w in active if w.status == WorkerStatus.IDLE),
                "busy": sum(1 for w in active if w.status == WorkerStatus.BUSY),
                "total_completed": sum(w.tasks_completed for w in active),
                "utilization": sum(w.current_load for w in active) / max(sum(w.capacity for w in active), 0.001),
            }

    def get_scaling_history(self, limit: int = 20) -> list[ScalingDecision]:
        with self._lock:
            return list(self._scaling_history[-limit:])
