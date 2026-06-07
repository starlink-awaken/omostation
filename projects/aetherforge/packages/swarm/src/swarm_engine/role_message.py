from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    ERROR = "error"


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class RoleMessage:
    """Standard message format for role communication."""

    message_id: str
    sender_role_id: str
    target_role_id: str | None  # None for broadcast
    type: MessageType
    content: Any
    created_at: float
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        sender_id: str,
        content: Any,
        target_id: str | None = None,
        msg_type: MessageType = MessageType.REQUEST,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RoleMessage:
        return cls(
            message_id=str(uuid.uuid4()),
            sender_role_id=sender_id,
            target_role_id=target_id,
            type=msg_type,
            content=content,
            created_at=datetime.now().timestamp(),
            priority=priority,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "id": self.message_id,
                "sender": self.sender_role_id,
                "target": self.target_role_id,
                "type": self.type.value,
                "content": self.content,
                "ts": self.created_at,
                "prio": self.priority.value,
                "corr_id": self.correlation_id,
                "meta": self.metadata,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> RoleMessage:
        data = json.loads(json_str)
        return cls(
            message_id=data["id"],
            sender_role_id=data["sender"],
            target_role_id=data.get("target"),
            type=MessageType(data["type"]),
            content=data["content"],
            created_at=data["ts"],
            priority=MessagePriority(data.get("prio", 1)),
            correlation_id=data.get("corr_id"),
            metadata=data.get("meta", {}),
        )
