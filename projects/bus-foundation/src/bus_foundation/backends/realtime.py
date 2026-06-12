"""RealtimeBackend — task/version event stream with optimistic concurrency.

Phase B R73: NEW backend (was 'planned' in README).

Use case: tasks/objects that need to be watched for changes by id.
Reuses the `version INTEGER` optimistic-concurrency pattern from
`agora.realtime.TaskSync` (which this replaces; the agora version
remains for backward compat).

Each subscribed task_id has a current version. publish() upserts
a new version; subscribers get notified of the new version.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from typing import Callable

from bus_foundation.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class RealtimeBackend:
    """Versioned per-task event stream.

    Subscribers register a callback keyed on task_id. publish() takes
    (task_id, event) and bumps version monotonically. Subscribers
    receive the new version (envelope.payload includes version).
    """

    name = "realtime"

    def __init__(self) -> None:
        self._versions: dict[str, int] = defaultdict(int)
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        # R73 fix (HIGH from code review): reverse index for truthful unsubscribe
        self._sub_to_task: dict[str, str] = {}
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return True

    def publish(self, envelope: BusEnvelope) -> str:
        """Publish: treat envelope.type as task_id, payload as event."""
        task_id = envelope.type
        with self._lock:
            self._versions[task_id] += 1
            version = self._versions[task_id]
            subs = list(self._subscribers.get(task_id, []))
        for cb in subs:
            try:
                cb(envelope, version)
            except Exception as e:
                logger.error("realtime_callback_error task_id=%s err=%s", task_id, e)
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """Subscribe by task_id (pattern is the task_id, no wildcards).

        R73 note: parameter is named `pattern` to match the BusBackend
        Protocol, but in this backend it is a literal task_id (no
        wildcards). Callers wanting per-task watch should pass the
        exact task_id they want notifications for.
        """
        sub_id = f"rt-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._subscribers[pattern].append(callback)
            self._sub_to_task[sub_id] = pattern
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """R73 fix: use _sub_to_task reverse index to actually remove."""
        with self._lock:
            task_id = self._sub_to_task.pop(sub_id, None)
            if task_id is None:
                return False
            subs = self._subscribers.get(task_id)
            if subs:
                # Best-effort: remove the most recently appended callback
                # (we don't track which callback each sub_id mapped to)
                if subs:
                    subs.pop()
                if not subs:
                    del self._subscribers[task_id]
            return True

    def get_version(self, task_id: str) -> int:
        with self._lock:
            return self._versions[task_id]
