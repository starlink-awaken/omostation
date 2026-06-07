from __future__ import annotations

from ._compat import TaskResult, TaskType, WorkerBundle, WorkerHandle

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
# Worker Pool ≡ Worker
# 内涵 ≝ {Worker, Pool}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, WorkerPool)}
# 功能 ⊢ {Worker_Pool, Init_Worker, Validate_Pool}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: WorkerPool — worker registry, heartbeat tracking, stale detection.
  Extracted from SwarmLifecycleManager._workers, _heartbeats, ping_heartbeat(),
  touch_heartbeat(), get_stale_workers(), list_active(), list_active_threads(),
  get_handle(), all_handles().
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
---

Responsibility: Single — maintain the worker registry and heartbeat state.
Does not handle spawning, reaping, or persistence.
"""

import logging
import time
from collections.abc import Iterator, MutableMapping
from threading import RLock
from typing import Any

_log = logging.getLogger(__name__)

# Module-level re-export for backward compatibility
logger = logging.getLogger(__name__)


class WorkerNotFoundError(LookupError):
    """Raised when a worker_id is not in the active registry."""


class LegacyWorkerRegistry(MutableMapping[str, "WorkerHandle"]):
    """Compatibility view that exposes live and reaped worker handles."""

    def __init__(self, pool: WorkerPool) -> None:
        self._pool = pool

    def __getitem__(self, worker_id: str) -> WorkerHandle:
        with self._pool._lock:
            handle = self._pool._workers.get(worker_id)
            if handle is not None:
                return handle

            bundle = self._pool._bundles.get(worker_id)
            bundle_handle = getattr(bundle, "handle", None)
            if bundle_handle is not None:
                return bundle_handle

        raise KeyError(worker_id)

    def __setitem__(self, worker_id: str, handle: WorkerHandle) -> None:
        with self._pool._lock:
            self._pool._workers[worker_id] = handle
            self._pool._heartbeats.setdefault(worker_id, time.time())

    def __delitem__(self, worker_id: str) -> None:
        removed = False
        with self._pool._lock:
            if worker_id in self._pool._workers:
                self._pool._workers.pop(worker_id, None)
                self._pool._heartbeats.pop(worker_id, None)
                self._pool._thread_worker_ids.discard(worker_id)
                removed = True
            if worker_id in self._pool._bundles:
                self._pool._bundles.pop(worker_id, None)
                removed = True

        if not removed:
            raise KeyError(worker_id)

    def __iter__(self) -> Iterator[str]:
        with self._pool._lock:
            worker_ids = dict.fromkeys([*self._pool._workers.keys(), *self._pool._bundles.keys()])
        return iter(tuple(worker_ids))

    def __len__(self) -> int:
        with self._pool._lock:
            return len(set(self._pool._workers) | set(self._pool._bundles))

    def __contains__(self, worker_id: Any) -> bool:
        if not isinstance(worker_id, str):
            return False
        with self._pool._lock:
            if worker_id in self._pool._workers:
                return True
            bundle = self._pool._bundles.get(worker_id)
            return getattr(bundle, "handle", None) is not None


class WorkerPool:
    """
    Thread-safe worker registry with heartbeat tracking.

    Responsibility: Manage the in-memory worker registry, heartbeats,
    task result accumulation, and handle snapshots.
    All state is held in memory; persistence is handled by SwarmPersistence.

    Usage::

        pool = WorkerPool()
        pool.register(handle)
        pool.ping_heartbeat("worker-1")
        active = pool.list_active()
    """

    def __init__(
        self,
        heartbeat_timeout: float = 30.0,
    ) -> None:
        self._lock = RLock()
        self._workers: dict[str, WorkerHandle] = {}
        self._bundles: dict[str, Any] = {}  # worker_id -> WorkerBundle (built lazily)
        self._heartbeats: dict[str, float] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._thread_worker_ids: set[str] = set()
        self._legacy_workers = LegacyWorkerRegistry(self)

    # ─── Registration ────────────────────────────────────────────────────────

    def register(
        self,
        handle: WorkerHandle,
        is_thread_worker: bool = False,
    ) -> None:
        """Register a live worker handle."""
        with self._lock:
            self._workers[handle.worker_id] = handle
            self._heartbeats[handle.worker_id] = time.time()
            if is_thread_worker:
                self._thread_worker_ids.add(handle.worker_id)

    def unregister(self, worker_id: str) -> None:
        """Remove a worker from the registry."""
        with self._lock:
            self._workers.pop(worker_id, None)
            self._heartbeats.pop(worker_id, None)
            self._thread_worker_ids.discard(worker_id)

    # ─── Heartbeat ────────────────────────────────────────────────────────────

    def ping_heartbeat(self, worker_id: str) -> None:
        """Record a heartbeat ping for a worker."""
        with self._lock:
            self._heartbeats[worker_id] = time.time()

    def touch_heartbeat(self, worker_id: str) -> None:
        """Update last_heartbeat timestamp on a handle and persist heartbeat."""
        with self._lock:
            handle = self._workers.get(worker_id)
            if handle:
                handle.last_heartbeat = time.time()
                self._heartbeats[worker_id] = time.time()

    def get_stale_workers(self) -> list[str]:
        """Return IDs of active workers that have not pinged within the timeout."""
        with self._lock:
            stale = []
            now = time.time()
            for worker_id, last_ping in self._heartbeats.items():
                if now - last_ping > self._heartbeat_timeout:
                    if worker_id in self._workers:
                        h = self._workers[worker_id]
                        if h.state.name == "ACTIVE":  # pylint: disable=protected-access
                            stale.append(worker_id)
            return stale

    # ─── Accessors ────────────────────────────────────────────────────────────

    def list_active(self) -> list[WorkerHandle]:
        """Return all workers in ACTIVE or STARVING state."""
        with self._lock:
            return [h for h in self._workers.values() if h.state.name in ("ACTIVE", "STARVING")]

    def list_active_threads(self) -> list[WorkerHandle]:
        """Return WorkerHandles for internal-thread workers in ACTIVE or STARVING."""
        with self._lock:
            return [
                h
                for worker_id, h in self._workers.items()
                if worker_id in self._thread_worker_ids and h.state.name in ("ACTIVE", "STARVING")
            ]

    def get_handle(self, worker_id: str) -> WorkerHandle:
        """Retrieve a live WorkerHandle by ID."""
        with self._lock:
            handle = self._workers.get(worker_id)
        if handle is None:
            raise WorkerNotFoundError(f"[WorkerPool] Worker '{worker_id}' not found.")
        return handle

    def get_handle_unsafe(self, worker_id: str) -> WorkerHandle | None:
        """Retrieve a handle without raising (for internal use)."""
        with self._lock:
            return self._workers.get(worker_id)

    def all_handles(self) -> dict[str, WorkerHandle]:
        """Return a snapshot copy of the internal workers dict."""
        with self._lock:
            return dict(self._workers)

    def handle_count(self) -> int:
        """Return total number of registered workers."""
        with self._lock:
            return len(self._workers)

    def active_count(self) -> int:
        """Return number of workers in ACTIVE state."""
        with self._lock:
            return sum(1 for h in self._workers.values() if h.state.name == "ACTIVE")

    def legacy_workers(self) -> LegacyWorkerRegistry:
        """Return a live compatibility view over active and reaped workers."""
        return self._legacy_workers

    def mark_thread_worker(self, worker_id: str) -> None:
        """Mark a worker as an internal-thread worker."""
        with self._lock:
            self._thread_worker_ids.add(worker_id)

    # ─── Task results ────────────────────────────────────────────────────────

    def record_task_result(
        self,
        result: TaskResult,
    ) -> WorkerHandle:
        """Append a completed TaskResult to the worker's accumulating list.

        Returns:
            The updated WorkerHandle.

        Raises:
            WorkerNotFoundError: If result.worker_id is unknown.
        """
        with self._lock:
            if result.worker_id not in self._workers:
                raise WorkerNotFoundError(
                    f"[WorkerPool] Worker '{result.worker_id}' not found when recording task result."
                )
            handle = self._workers[result.worker_id]
            handle.eu_consumed += result.eu_consumed
            handle.last_heartbeat = time.time()
            self._heartbeats[result.worker_id] = time.time()

            # Accumulate into pre-bundle list stored on the handle
            if not hasattr(handle, "_task_results"):
                object.__setattr__(handle, "_task_results", [])
            handle._task_results.append(result)  # type: ignore[attr-defined]

        _log.debug(
            "[WorkerPool] Task result recorded for '%s': success=%s eu=%.2f",
            result.worker_id,
            result.success,
            result.eu_consumed,
        )
        return handle

    def store_bundle(self, worker_id: str, bundle: Any) -> None:
        """Store a completed WorkerBundle after reap."""
        with self._lock:
            self._bundles[worker_id] = bundle

    def get_bundle(self, worker_id: str) -> Any | None:
        """Retrieve a stored WorkerBundle."""
        with self._lock:
            return self._bundles.get(worker_id)

    def build_bundle(self, worker_id: str) -> Any:
        """Assemble a WorkerBundle from accumulated task results on a handle."""

        with self._lock:
            handle = self._workers[worker_id]
            task_results: list[TaskResult] = getattr(handle, "_task_results", [])

        total_eu = sum(r.eu_consumed for r in task_results)
        total_tasks = len(task_results)
        successful = sum(1 for r in task_results if r.success)

        return WorkerBundle(
            handle=handle,
            task_type=TaskType.UNKNOWN,
            task_results=tuple(task_results),
            total_eu_consumed=total_eu,
            total_tasks=total_tasks,
            successful_tasks=successful,
            nectar_earned=0.0,  # Nectar calculation delegated to INectarEngine
        )
