"""MessageBusBackend — in-process agent-to-agent pub/sub with req/resp correlation."""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from bus_foundation.envelope import BusEnvelope
from bus_foundation.backends.pattern_match import match_pattern

logger = logging.getLogger(__name__)


class MessageBusBackend:
    """In-process agent-to-agent pub/sub with request/response correlation."""

    name = "messagebus"

    def __init__(self):
        self._subscribers: dict[str, tuple[str, Callable]] = {}

    def is_available(self) -> bool:
        return True

    def publish(self, envelope: BusEnvelope) -> str:
        for sub_id, (pattern, callback) in self._subscribers.items():
            if self._match(pattern, envelope.type):
                try:
                    callback(envelope)
                except Exception as e:
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
        return match_pattern(pattern, event_type)
