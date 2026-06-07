"""Worker binding strategies for D_Execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BindingStrategy(ABC):
    """Abstract base for worker binding strategies.

    Each strategy implements a different policy for selecting a worker from
    the available pool for a given task.
    """

    @abstractmethod
    def select_worker(
        self,
        task: dict[str, Any],
        available_workers: list[Any],
    ) -> Any | None:
        """Select the best worker for *task* from *available_workers*."""
        ...


class HybridBinding(BindingStrategy):
    """Hybrid binding: prefer long-term bound workers, fall back to
    on-demand selection.

    Scores each available worker by combining trust score and current load.
    """

    def __init__(self, long_term_weight: float = 0.7) -> None:
        self.long_term_weight = long_term_weight

    def select_worker(
        self,
        task: dict[str, Any],
        available_workers: list[Any],
    ) -> Any | None:
        if not available_workers:
            return None
        scored = [(w, self._score_worker(w, task)) for w in available_workers]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored else None

    @staticmethod
    def _score_worker(worker: Any, _task: dict[str, Any]) -> float:
        base = getattr(worker, "trust_score", 50)
        metrics = getattr(worker, "metrics", None)
        load = 1.0 - (metrics.load_factor if metrics else 0.0)
        return float(base) * load


class LongTermBinding(BindingStrategy):
    """Long-term binding: a dedicated worker is bound indefinitely.

    The bound worker is identified by ``worker_id`` (set at construction
    time or read from the task payload as ``affinity_worker_id``).
    """

    def __init__(self, worker_id: str | None = None) -> None:
        self.bound_worker_id = worker_id

    def select_worker(
        self,
        task: dict[str, Any],
        available_workers: list[Any],
    ) -> Any | None:
        worker_id = self.bound_worker_id or task.get("affinity_worker_id")
        if worker_id is None:
            return available_workers[0] if available_workers else None
        for w in available_workers:
            if getattr(w, "worker_id", None) == worker_id:
                return w
        return None


class OnDemandBinding(BindingStrategy):
    """On-demand binding: select the least-loaded available worker.

    When ``prefer_idle`` is true (the default) the strategy filters the
    pool to idle workers first.
    """

    def __init__(self, prefer_idle: bool = True) -> None:
        self.prefer_idle = prefer_idle

    def select_worker(
        self,
        task: dict[str, Any],
        available_workers: list[Any],
    ) -> Any | None:
        if not available_workers:
            return None

        candidates = list(available_workers)

        if self.prefer_idle:
            idle = [w for w in candidates if hasattr(w, "status") and str(w.status).lower() == "workerstatus.idle"]
            if idle:
                candidates = idle

        candidates.sort(key=lambda w: getattr(getattr(w, "metrics", None), "load_factor", 0))
        return candidates[0]
