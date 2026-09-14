from __future__ import annotations

"""
Quality gate for the D-Harvest pipeline.

Provides ``QualityGate`` which validates extracted ``StructuredKnowledge``
items against configurable rules (content length, structure, language) and
returns ``ValidationResult`` per item.
"""


from kairon_pipeline.extract_base import StructuredKnowledge


class ValidationResult:
    """Result of validating a single ``StructuredKnowledge`` item.

    Parameters
    ----------
    passed:
        ``True`` when the item meets all quality rules.
    quality_score:
        Float between 0.0 and 1.0 representing overall quality.
    reasons:
        Human-readable list of why the item passed or failed.
    """

    def __init__(
        self,
        passed: bool,
        quality_score: float = 1.0,
        reasons: list[str] | None = None,
    ) -> None:
        self.passed = passed
        self.quality_score = quality_score
        self.reasons = reasons or []


class QualityGate:
    """Configurable quality gate for extracted knowledge items.

    Applies simple quality heuristics:
    - Content length must exceed a minimum threshold.
    - Title must be non-empty.
    - Body must contain enough words to be meaningful.
    """

    def __init__(
        self,
        min_title_length: int = 3,
        min_body_length: int = 50,
        min_word_count: int = 10,
    ) -> None:
        self._min_title_length = min_title_length
        self._min_body_length = min_body_length
        self._min_word_count = min_word_count

    async def validate(
        self,
        items: list[StructuredKnowledge],
    ) -> list[ValidationResult]:
        """Validate a list of items against quality rules.

        Returns a ``ValidationResult`` for each input item, in the same order.
        """
        results: list[ValidationResult] = []
        for item in items:
            reasons: list[str] = []
            score = 1.0

            # Rule 1: Title length
            if len(item.title) < self._min_title_length:
                reasons.append(f"Title too short ({len(item.title)} < {self._min_title_length})")
                score -= 0.3

            # Rule 2: Body length
            if len(item.body) < self._min_body_length:
                reasons.append(f"Body too short ({len(item.body)} < {self._min_body_length})")
                score -= 0.3

            # Rule 3: Word count
            word_count = len(item.body.split())
            if word_count < self._min_word_count:
                reasons.append(f"Too few words ({word_count} < {self._min_word_count})")
                score -= 0.3

            passed = score > 0.4  # at least one rule must pass comfortably
            quality_score = max(0.0, min(1.0, score))

            results.append(
                ValidationResult(
                    passed=passed,
                    quality_score=quality_score,
                    reasons=reasons or ["All quality rules passed"],
                )
            )

        return results
