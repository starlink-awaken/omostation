"""SQLite-backed persistent task store with state machine and retry logic."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)


class TaskState(Enum):
    """Lifecycle states for a persisted task record."""

    pending = "pending"
    running = "running"
    retrying = "retrying"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    dead_letter = "dead_letter"
    decomposed = "decomposed"


@dataclass
class TaskRecord:
    """Persistent snapshot of a task lifecycle."""

    task_id: str
    intent: str
    state: TaskState = TaskState.pending
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: str = ""
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0
    next_retry_at: float | None = None
    priority: int = 5
    deadline: float | None = None
    worker_id: str = ""
    estimated_eu: float = 1.0
    role_id: str = ""
    task_type: str = ""
    parent_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (1 <= self.priority <= 10):
            msg = f"priority must be 1-10, got {self.priority}"
            raise ValueError(msg)

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["metadata"] = json.dumps(self.metadata)
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> TaskRecord:
        raw_meta = row.get("metadata")
        metadata = json.loads(raw_meta) if raw_meta else {}
        return cls(
            task_id=row["task_id"],
            intent=row["intent"],
            state=TaskState(row["state"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            result=row["result"],
            error=row["error"],
            retry_count=row["retry_count"],
            max_retries=row.get("max_retries", 3),
            retry_delay=row.get("retry_delay", 1.0),
            backoff_factor=row.get("backoff_factor", 2.0),
            next_retry_at=row.get("next_retry_at"),
            priority=row.get("priority", 5),
            deadline=row.get("deadline"),
            worker_id=row.get("worker_id", ""),
            estimated_eu=row.get("estimated_eu", 1.0),
            role_id=row.get("role_id", ""),
            task_type=row.get("task_type", ""),
            parent_id=row.get("parent_id", ""),
            metadata=metadata,
        )
