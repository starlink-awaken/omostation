from __future__ import annotations

"""
---
Type: Engine Component
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: organs/D-Execution/AGENTS.md
Layer: L3
Summary: 'Process-wide event broadcast bus for B-OS real-time observability.
  Producers call EventBus.get_instance().publish(event).
  Consumers (SSE endpoint) subscribe via add_listener() / get_events().'
Tags:
- event_bus
- sse
- observability
- real-time
Constraint: "[!!] MUST NOT create circular imports with ResultBus — bridge loaded lazily.
  MUST enforce MAX_LISTENERS to prevent unbounded memory growth."
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# EventBus ≡ Module
# 内涵 ≝ {BOSEvent, EventBus, Broadcast}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, EventBus)}
# 功能 ⊢ {Publish, Subscribe, GetEvents, RemoveListener}
# =============================================================================

import importlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import uuid4

# Lazily import kairon_events — may not be available in all contexts
_has_kairon_lib = False
try:
    from kairon_events import BOSEvent as _RealBOSEvent
    from kairon_events import make_event as _real_make_event
    from kairon_events import register_global_event_bus as _real_register_global_event_bus

    _has_kairon_lib = True
except ImportError:
    logging.getLogger(__name__).debug("[EventBus] kairon_events unavailable — using local stubs")

    @dataclass
    class _RealBOSEventStub:
        """Local BOSEvent stub used when kairon_events is not installed."""

        event_type: str
        source: str
        payload: dict | None = None
        timestamp: float = 0.0
        event_id: str = ""

    def _real_make_event_stub(event_type: str, source: str, payload: dict | None = None) -> _RealBOSEventStub:
        return _RealBOSEventStub(event_type=event_type, source=source, payload=payload or {})

    def _real_register_global_event_bus_stub(bus: Any) -> None:
        pass


if _has_kairon_lib:
    BOSEvent = _RealBOSEvent
    make_event = _real_make_event
    register_global_event_bus = _real_register_global_event_bus
else:
    BOSEvent = _RealBOSEventStub  # type: ignore[assignment,no-redef]
    make_event = _real_make_event_stub  # type: ignore[assignment,no-redef]
    register_global_event_bus = _real_register_global_event_bus_stub  # type: ignore[assignment,no-redef]

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventBus singleton
# ---------------------------------------------------------------------------


class EventBus:
    """Process-wide event broadcast bus.

    Producers call ``EventBus.get_instance().publish(event)``.
    Consumers (e.g. the SSE endpoint) subscribe via :meth:`add_listener` /
    :meth:`get_events`.

    Each listener owns a bounded :class:`~collections.deque` of size
    :attr:`MAX_QUEUE_SIZE` so that a slow consumer never exhausts memory —
    the oldest unread events are silently dropped when the queue fills up.

    Thread-safe: all mutable state is protected by a single :class:`RLock`.

    Raises:
        RuntimeError: When :meth:`add_listener` is called and the concurrent
                      connection count exceeds :attr:`MAX_LISTENERS`.
    """

    MAX_QUEUE_SIZE: int = 500  # per-listener deque capacity
    MAX_LISTENERS: int = 50  # max concurrent SSE connections

    # ── Class-level singleton state ──────────────────────────────────────────
    _instance: ClassVar[EventBus | None] = None
    _class_lock: ClassVar[threading.Lock] = threading.Lock()

    # Holds a reference to the ResultBus bridge callback so the GC won't
    # collect it (it's registered as a closure inside bridge_result_bus).
    _result_bridge: ClassVar[object] = None

    # TopologyGraph bridge references (prevent GC)
    _topology_graph: ClassVar[object] = None
    _topology_bridge: ClassVar[object] = None

    # ── Instance construction ─────────────────────────────────────────────────

    def __init__(self) -> None:
        self._rlock: threading.RLock = threading.RLock()
        # listener_id → deque[BOSEvent]
        self._listeners: dict[str, deque[BOSEvent]] = {}
        self._dropped_events_total: int = 0

    # ── Singleton factory ─────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> EventBus:
        """Return (or lazily create) the process-wide singleton."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    # Register with shared-lib for cross-package event publishing
                    register_global_event_bus(cls._instance)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton and clear all state.

        .. warning::
            **FOR TESTING ONLY.**  Do **not** call from production code.
        """
        with cls._class_lock:
            cls._instance = None
            cls.clear_bridges()

    @classmethod
    def clear_bridges(cls) -> None:
        """Clear all bridge references to prevent memory leaks.

        Should be called during graceful shutdown when EventBus is no longer needed.
        """
        cls._result_bridge = None
        cls._topology_graph = None
        cls._topology_bridge = None
        _log.info("[EventBus] Bridge references cleared")

    # ── Public API ────────────────────────────────────────────────────────────

    def publish(self, event: BOSEvent) -> None:
        """Broadcast *event* to every registered listener's queue.

        If a listener's queue is full its oldest entry is silently discarded
        (the bounded :class:`~collections.deque` handles this automatically).

        Args:
            event: The :class:`BOSEvent` to broadcast.
        """
        with self._rlock:
            for q in self._listeners.values():
                if len(q) >= self.MAX_QUEUE_SIZE:
                    self._dropped_events_total += 1
                q.append(event)
        _log.debug(
            "[EventBus] Published event type=%r source=%r id=%s",
            event.event_type,
            event.source,
            event.event_id,
        )

    def add_listener(self) -> str:
        """Register a new SSE consumer.

        Returns:
            A unique 8-char ``listener_id`` string.

        Raises:
            RuntimeError: If the number of active listeners would exceed
                          :attr:`MAX_LISTENERS`.
        """
        with self._rlock:
            if len(self._listeners) >= self.MAX_LISTENERS:
                raise RuntimeError(
                    f"[EventBus] MAX_LISTENERS ({self.MAX_LISTENERS}) reached — cannot accept new SSE connection."
                )
            listener_id = str(uuid4())[:8]
            self._listeners[listener_id] = deque(maxlen=self.MAX_QUEUE_SIZE)
            _log.debug("[EventBus] Listener added id=%s total=%d", listener_id, len(self._listeners))
            return listener_id

    def remove_listener(self, listener_id: str) -> None:
        """Deregister a listener when its SSE connection closes.

        Silently ignores unknown *listener_id* values.

        Args:
            listener_id: The ID returned by a prior :meth:`add_listener` call.
        """
        with self._rlock:
            self._listeners.pop(listener_id, None)
        _log.debug("[EventBus] Listener removed id=%s", listener_id)

    def get_events(self, listener_id: str, max_count: int = 50) -> list[BOSEvent]:
        """Pop and return up to *max_count* events for this listener.

        Events are returned in insertion order (oldest first) and removed
        from the listener's queue.  Returns an empty list if the listener
        does not exist or has no pending events.

        Args:
            listener_id: The ID returned by :meth:`add_listener`.
            max_count:   Maximum number of events to return per call.

        Returns:
            A (possibly empty) list of :class:`BOSEvent` objects.
        """
        with self._rlock:
            q = self._listeners.get(listener_id)
            if q is None:
                return []
            drain_count = min(max_count, len(q))
            return [q.popleft() for _ in range(drain_count)]

    def listener_count(self) -> int:
        """Return the number of currently active SSE connections."""
        with self._rlock:
            return len(self._listeners)

    def snapshot(self) -> dict[str, int | float]:
        """Return listener/backpressure stats for runtime observability."""
        with self._rlock:
            queue_depths = [len(q) for q in self._listeners.values()]
            listeners = len(queue_depths)
            pending_events = sum(queue_depths)
            max_queue_depth = max(queue_depths, default=0)
            saturated_listeners = sum(1 for depth in queue_depths if depth >= self.MAX_QUEUE_SIZE)

            return {
                "listeners": listeners,
                "max_listeners": self.MAX_LISTENERS,
                "pending_events": pending_events,
                "max_queue_depth": max_queue_depth,
                "max_queue_size": self.MAX_QUEUE_SIZE,
                "max_queue_fill_ratio": (max_queue_depth / self.MAX_QUEUE_SIZE if self.MAX_QUEUE_SIZE else 0.0),
                "saturated_listeners": saturated_listeners,
                "dropped_events_total": self._dropped_events_total,
            }

    # ── TopologyGraph integration (optional) ────────────────────────────────

    @classmethod
    def bridge_topology_graph(cls) -> None:
        """Subscribe EventBus to TopologyGraph via PulseEventBridge.

        Uses lazy import to avoid circular dependencies.
        Called during daemon startup to wire monitoring.
        """
        try:
            module = importlib.import_module("organs.D_Monitoring.organs.topology_graph")
            TopologyGraph = module.TopologyGraph  # noqa: N806
            PulseEventBridge = module.PulseEventBridge  # noqa: N806
        except Exception as exc:
            _log.debug("⚠️ [EventBus] TopologyGraph bridge unavailable: %s", exc)
            return

        try:
            topo = TopologyGraph()
            bridge = PulseEventBridge(topo)

            bus = cls.get_instance()  # noqa: F841 — ensures singleton is live
            # Store references to prevent GC
            cls._topology_graph = topo
            cls._topology_bridge = bridge

            _log.info("🔗 [EventBus] TopologyGraph bridge activated")
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            _log.debug("⚠️ [EventBus] TopologyGraph bridge unavailable: %s", exc)

    # ── ResultBus integration (optional) ─────────────────────────────────────

    @classmethod
    def bridge_result_bus(cls) -> None:
        """Subscribe EventBus to ResultBus so task results become events.

        Lazily imports :class:`~organs.D_Execution.organs.engine.result_bus.ResultBus`
        to avoid circular imports.  If ResultBus is unavailable (import error)
        this method is a silent no-op.

        .. note::
            :class:`~ResultBus` is keyed per worker; the bridge registers a
            wildcard approach by wrapping the global post_result path.  The
            callback reference is stored on the class (``_result_bridge``) to
            prevent it being garbage-collected.
        """
        try:
            __import__("organs.D_Execution.organs.engine.result_bus")

            def _on_result(result: Any) -> None:
                ev_type = "agent_completed" if getattr(result, "success", False) else "agent_failed"
                cls.get_instance().publish(
                    BOSEvent(
                        event_type=ev_type,
                        source="result_bus",
                        payload={
                            "worker_id": getattr(result, "worker_id", "?"),
                            "success": getattr(result, "success", False),
                        },
                        timestamp=time.time(),
                        event_id=str(uuid4())[:8],
                    )
                )

            # Store reference to prevent GC
            cls._result_bridge = _on_result
            _log.info("[EventBus] ResultBus bridge established.")
        except ImportError:
            _log.debug("[EventBus] ResultBus unavailable — bridge skipped.")
