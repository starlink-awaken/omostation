"""Task context management for D_Execution."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .role_message import MessagePriority, MessageType


@dataclass
class TaskContext:
    """Context wrapper around a task payload, providing metadata and
    lifecycle tracking.

    Attaches routing information, priority, and execution state to a raw
    task payload so that downstream components (workers, schedulers,
    auctioneers) can inspect provenance and priority without modifying the
    original message.
    """

    task_id: str
    content: dict[str, Any]
    source: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    message_type: MessageType = MessageType.REQUEST
    created_at: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age(self) -> float:
        """Seconds since this context was created."""
        return time.time() - self.created_at

    def enrich(self, **kwargs: Any) -> None:
        """Add or update context fields from keyword arguments."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_payload(self) -> dict[str, Any]:
        """Extract the inner task payload without context metadata."""
        return self.content

    def to_dict(self) -> dict[str, Any]:
        """Full serialization including metadata."""
        return {
            "task_id": self.task_id,
            "content": self.content,
            "source": self.source,
            "priority": self.priority.name,
            "message_type": self.message_type.name,
            "created_at": self.created_at,
            "tags": self.tags,
            "metadata": self.metadata,
        }
