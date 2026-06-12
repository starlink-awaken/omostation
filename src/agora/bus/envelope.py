"""BusEnvelope — wire-format envelope for all bus events.

Phase A.0: extend agora/core/event_bus.py:124-131 envelope with schema_version.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    PIPELINE_COMPLETED = "pipeline:completed"
    PIPELINE_STARTED = "pipeline:started"
    MESSAGE_RECEIVED = "message:received"


class BusEnvelope:
    def __init__(
        self,
        type: str | EventType,
        source: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
        schema_version: int = 1,
        id: str | None = None,
        time: str | None = None,
    ):
        if isinstance(type, EventType):
            type = type.value
        # 用 datetime.now() 拿 epoch, 避免 `time` 模块名与 self.time 字段冲突
        epoch = int(datetime.now(UTC).timestamp())
        self.id = id or f"evt_{epoch}_{uuid.uuid4().hex[:6]}"
        self.time = time or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.type = type
        self.source = source
        self.schema_version = schema_version
        self.trace_id = trace_id
        self.payload = payload or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "time": self.time,
            "type": self.type,
            "source": self.source,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BusEnvelope":
        return cls(
            id=d.get("id"),
            time=d.get("time"),
            type=d["type"],
            source=d["source"],
            schema_version=d.get("schema_version", 1),
            trace_id=d.get("trace_id"),
            payload=d.get("payload", {}),
        )

    @classmethod
    def from_json(cls, s: str) -> "BusEnvelope":
        return cls.from_dict(json.loads(s))

    def __repr__(self) -> str:
        return f"BusEnvelope(id={self.id!r}, type={self.type!r}, source={self.source!r})"
