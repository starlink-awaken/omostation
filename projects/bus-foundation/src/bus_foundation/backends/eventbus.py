"""EventBusBackend — in-process pubsub (bus-foundation flavor).

Phase B (R66): bus-foundation has NO agora dependency. The premium backend
that wraps `agora.core.event_bus` STAYS in agora (it is an agora-specific
premium backend that consumers can opt into). The bus-foundation version
here is a simple in-process dict-of-lists pubsub for projects that don't
need agora's persistent-event-log semantics.
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable

from bus_foundation.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class EventBusBackend:
    """Simple in-process pub/sub for bus-foundation (zero external deps).

    Implementation: dict[sub_id] = (pattern, callback). Publish() iterates
    and dispatches synchronously. Patterns: '*' (all), 'foo:*' (prefix),
    'foo:bar' (exact).

    Thread safety: subscribe/unsubscribe guarded by a lock. Publish takes
    the lock briefly to copy the subscriber list, then dispatches outside
    the lock (callbacks must not call subscribe/unsubscribe of the same
    backend from within a callback, but the dict copy prevents iteration
    races on simple cases).
    """

    name = "eventbus"

    def __init__(self) -> None:
        self._subscribers: dict[str, tuple[str, Callable]] = {}
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """In-process backend is always available."""
        return True

    def publish(self, envelope: BusEnvelope) -> str:
        with self._lock:
            snapshot = list(self._subscribers.items())
        for sub_id, (pattern, callback) in snapshot:
            if self._match(pattern, envelope.type):
                try:
                    callback(envelope)
                except Exception as e:
                    logger.error("eventbus_callback_error sub_id=%s err=%s", sub_id, e)
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        sub_id = f"eventbus-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._subscribers[sub_id] = (pattern, callback)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        with self._lock:
            if sub_id in self._subscribers:
                del self._subscribers[sub_id]
                return True
            return False

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type
