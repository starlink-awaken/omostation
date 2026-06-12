"""PersistentBusBackend — durable in-process pub/sub via SQLite.

Phase B R73: NEW backend. Cross-process pub/sub for low-throughput,
durable-delivery scenarios (audit logs, task notifications, workflows
that need resume-on-restart).

Use case: when you want the fire-and-forget semantics of EventBus but
need the events to survive a process restart. NOT for high-throughput
production pub/sub (use Kafka/NATS for that).

Design (intentionally simple):
- SQLite table with WAL mode for concurrent reads + 1 writer
- Insert on publish, fanout via in-process subscriber list
- Optional retention: keep last N events (default: 10000)
- Subscriber register_hook for in-process delivery (reuses BusBackend
  protocol contract)
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bus_foundation.envelope import BusEnvelope
from bus_foundation.backends.pattern_match import match_pattern

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".runtime" / "bus_persistent.db"
MAX_EVENTS = 10_000
SUBSCRIBER_TTL_SECONDS = 24 * 3600


class PersistentBusBackend:
    """SQLite-backed durable pub/sub.

    One SQLite DB, WAL mode. Subscribers are in-process callbacks
    (cross-process delivery is via the SQLite file itself, polled by
    other processes if needed).
    """

    name = "persistent"

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._open_conn()
        self._init_schema()
        self._subscribers: dict[str, tuple[str, float, Callable]] = {}
        self._gc()

    def _open_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS persistent_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    source TEXT,
                    time TEXT NOT NULL,
                    envelope_json TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS persistent_events_type_time
                ON persistent_events(event_type, time)
            """)
            self._conn.commit()

    def _gc(self) -> None:
        """Trim to MAX_EVENTS (FIFO)."""
        with self._lock:
            count_row = self._conn.execute("SELECT COUNT(*) AS n FROM persistent_events").fetchone()
            n = count_row["n"] if count_row else 0
            if n > MAX_EVENTS:
                excess = n - MAX_EVENTS
                self._conn.execute(
                    """
                    DELETE FROM persistent_events
                    WHERE id IN (
                        SELECT id FROM persistent_events ORDER BY time ASC LIMIT ?
                    )
                    """,
                    (excess,),
                )
                self._conn.commit()
                logger.info("persistent_gc trimmed=%d", excess)

    def _now(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def is_available(self) -> bool:
        try:
            return self.db_path.parent.exists()
        except Exception:
            return False

    def publish(self, envelope: BusEnvelope) -> str:
        now = self._now()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO persistent_events (id, event_type, source, time, envelope_json) VALUES (?, ?, ?, ?, ?)",
                (envelope.id, envelope.type, envelope.source, now, envelope.to_json()),
            )
            self._conn.commit()
        # In-process fanout
        self._cleanup_subs()
        for sub_id, (pattern, _last_seen, callback) in self._subscribers.items():
            if self._match(pattern, envelope.type):
                try:
                    callback(envelope)
                except Exception as e:
                    logger.error("persistent_callback_error sub_id=%s err=%s", sub_id, e)
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        sub_id = f"persistent-{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (pattern, time.monotonic(), callback)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        return self._subscribers.pop(sub_id, None) is not None

    def _cleanup_subs(self) -> None:
        """Drop subscribers that haven't been seen in SUBSCRIBER_TTL_SECONDS.

        R74 fix: use time.monotonic() for TTL delta (right call for elapsed
        time; immune to system clock changes).
        """
        now = time.monotonic()
        expired = [sid for sid, (_, _last, _) in self._subscribers.items() if now - _last > SUBSCRIBER_TTL_SECONDS]
        for sid in expired:
            del self._subscribers[sid]

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        # R74 LOW fix: delegate to shared helper (deduplicates 6 copies)
        return match_pattern(pattern, event_type)

    def get_recent(self, event_type: str = "", limit: int = 100) -> list[dict[str, Any]]:
        """Query historical events (for catch-up on restart)."""
        with self._lock:
            if event_type:
                rows = self._conn.execute(
                    "SELECT * FROM persistent_events WHERE event_type = ? ORDER BY time DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM persistent_events ORDER BY time DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
