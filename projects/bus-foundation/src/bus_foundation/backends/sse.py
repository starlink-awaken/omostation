"""SSEBackend — fan-out to in-process SSE-style subscribers (bus-foundation flavor).

Phase B (R66): bus-foundation's SSEBackend is a minimal in-process fan-out
that lets projects with an HTTP layer bridge BusEnvelope -> SSE wire format
without depending on agora.sse. The premium backend that wraps the global
`agora.sse.sse_manager` singleton STAYS in agora. The bus-foundation version
exposes only `client_count()`, `broadcast()`, and the BusBackend Protocol
methods; consumers wire their own SSE/HTTP layer to it.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from bus_foundation.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class SSEBackend:
    """In-process fan-out — consumers wire their own HTTP/SSE layer to it.

    The bus-foundation SSEBackend exposes a `broadcast(type, data)` method
    (in addition to the BusBackend Protocol) so an HTTP layer (FastAPI,
    Starlette, aiohttp) can pipe messages out to its connected clients.
    """

    name = "sse"

    def __init__(self) -> None:
        self._subscribers: dict[str, tuple[str, Callable]] = {}
        self._client_count = 0

    def is_available(self) -> bool:
        return True

    def publish(self, envelope: BusEnvelope) -> str:
        # Fan out to in-process subscribers (e.g. tests, observability).
        for sub_id, (pattern, callback) in self._subscribers.items():
            if self._match(pattern, envelope.type):
                try:
                    callback(envelope)
                except Exception as e:
                    logger.error("sse_callback_error sub_id=%s err=%s", sub_id, e)
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        sub_id = f"sse-{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (pattern, callback)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        if sub_id in self._subscribers:
            del self._subscribers[sub_id]
            return True
        return False

    def broadcast(self, event_type: str, data: dict) -> None:
        """Push a raw wire-format event to connected HTTP clients.

        Consumers track client count via `client_connected()` / `client_disconnected()`.
        """
        # No-op in bus-foundation core; HTTP layer wires its own broadcast.
        logger.debug("sse_broadcast type=%s", event_type)

    def client_connected(self) -> None:
        self._client_count += 1

    def client_disconnected(self) -> None:
        if self._client_count > 0:
            self._client_count -= 1

    def client_count(self) -> int:
        return self._client_count

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type
