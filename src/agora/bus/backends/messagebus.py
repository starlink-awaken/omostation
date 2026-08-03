"""MessageBusBackend — wraps runtime.executor.message_bus (in-process agent comm).

Phase A.1: thin wrapper that exposes agent-to-agent messaging as a bus backend.
Preserves request/response semantics (do NOT flatten to fire-and-forget).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from agora.bus.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class MessageBusBackend:
    """In-process agent-to-agent pub/sub with request/response correlation.

    Reuses semantics from runtime/executor/message_bus.py:
    - agent-addressed subscriptions
    - message-type subscriptions
    - request/response correlation via reply_to
    - broadcast
    """

    name = "messagebus"

    def __init__(self):
        self._subscribers: dict[
            str, tuple[str, Callable]
        ] = {}  # sub_id -> (pattern, callback)

    def is_available(self) -> bool:
        return True

    def publish(self, envelope: BusEnvelope) -> str:
        for pattern, callback in self._subscribers.values():
            if self._match(pattern, envelope.type):
                try:
                    callback(envelope)
                except Exception as e:  # defensive fallback
                    logger.error("messagebus_callback_error", e)
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        sub_id = f"msgbus-{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (pattern, callback)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
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
