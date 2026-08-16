"""Intent classification primitives — extracted from SharedBrain D_Intelligence.

Provides complexity level classification for research task routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ComplexityLevel(Enum):
    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"


@dataclass
class ClassificationResult:
    level: ComplexityLevel
    confidence: float = 0.0
    reason: str = ""
    suggested_swarm_size: int = 1

    @property
    def requires_swarm(self) -> bool:
        return self.level == ComplexityLevel.COMPLEX

    @property
    def is_trivial(self) -> bool:
        return self.level == ComplexityLevel.SIMPLE and self.confidence > 0.8


# Heuristic patterns for complexity classification
COMPLEXITY_PATTERNS: dict[ComplexityLevel, list[str]] = {
    ComplexityLevel.SIMPLE: [
        r"\b(read|get|fetch|list|show|display|check)\b",
        r"\b(status|health|ping)\b",
    ],
    ComplexityLevel.MODERATE: [
        r"\b(analyze|search|query|find|compare|evaluate)\b",
        r"\b(generate|create|build|write)\b",
    ],
    ComplexityLevel.COMPLEX: [
        r"\b(deploy|migrate|refactor|restructure)\b",
        r"\b(orchestrate|coordinate|multi.*step|pipeline)\b",
        r"\b(train|fine.*tune|optimize.*model)\b",
    ],
}


def classify_intent(text: str) -> ClassificationResult:
    """Classify intent complexity using heuristic pattern matching."""
    import re

    scores: dict[ComplexityLevel, int] = {level: 0 for level in ComplexityLevel}
    for level, patterns in COMPLEXITY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                scores[level] += 1

    total_hits = sum(scores.values())
    if total_hits == 0:
        return ClassificationResult(level=ComplexityLevel.MODERATE, confidence=0.3, reason="no patterns matched")

    best = max(scores, key=lambda k: scores[k])
    confidence = scores[best] / total_hits
    swarm_size = 1 if best == ComplexityLevel.SIMPLE else (3 if best == ComplexityLevel.MODERATE else 8)

    return ClassificationResult(
        level=best,
        confidence=round(confidence, 2),
        reason=f"matched {scores[best]} patterns",
        suggested_swarm_size=swarm_size,
    )
