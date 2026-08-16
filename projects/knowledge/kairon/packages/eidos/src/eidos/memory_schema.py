"""Memory schema models — extracted from SharedBrain D_Memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryRecord:
    record_id: str
    content: str
    memory_type: str = "fact"
    confidence: float = 1.0
    source: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "source": self.source,
            "tags": self.tags,
        }


@dataclass
class MemorySession:
    session_id: str
    records: list[MemoryRecord] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def record_count(self) -> int:
        return len(self.records)

    def add_record(self, record: MemoryRecord) -> None:
        self.records.append(record)

    def valid_records(self, min_confidence: float = 0.5) -> list[MemoryRecord]:
        return [r for r in self.records if r.confidence >= min_confidence]
