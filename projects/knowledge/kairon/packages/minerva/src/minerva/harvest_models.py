"""Harvest data models — extracted from SharedBrain D_Harvest."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class HarvestFact:
    subject: str
    predicate: str
    object: str
    source: str = ""
    confidence: float = 1.0
    harvested_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.harvested_at:
            self.harvested_at = datetime.now(UTC).isoformat()

    def as_triple(self) -> tuple[str, str, str]:
        return (self.subject, self.predicate, self.object)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "source": self.source,
            "confidence": self.confidence,
            "harvested_at": self.harvested_at,
        }


@dataclass
class HarvestRecord:
    source_url: str
    facts: list[HarvestFact] = field(default_factory=list)
    operation: str = "harvest"
    duration_ms: float = 0.0

    @property
    def fact_count(self) -> int:
        return len(self.facts)

    def valid_facts(self, min_confidence: float = 0.5) -> list[HarvestFact]:
        return [f for f in self.facts if f.confidence >= min_confidence]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "operation": self.operation,
            "fact_count": self.fact_count,
            "duration_ms": self.duration_ms,
            "facts": [f.to_dict() for f in self.facts],
        }
