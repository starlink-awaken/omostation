"""Knowledge integration bridge — connects harvest output to knowledge stores.

Extracted core abstractions from SharedBrain D_KnowledgeIntegration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

QUALITY_THRESHOLD = 0.6


@dataclass
class KnowledgeRecord:
    """A single knowledge record with quality scoring."""

    source: str
    content: dict[str, Any]
    quality_score: float = 0.0
    triple_count: int = 0
    validated: bool = False

    def meets_threshold(self) -> bool:
        return self.quality_score >= QUALITY_THRESHOLD

    def validate(self) -> bool:
        """Validate record meets quality and content requirements."""
        if not self.content:
            return False
        if self.quality_score < QUALITY_THRESHOLD:
            return False
        self.validated = True
        return True

    def to_triple(self) -> tuple[str, str, str] | None:
        """Extract (subject, predicate, object) triple from validated record."""
        if not self.validated:
            return None
        subj = self.content.get("entity", self.source)
        pred = self.content.get("relation", "has")
        obj = self.content.get("value", str(self.content))
        return (str(subj), str(pred), str(obj))
