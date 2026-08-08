"""AsyncioBackend — in-process pubsub for async/await consumers.

Phase A.1: uses asyncio.Queue per subscriber, no external deps.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

from agora.bus.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class AsyncioBackend:
    """In-process pub/sub using asyncio.Queue.

    Use case: same-process consumers that want to await events
    without IPC / file I/O overhead.
    """

    name = "asyncio"

    def __init__(self):
        self._subscribers: dict[
            str, tuple[str, asyncio.Queue, asyncio.Task | None]
        ] = {}

    def __del__(self) -> None:
        # Best-effort teardown for short-lived test instances. The backend
        # owns the drain tasks it creates; cancel them so loop shutdown does
        # not report unraisable pending-task noise.
        for sub_id in list(self._subscribers):
            self.unsubscribe(sub_id)

    def is_available(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            # No running loop — backend works but consumer must use create_task
            return True

    def publish(self, envelope: BusEnvelope) -> str:
        for sub_id, (pattern, queue, _task) in self._subscribers.items():
            if self._match(pattern, envelope.type):
                try:
                    queue.put_nowait(envelope)
                except asyncio.QueueFull:
                    # Log includes sub_id and event id for observability.
                    # Drop the event — caller (router) decides DLQ policy.
                    logger.warning(
                        "asyncio_queue_full sub_id=%s event_id=%s", sub_id, envelope.id
                    )
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """Subscribe with a callback (sync) — backend fires callback via loop.

        For pure async, use subscribe_async() instead.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        sub_id = f"asyncio-{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (pattern, queue, None)

        # Spawn a task that drains the queue to the callback
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("asyncio_subscribe_no_loop sub_id=%s", sub_id)
            return sub_id

        async def _drain() -> None:
            while True:
                try:
                    env = await queue.get()
                except asyncio.CancelledError:
                    break
                try:
                    callback(env)
                except Exception as e:  # defensive fallback
                    logger.error("asyncio_callback_error err=%s", e)

        task = loop.create_task(_drain())
        self._subscribers[sub_id] = (pattern, queue, task)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        if sub_id in self._subscribers:
            _pattern, _queue, task = self._subscribers.pop(sub_id)
            if task is not None and not task.done():
                task.cancel()
            return True
        return False

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type
