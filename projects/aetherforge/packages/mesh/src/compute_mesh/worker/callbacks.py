"""StepCallbacks — hook system for task lifecycle events (vs CrewAI callbacks).

Allows registering callbacks at each stage of task execution::

    from compute_mesh.worker.callbacks import StepCallbacks

    cb = StepCallbacks()

    @cb.on_task_start
    def log_start(worker_id, task):
        print(f"Starting {task} on {worker_id}")

    @cb.on_task_complete
    def log_complete(worker_id, result):
        print(f"Done: {result['latency_ms']}ms")

    dispatcher.set_callbacks(cb)
    dispatcher.dispatch("ollama-local", prompt="hello")
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

_log = logging.getLogger(__name__)

# Type aliases
TaskCallback = Callable[..., None]
_HandlerList = list[Callable[..., None]]


class StepCallbacks:
    """Mutable collection of lifecycle hooks for task execution.

    Each attribute is a list of handlers. Use ``.add()`` or decorator
    syntax to register::

        cb = StepCallbacks()
        cb.on_task_start.add(my_handler)   # add
        cb.on_task_start.remove(my_handler)  # remove
        cb.on_task_start.clear()            # clear
    """

    def __init__(self) -> None:
        self._on_task_start: _HandlerList = []
        self._on_task_complete: _HandlerList = []
        self._on_task_fail: _HandlerList = []
        self._on_worker_claim: _HandlerList = []
        self._on_worker_release: _HandlerList = []
        self._on_retry: _HandlerList = []

    # ── Handler collection helper ────────────────────────────────────────────

    class _HandlerCollection:
        """A list of handlers with add/remove/clear and decorator support."""

        def __init__(self, store: _HandlerList) -> None:
            self._store = store

        def add(self, fn: Callable) -> None:
            self._store.append(fn)

        def remove(self, fn: Callable) -> None:
            if fn in self._store:
                self._store.remove(fn)

        def clear(self) -> None:
            self._store.clear()

        def __call__(self, fn: Callable) -> Callable:
            """Decorator usage: @cb.on_task_start"""
            self._store.append(fn)
            return fn

        def __len__(self) -> int:
            return len(self._store)

    @property
    def on_task_start(self) -> _HandlerCollection:
        """Called with ``(worker_id, task_description)`` before execution."""
        return StepCallbacks._HandlerCollection(self._on_task_start)

    @property
    def on_task_complete(self) -> _HandlerCollection:
        """Called with ``(worker_id, result_dict)`` on successful completion."""
        return StepCallbacks._HandlerCollection(self._on_task_complete)

    @property
    def on_task_fail(self) -> _HandlerCollection:
        """Called with ``(worker_id, error_str)`` on failure."""
        return StepCallbacks._HandlerCollection(self._on_task_fail)

    @property
    def on_worker_claim(self) -> _HandlerCollection:
        """Called with ``(worker_id)`` when a worker is claimed for a task."""
        return StepCallbacks._HandlerCollection(self._on_worker_claim)

    @property
    def on_worker_release(self) -> _HandlerCollection:
        """Called with ``(worker_id)`` when a worker is released."""
        return StepCallbacks._HandlerCollection(self._on_worker_release)

    @property
    def on_retry(self) -> _HandlerCollection:
        """Called with ``(worker_id, attempt, error)`` on retry."""
        return StepCallbacks._HandlerCollection(self._on_retry)

    # ── Fire methods (used by TaskDispatcher) ────────────────────────────────

    def fire_task_start(self, worker_id: str, task: str) -> None:
        for fn in self._on_task_start:
            try:
                fn(worker_id, task)
            except Exception:
                _log.exception("on_task_start handler failed")

    def fire_task_complete(self, worker_id: str, result: dict[str, Any]) -> None:
        for fn in self._on_task_complete:
            try:
                fn(worker_id, result)
            except Exception:
                _log.exception("on_task_complete handler failed")

    def fire_task_fail(self, worker_id: str, error: str) -> None:
        for fn in self._on_task_fail:
            try:
                fn(worker_id, error)
            except Exception:
                _log.exception("on_task_fail handler failed")

    def fire_worker_claim(self, worker_id: str) -> None:
        for fn in self._on_worker_claim:
            try:
                fn(worker_id)
            except Exception:
                _log.exception("on_worker_claim handler failed")

    def fire_worker_release(self, worker_id: str) -> None:
        for fn in self._on_worker_release:
            try:
                fn(worker_id)
            except Exception:
                _log.exception("on_worker_release handler failed")

    def fire_retry(self, worker_id: str, attempt: int, error: str) -> None:
        for fn in self._on_retry:
            try:
                fn(worker_id, attempt, error)
            except Exception:
                _log.exception("on_retry handler failed")
