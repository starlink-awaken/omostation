from __future__ import annotations

"""
---
Type: Organ
Status: Experimental
Layer: L4-Gateway
Summary: Redis-backed message queue adapter for high-concurrency federation messaging.
         Drop-in replacement for SQLite-backed queue when Redis is available.
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Redis Message Queue ≡ Module
# 内涵 ≝ {Redis, Message, Queue}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, RedisMessageQueue)}
# 功能 ⊢ {Redis_Message, Message_Queue, Queue_Init}
# =============================================================================
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
from typing import Any  # noqa: E402

_log = logging.getLogger(__name__)

# Redis connection settings
REDIS_URL = os.environ.get("BOS_REDIS_URL", "")  # e.g. "redis://localhost:6379/0"
REDIS_QUEUE_PREFIX = os.environ.get("BOS_REDIS_QUEUE_PREFIX", "bos:gateway:")

__all__ = ["RedisMessageQueue"]


class RedisMessageQueue:
    """Redis-backed message queue for D-Gateway.

    Provides the same interface as the SQLite queue but with Redis backing
    for high-concurrency scenarios.  Requires ``BOS_REDIS_URL`` to be set.

    Falls back gracefully to ``is_available == False`` if Redis is
    unavailable (missing package, bad URL, or unreachable server); callers
    should check :attr:`is_available` and fall back to the SQLite queue.

    Example::

        q = RedisMessageQueue("tasks")
        if not q.is_available:
            q = SqliteMessageQueue("tasks")   # your existing impl
    """

    def __init__(self, queue_name: str) -> None:
        self._queue_name = queue_name
        self._redis: Any = None
        self._available = False
        self._connect()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        """Attempt to connect to Redis with exponential backoff retry (3 attempts)."""
        if not REDIS_URL:
            _log.debug("BOS_REDIS_URL not set; Redis queue disabled")
            return
        try:
            import redis  # type: ignore[import]
        except ImportError:
            _log.warning("redis package not installed; falling back to SQLite queue")
            return

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                self._redis = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis.ping()
                self._available = True
                _log.info("Redis message queue connected: %s", REDIS_URL)
                return
            except (OSError, ValueError) as exc:
                last_exc = exc
                wait = 2**attempt  # 1s, 2s, 4s
                _log.warning(
                    "Redis connection attempt %d/3 failed (%s); retrying in %ds",
                    attempt + 1,
                    exc,
                    wait,
                )
                import time

                time.sleep(wait)

        _log.warning(
            "Redis unavailable after 3 attempts (%s); using SQLite fallback", last_exc
        )
        self._redis = None

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """True when this instance is backed by a live Redis connection."""
        return self._available

    def enqueue(self, message: dict[str, Any], priority: int = 0) -> bool:
        """Enqueue *message*.  Returns ``True`` on success, ``False`` otherwise.

        Args:
            message:  JSON-serialisable dict to enqueue.
            priority: Reserved for future priority-queue support; currently
                      ignored (all messages are FIFO).

        Returns:
            ``True`` if the message was successfully pushed; ``False`` when
            Redis is unavailable or an error occurred.
        """
        if not self._available or self._redis is None:
            return False
        key = f"{REDIS_QUEUE_PREFIX}{self._queue_name}"
        try:
            self._redis.lpush(key, json.dumps(message))
            return True
        except Exception as exc:
            _log.error("Redis enqueue failed: %s", exc)
            return False

    def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """Blocking dequeue with *timeout* seconds.

        Uses ``BRPOP`` so the call returns as soon as a message is available,
        up to *timeout* seconds.

        Returns:
            Deserialized message dict, or ``None`` if the queue was empty /
            Redis is unavailable.
        """
        if not self._available or self._redis is None:
            return None
        key = f"{REDIS_QUEUE_PREFIX}{self._queue_name}"
        try:
            result = self._redis.brpop(key, timeout=int(timeout))
            if result:
                _, data = result
                return json.loads(data)
        except Exception as exc:
            _log.error("Redis dequeue failed: %s", exc)
        return None

    def queue_length(self) -> int:
        """Return the current number of items in the queue.

        Returns:
            Non-negative integer queue depth, or ``-1`` when Redis is
            unavailable or the length cannot be determined.
        """
        if not self._available or self._redis is None:
            return -1
        try:
            key = f"{REDIS_QUEUE_PREFIX}{self._queue_name}"
            return int(self._redis.llen(key))
        except Exception:
            return -1
