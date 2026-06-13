"""AsyncioBackend — in-process pubsub for async/await consumers.

Phase A.1: uses asyncio.Queue per subscriber, no external deps.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

from bus_foundation.backends.pattern_match import match_pattern
from bus_foundation.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class AsyncioBackend:
    """In-process pub/sub using asyncio.Queue.

    Use case: same-process consumers that want to await events
    without IPC / file I/O overhead.
    """

    name = "asyncio"

    def __init__(self):
        self._subscribers: dict[str, tuple[str, asyncio.Queue]] = {}

    def is_available(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            # No running loop — backend works but consumer must use create_task
            return True

    def publish(self, envelope: BusEnvelope) -> str:
        for sub_id, (pattern, queue) in self._subscribers.items():
            if self._match(pattern, envelope.type):
                try:
                    queue.put_nowait(envelope)
                except asyncio.QueueFull:
                    logger.warning("asyncio_queue_full sub_id=%s event_id=%s", sub_id, envelope.id)
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """Subscribe with a callback (sync) — backend fires callback via loop."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        sub_id = f"asyncio-{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (pattern, queue)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("asyncio_subscribe_no_loop sub_id=%s", sub_id)
            return sub_id

        async def _drain() -> None:
            while True:
                env = await queue.get()
                try:
                    callback(env)
                except Exception as e:
                    logger.error("asyncio_callback_error err=%s", e)

        loop.create_task(_drain())
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        if sub_id in self._subscribers:
            del self._subscribers[sub_id]
            return True
        return False

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        return match_pattern(pattern, event_type)
