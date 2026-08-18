from __future__ import annotations

import logging
import threading
import time

import redis

from .message_broker import MessageBroker
from .role_message import RoleMessage

_log = logging.getLogger(__name__)


class RedisMessageBroker(MessageBroker):
    """
    Production-grade message broker using Redis Lists and PubSub.
    Extends the base MessageBroker interface (duck-typing) for compatibility.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "swarm:") -> None:
        super().__init__()
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix
        self._pubsub = self._redis.pubsub()
        self._run_pubsub = True
        self._pubsub_thread: threading.Thread | None = None
        self._registered_roles: set[str] = set()

        self._start_pubsub_listener()

    def _get_queue_key(self, role_id: str) -> str:
        return f"{self._prefix}queue:{role_id}"

    def _get_broadcast_channel(self) -> str:
        return f"{self._prefix}broadcast"

    def register_role(self, role_id: str) -> None:
        with self._lock:
            self._registered_roles.add(role_id)
            # Ensure list exists by not doing anything (Redis creates on push)

    def unregister_role(self, role_id: str) -> None:
        with self._lock:
            self._registered_roles.discard(role_id)
            self._redis.delete(self._get_queue_key(role_id))

    def send(self, message: RoleMessage) -> bool:
        """Send message via Redis."""
        # Notify local global listeners
        for listener in self._global_listeners:
            try:
                listener(message)
            except Exception:
                _log.debug("Global listener raised an exception", exc_info=True)

        payload = message.to_json()

        if message.target_role_id:
            # Point-to-Point (Redis List LPUSH)
            # We don't support true Priority Queue in Redis List trivially,
            # but we can use simple list for demonstration, or multiple lists for priority.
            # To keep it simple, we push to a single list.
            self._redis.lpush(self._get_queue_key(message.target_role_id), payload)
            return True
        else:
            # Broadcast (Redis Pub/Sub)
            self._redis.publish(self._get_broadcast_channel(), payload)
            return True

    def receive(self, role_id: str, timeout: float | None = None) -> RoleMessage | None:
        """Receive message via Redis List BRPOP."""
        if role_id not in self._registered_roles:
            return None

        key = self._get_queue_key(role_id)
        # timeout=0 means block indefinitely in redis-py, whereas Python queue block forever is None
        t = int(timeout) if timeout else 0
        try:
            result = self._redis.brpop([key], timeout=t)
            if result:
                _, payload = result
                return RoleMessage.from_json(payload)  # type: ignore[reportArgumentType]
        except redis.RedisError as e:
            _log.error(f"Redis receive error for {role_id}: {e}")
        return None

    def _start_pubsub_listener(self) -> None:
        self._pubsub.subscribe(self._get_broadcast_channel())

        def listener() -> None:
            while self._run_pubsub:
                message = self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        role_msg = RoleMessage.from_json(message["data"])
                        # Broadcast message received, distribute to all local roles
                        with self._lock:
                            for role_id in self._registered_roles:
                                if role_id != role_msg.sender_role_id:
                                    self._redis.lpush(self._get_queue_key(role_id), message["data"])
                    except Exception as e:
                        _log.error(f"Failed to process broadcast message: {e}")
                time.sleep(0.01)

        self._pubsub_thread = threading.Thread(target=listener, daemon=True)
        self._pubsub_thread.start()

    def close(self) -> None:
        self._run_pubsub = False
        if self._pubsub_thread:
            self._pubsub_thread.join()
        self._pubsub.close()
        self._redis.close()
