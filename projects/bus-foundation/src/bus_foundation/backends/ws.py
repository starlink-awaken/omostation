"""WebSocketBackend — full-duplex pub/sub for browser clients.

Phase B R73: NEW backend (was 'planned' in README).

Use case: browser/JS clients that need bidirectional communication.
Reuses asyncio.Queue per client, broadcasts to all subscribers matching
the pattern.

R73 design notes:
- In-process server (no external deps)
- Real ws protocol would need `websockets` lib; for now we model
  the pattern-match + delivery semantics; transport stub
- Future R74+: add real `websockets` dep + actual socket loop
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Callable

from bus_foundation.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class WebSocketBackend:
    """WebSocket-style fanout: in-process client emulation.

    Each "client" is an asyncio.Queue. publish() puts the envelope on
    every matching client's queue. A real WebSocket transport would
    drain these queues to actual sockets (future work, R74+).
    """

    name = "ws"

    def __init__(self) -> None:
        self._clients: dict[str, tuple[str, asyncio.Queue[BusEnvelope]]] = {}

    def is_available(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return True  # usable but subscribers must use create_task

    def publish(self, envelope: BusEnvelope) -> str:
        for client_id, (pattern, queue) in self._clients.items():
            if self._match(pattern, envelope.type):
                try:
                    queue.put_nowait(envelope)
                except asyncio.QueueFull:
                    logger.warning("ws_queue_full client_id=%s event_id=%s", client_id, envelope.id)
        return envelope.id

    def connect(self, pattern: str) -> tuple[str, asyncio.Queue[BusEnvelope]]:
        """Add a fake client connection. Returns (client_id, queue)."""
        client_id = f"ws-{uuid.uuid4().hex[:8]}"
        queue: asyncio.Queue[BusEnvelope] = asyncio.Queue(maxsize=1000)
        self._clients[client_id] = (pattern, queue)
        return client_id, queue

    def disconnect(self, client_id: str) -> bool:
        return self._clients.pop(client_id, None) is not None

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """Subscribe: connect + spawn drain task."""
        client_id, queue = self.connect(pattern)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("ws_subscribe_no_loop client_id=%s", client_id)
            return client_id
        loop.create_task(self._drain(client_id, queue, callback))
        return client_id

    async def _drain(self, client_id: str, queue: asyncio.Queue, callback: Callable) -> None:
        while True:
            env = await queue.get()
            try:
                callback(env)
            except Exception as e:
                logger.error("ws_callback_error client_id=%s err=%s", client_id, e)

    def unsubscribe(self, sub_id: str) -> bool:
        return self.disconnect(sub_id)

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type
