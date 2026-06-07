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
# Cost Aware Dispatcher ≡ Module
# 内涵 ≝ {Cost, Aware, Dispatcher}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CostAwareDispatcher)}
# 功能 ⊢ {Cost_Aware, Aware_Dispatcher, Dispatcher_Init}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .organs.engine.task_store import TaskRecord  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


def _load_economy_controller() -> type | None:
    """Lazy-import EconomyController to avoid cross-organ direct import."""
    import importlib

    try:
        mod = importlib.import_module("organs.D_Economy.organs.economy_controller")
        return mod.EconomyController
    except (ImportError, AttributeError):
        _log.debug("[CostAwareDispatcher] EconomyController unavailable")
        return None


class CostAwareDispatcher:
    """Routes tasks to cheapest capable worker, enforcing EU budgets."""

    def __init__(self, economy: Any | None = None) -> None:
        self._economy = economy
        self._rr_index = 0

    def dispatch(self, task: TaskRecord, candidates: list[str]) -> str | None:
        """Select cheapest worker from candidates.

        Returns worker_id or None if no budget / no candidates.
        Falls back to round-robin when no EconomyController is wired.
        """
        if not candidates:
            return None

        if self._economy is None:
            # Graceful degradation: round-robin across candidates
            idx = self._rr_index % len(candidates)
            self._rr_index += 1
            return candidates[idx]

        # 1. Check role budget
        status = self._economy.get_budget_status(task.role_id)
        if status["remaining"] < task.estimated_eu:
            _log.warning(
                "[CostAwareDispatcher] Insufficient budget for role=%s (remaining=%.2f, estimated=%.2f)",
                task.role_id,
                status["remaining"],
                task.estimated_eu,
            )
            return None

        # 2. Select cheapest capable worker
        worker_id = self._economy.get_cheapest_worker(
            task.task_type,
            candidates,
        )
        if worker_id is None:
            _log.warning(
                "[CostAwareDispatcher] No eligible worker for task_type=%s",
                task.task_type,
            )
            return None

        # [RFC-038] Worker-level EU pre-flight check
        # Ensures the selected physical worker has sufficient fuel to start.
        balance_getter = getattr(self._economy, "get_worker_balance", None)
        if callable(balance_getter):
            worker_balance = balance_getter(worker_id)
            if isinstance(worker_balance, int | float) and worker_balance < task.estimated_eu:
                _log.warning(
                    "[CostAwareDispatcher] Selected worker %s is STARVED "
                    "(balance=%.2f, required=%.2f). Rejecting dispatch.",
                    worker_id,
                    worker_balance,
                    task.estimated_eu,
                )
                return None

        # 3. Charge EU
        charged = self._economy.charge_task(
            task.role_id,
            task.task_id,
            task.estimated_eu,
        )
        if not charged:
            _log.warning(
                "[CostAwareDispatcher] charge_task failed for role=%s task=%s",
                task.role_id,
                task.task_id,
            )
            return None

        _log.info(
            "[CostAwareDispatcher] Dispatched task=%s → worker=%s (%.2f EU)",
            task.task_id,
            worker_id,
            task.estimated_eu,
        )
        return worker_id

    def report_outcome(
        self,
        task: TaskRecord,
        worker_id: str,
        success: bool,
        actual_eu: float,
    ) -> None:
        """Report task completion for reputation update."""
        if self._economy is None:
            return
        self._economy.record_task_outcome(worker_id, success, actual_eu)
        _log.info(
            "[CostAwareDispatcher] Outcome task=%s worker=%s success=%s eu=%.2f",
            task.task_id,
            worker_id,
            success,
            actual_eu,
        )
