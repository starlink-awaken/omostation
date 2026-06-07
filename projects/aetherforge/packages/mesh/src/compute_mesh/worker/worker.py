"""Mesh Worker — execution slot on a compute node.

A worker represents an execution slot bound to a :class:`ComputeNode`.
Multiple workers can exist on one node (e.g., 4 concurrent slots).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class WorkerStatus(Enum):
    """Operational status of a mesh worker."""

    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class MeshWorker:
    """An execution slot on a compute node.

    Workers are the atomic unit of task execution in the mesh.
    A ``ComputeNode`` with ``max_concurrency=4`` can host 4 workers.
    """

    worker_id: str
    """Unique identifier (e.g. ``"ollama-local-w1"``)."""

    node_id: str
    """The :class:`ComputeNode` this worker belongs to."""

    status: WorkerStatus = WorkerStatus.IDLE
    """Current operational status."""

    current_task: str = ""
    """ID of the task currently being executed, if any."""

    tasks_completed: int = 0
    """Total tasks completed over this worker's lifetime."""

    tasks_failed: int = 0
    """Total tasks that ended in error."""

    current_load: float = 0.0
    """Current load factor (0.0–1.0)."""

    avg_latency_ms: float = 0.0
    """Rolling average latency in milliseconds."""

    created_at: float = 0.0
    """Unix timestamp of creation."""

    last_heartbeat: float = 0.0
    """Unix timestamp of last heartbeat."""

    last_task_end: float = 0.0
    """Unix timestamp of last task completion."""

    tags: dict[str, str] = field(default_factory=dict)
    """Arbitrary key-value tags."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Extensible metadata."""

    def __post_init__(self) -> None:
        now = datetime.now().timestamp()
        if not self.created_at:
            self.created_at = now
        if not self.last_heartbeat:
            self.last_heartbeat = now

    @property
    def is_idle(self) -> bool:
        return self.status == WorkerStatus.IDLE

    @property
    def is_busy(self) -> bool:
        return self.status == WorkerStatus.BUSY

    @property
    def uptime_seconds(self) -> float:
        return datetime.now().timestamp() - self.created_at

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "node_id": self.node_id,
            "status": self.status.value,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "current_load": self.current_load,
            "avg_latency_ms": self.avg_latency_ms,
            "success_rate": self.success_rate,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "last_heartbeat": self.last_heartbeat,
        }
