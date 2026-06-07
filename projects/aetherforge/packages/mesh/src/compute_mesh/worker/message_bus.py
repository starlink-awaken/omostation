"""WorkerMessageBus — Worker 间消息传递机制 (内存 Queue + SQLite 持久化).

借鉴 Ray 的 Object Store / Actor 通信模型:
  - 异步消息投递 (send/receive)
  - 按 Worker ID 路由
  - 可选 SQLite 持久化 (重启不丢消息)
  - 支持 pub/sub 模式

Usage::

    from compute_mesh.worker.message_bus import WorkerMessageBus

    bus = WorkerMessageBus()
    bus.send("worker-1", {"type": "task", "payload": "hello"})
    msgs = bus.receive("worker-1")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

_log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".aetherforge" / "message_bus.db"


@dataclass
class Message:
    """A single message on the bus."""

    id: str = ""
    """Unique message ID."""
    sender: str = ""
    """Worker ID of the sender."""
    recipient: str = ""
    """Worker ID of the recipient (or ``"*"`` for broadcast)."""
    msg_type: str = "generic"
    """Message type for routing (``"task"``, ``"result"``, ``"heartbeat"``)."""
    payload: dict[str, Any] = field(default_factory=dict)
    """Arbitrary message payload."""
    timestamp: float = 0.0
    """Unix timestamp of when the message was sent."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class WorkerMessageBus:
    """Message bus for inter-worker communication.

    Supports both in-memory (fast) and SQLite-backed (persistent) modes.
    Messages are delivered via :meth:`receive` (pull) or :meth:`subscribe`
    (push).
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None
        self._inbox: dict[str, list[Message]] = defaultdict(list)
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[Callable[[Message], None]]] = defaultdict(list)
        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite persistence."""
        if not self._db_path:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                msg_type TEXT NOT NULL DEFAULT 'generic',
                payload TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_recipient
            ON messages(recipient)
        """)
        conn.commit()
        conn.close()

    # ── Send ─────────────────────────────────────────────────────────────────

    def send(
        self,
        recipient: str,
        payload: dict[str, Any],
        msg_type: str = "generic",
        sender: str = "",
    ) -> str:
        """Send a message to *recipient* (or ``"*"`` for broadcast).

        Returns the message ID.
        """
        msg = Message(
            id=str(uuid4()),
            sender=sender,
            recipient=recipient,
            msg_type=msg_type,
            payload=payload,
            timestamp=time.time(),
        )

        with self._lock:
            # In-memory
            self._inbox[recipient].append(msg)

            # Persist to SQLite
            if self._db_path:
                self._persist_message(msg)

            # Notify subscribers
            for listener in self._subscribers.get(recipient, []):
                try:
                    listener(msg)
                except Exception:
                    _log.exception("Subscriber failed for message %s", msg.id)

            # Broadcast subscribers
            for listener in self._subscribers.get("*", []):
                try:
                    listener(msg)
                except Exception:
                    _log.exception("Broadcast subscriber failed for message %s", msg.id)

        _log.debug("Message %s sent to %s (type=%s)", msg.id[:8], recipient, msg_type)
        return msg.id

    def _persist_message(self, msg: Message) -> None:
        """Write message to SQLite."""
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute(
                """INSERT OR IGNORE INTO messages
                   (id, sender, recipient, msg_type, payload, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (msg.id, msg.sender, msg.recipient, msg.msg_type,
                 json.dumps(msg.payload), msg.timestamp),
            )
            conn.commit()
            conn.close()
        except Exception:
            _log.exception("Failed to persist message %s", msg.id)

    # ── Receive ──────────────────────────────────────────────────────────────

    def receive(self, worker_id: str, msg_type: str | None = None) -> list[Message]:
        """Receive all pending messages for *worker_id*.

        Args:
            worker_id: The worker's identifier.
            msg_type: Optional filter (e.g. ``"task"``).

        Returns:
            List of messages (oldest first). Messages are removed from
            the inbox after being received.
        """
        with self._lock:
            all_msgs = self._inbox.pop(worker_id, [])
            # Also collect broadcast messages
            broadcasts = self._inbox.pop("*", [])
            all_msgs.extend(broadcasts)

        if msg_type:
            all_msgs = [m for m in all_msgs if m.msg_type == msg_type]

        # Sort by timestamp (oldest first)
        all_msgs.sort(key=lambda m: m.timestamp)
        return all_msgs

    def peek(self, worker_id: str, limit: int = 10) -> list[Message]:
        """Peek at pending messages without consuming them."""
        with self._lock:
            msgs = list(self._inbox.get(worker_id, []))
            msgs.extend(self._inbox.get("*", []))
        msgs.sort(key=lambda m: m.timestamp)
        return msgs[:limit]

    # ── Subscribe ────────────────────────────────────────────────────────────

    def subscribe(self, worker_id: str, callback: Callable[[Message], None]) -> None:
        """Register a push callback for messages to *worker_id*.

        Use ``"*"`` to receive all messages (broadcast).
        """
        self._subscribers[worker_id].append(callback)

    def unsubscribe(self, worker_id: str, callback: Callable[[Message], None]) -> None:
        """Remove a previously registered callback."""
        if callback in self._subscribers.get(worker_id, []):
            self._subscribers[worker_id].remove(callback)

    # ── History ──────────────────────────────────────────────────────────────

    def get_history(self, worker_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get historical messages for *worker_id* from SQLite."""
        if not self._db_path:
            return []
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                """SELECT * FROM messages
                   WHERE recipient = ? OR recipient = '*'
                   ORDER BY timestamp DESC LIMIT ?""",
                (worker_id, limit),
            )
            rows = [dict(row) for row in c.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []

    # ── Stats ────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return bus statistics."""
        with self._lock:
            inbox_sizes = {wid: len(msgs) for wid, msgs in self._inbox.items()}
        return {
            "inbox_count": len(self._inbox),
            "pending_messages": sum(len(v) for v in self._inbox.values()),
            "subscribers": sum(len(v) for v in self._subscribers.values()),
            "persistence": str(self._db_path) if self._db_path else "memory-only",
        }

    def clear(self) -> None:
        """Clear all in-memory messages."""
        with self._lock:
            self._inbox.clear()
