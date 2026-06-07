"""WorkerRegistry — thread-safe worker lifecycle management.

Tracks worker registration, heartbeat, status transitions, and provides
filtering for worker selection.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from .worker import MeshWorker, WorkerStatus

_log = logging.getLogger(__name__)

WorkerListener = Callable[[str, MeshWorker], None]

_DEFAULT_HEARTBEAT_TIMEOUT = 60.0  # seconds without heartbeat → ERROR


class WorkerRegistry:
    """Thread-safe registry of mesh workers.

    Usage::

        registry = WorkerRegistry()
        worker = MeshWorker(worker_id="w1", node_id="ollama-local")
        registry.register(worker)
        registry.heartbeat("w1")
        idle = registry.get_idle()
    """

    def __init__(self, heartbeat_timeout: float = _DEFAULT_HEARTBEAT_TIMEOUT) -> None:
        self._workers: dict[str, MeshWorker] = {}
        self._lock = threading.RLock()
        self._listeners: list[WorkerListener] = []
        self._heartbeat_timeout = heartbeat_timeout

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def register(self, worker: MeshWorker) -> bool:
        """Register a new worker or update an existing one.

        Returns ``True`` if the worker was newly added.
        """
        with self._lock:
            is_new = worker.worker_id not in self._workers
            self._workers[worker.worker_id] = worker
        self._notify("registered" if is_new else "updated", worker)
        return is_new

    def unregister(self, worker_id: str) -> bool:
        """Remove a worker from the registry.

        Returns ``True`` if the worker existed and was removed.
        """
        with self._lock:
            worker = self._workers.pop(worker_id, None)
        if worker:
            self._notify("unregistered", worker)
            return True
        return False

    def get(self, worker_id: str) -> MeshWorker | None:
        with self._lock:
            return self._workers.get(worker_id)

    def get_all(self) -> list[MeshWorker]:
        with self._lock:
            return list(self._workers.values())

    def count(self) -> int:
        with self._lock:
            return len(self._workers)

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def heartbeat(self, worker_id: str) -> bool:
        """Record a heartbeat for a worker. Returns ``True`` if found."""
        worker = self.get(worker_id)
        if worker is None:
            return False
        worker.last_heartbeat = time.time()
        if worker.status == WorkerStatus.ERROR:
            worker.status = WorkerStatus.IDLE
        return True

    def check_stale(self) -> list[str]:
        """Find workers that haven't heartbeated within the timeout.

        Marks them as ``ERROR`` and returns their IDs.
        """
        stale: list[str] = []
        now = time.time()
        for worker in self.get_all():
            if worker.status in (WorkerStatus.TERMINATED,):
                continue
            if now - worker.last_heartbeat > self._heartbeat_timeout:
                worker.status = WorkerStatus.ERROR
                stale.append(worker.worker_id)
                self._notify("stale", worker)
        return stale

    # ── Filtering ─────────────────────────────────────────────────────────────

    def filter(self, **kwargs: Any) -> list[MeshWorker]:
        with self._lock:
            results = list(self._workers.values())
            for attr, value in kwargs.items():
                results = [w for w in results if getattr(w, attr, None) == value]
            return results

    def get_idle(self) -> list[MeshWorker]:
        """Return all workers that are currently IDLE."""
        return self.filter(status=WorkerStatus.IDLE)

    def get_by_node(self, node_id: str) -> list[MeshWorker]:
        """Return all workers on a specific compute node."""
        return self.filter(node_id=node_id)

    # ── Status transitions ────────────────────────────────────────────────────

    def set_busy(self, worker_id: str, task_id: str = "") -> bool:
        worker = self.get(worker_id)
        if worker is None:
            return False
        worker.status = WorkerStatus.BUSY
        worker.current_task = task_id
        self._notify("busy", worker)
        return True

    def set_idle(self, worker_id: str) -> bool:
        worker = self.get(worker_id)
        if worker is None:
            return False
        worker.status = WorkerStatus.IDLE
        worker.current_task = ""
        self._notify("idle", worker)
        return True

    def set_error(self, worker_id: str, reason: str = "") -> bool:
        worker = self.get(worker_id)
        if worker is None:
            return False
        worker.status = WorkerStatus.ERROR
        if reason:
            worker.metadata["last_error"] = reason
        self._notify("error", worker)
        return True

    # ── Listeners ─────────────────────────────────────────────────────────────

    def add_listener(self, listener: WorkerListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: WorkerListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, event: str, worker: MeshWorker) -> None:
        for listener in self._listeners:
            try:
                listener(event, worker)
            except Exception:
                _log.exception("WorkerRegistry listener failed for event %s", event)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        workers = self.get_all()
        return {
            "total": len(workers),
            "idle": sum(1 for w in workers if w.status == WorkerStatus.IDLE),
            "busy": sum(1 for w in workers if w.status == WorkerStatus.BUSY),
            "error": sum(1 for w in workers if w.status == WorkerStatus.ERROR),
            "total_completed": sum(w.tasks_completed for w in workers),
            "total_failed": sum(w.tasks_failed for w in workers),
        }
