"""Type definitions for IntentClassifier (ARCH-003 SRP refactor).

Extracted from intent_classifier.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ComplexityLevel(Enum):
    """Intent complexity tier used to drive execution routing."""

    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"


@dataclass
class ClassificationResult:
    """Full classification output returned by IntentClassifier.classify()."""

    level: ComplexityLevel
    confidence: float  # 0.0 – 1.0
    rationale: str  # Human-readable explanation
    suggested_swarm_size: int  # 1 – 8 parallel workers
    suggested_roles: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.level.value} (confidence: {self.confidence:.2f}) — {self.rationale}"
