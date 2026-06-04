"""Technical debt scoring module.

Implements Pattern 09 v2.0 stage-aware debt scoring algorithm.
"""

from __future__ import annotations

from typing import Literal

from omo_debt.core.stage import StageType, get_normalization_factor, get_stage_weights

PriorityType = Literal["P0", "P1", "P2"]


class DebtScore:
    """Technical debt score result."""

    def __init__(
        self,
        impact: int,
        frequency: int,
        cost: int,
        stage: StageType,
        base_score: float,
        normalized_score: float,
        priority: PriorityType,
        weights: tuple[float, float, float],
        normalization_factor: float,
    ):
        self.impact = impact
        self.frequency = frequency
        self.cost = cost
        self.stage = stage
        self.base_score = base_score
        self.normalized_score = normalized_score
        self.priority = priority
        self.weights = weights
        self.normalization_factor = normalization_factor

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        w_impact, w_freq, w_cost = self.weights
        return {
            "debt_item": {
                "impact": self.impact,
                "frequency": self.frequency,
                "cost": self.cost,
            },
            "project_stage": self.stage,
            "weights": {
                "impact": w_impact,
                "frequency": w_freq,
                "cost": w_cost,
            },
            "normalization_factor": self.normalization_factor,
            "calculation": {
                "base_score": round(self.base_score, 2),
                "normalized_score": round(self.normalized_score, 2),
                "priority": self.priority,
            },
            "recommendation": self._get_recommendation(),
        }

    def _get_recommendation(self) -> str:
        """Get priority-based recommendation."""
        if self.priority == "P0":
            return "高优先级债务，建议在本周期内修复"
        elif self.priority == "P1":
            return "中等优先级债务，建议在近期修复"
        else:
            return "低优先级债务，可根据资源情况安排修复"


def calculate_score_v2(
    impact: int,
    frequency: int,
    cost: int,
    stage: StageType,
) -> DebtScore:
    """
    Calculate technical debt score using Pattern 09 v2.0 algorithm.

    Algorithm:
        1. Get stage-specific weights (impact, frequency, cost)
        2. Calculate base score: impact*w_i + frequency*w_f + cost*w_c
        3. Apply normalization factor (stability premium)
        4. Determine priority: P0 (≥7.0), P1 (5.0-6.9), P2 (<5.0)

    Args:
        impact: Impact score (1-10)
        frequency: Frequency score (1-10)
        cost: Cost score (1-10)
        stage: Project lifecycle stage

    Returns:
        DebtScore: Scoring result with all metadata

    Raises:
        ValueError: If any score is not in range [1, 10]

    Example:
        >>> score = calculate_score_v2(impact=9, frequency=8, cost=7, stage="rapid_evolution")
        >>> print(f"Score: {score.normalized_score:.2f}, Priority: {score.priority}")
        Score: 8.05, Priority: P0
    """
    # Validate inputs
    for name, value in [("impact", impact), ("frequency", frequency), ("cost", cost)]:
        if not 1 <= value <= 10:
            raise ValueError(f"{name} must be in range [1, 10], got {value}")

    # Get stage-specific parameters
    w_impact, w_freq, w_cost = get_stage_weights(stage)
    norm_factor = get_normalization_factor(stage)

    # Calculate base score (round to 2 decimals to match expected precision)
    base_score = round(impact * w_impact + frequency * w_freq + cost * w_cost, 2)

    # Apply normalization (round to 2 decimals)
    normalized_score = round(base_score * norm_factor, 2)

    # Determine priority
    priority: PriorityType
    if normalized_score >= 7.0:
        priority = "P0"
    elif normalized_score >= 5.0:
        priority = "P1"
    else:
        priority = "P2"

    return DebtScore(
        impact=impact,
        frequency=frequency,
        cost=cost,
        stage=stage,
        base_score=base_score,
        normalized_score=normalized_score,
        priority=priority,
        weights=(w_impact, w_freq, w_cost),
        normalization_factor=norm_factor,
    )


def compare_debt_scores(scores: list[DebtScore]) -> list[DebtScore]:
    """
    Compare and sort debt scores by normalized_score (descending).

    Args:
        scores: List of DebtScore objects

    Returns:
        List of DebtScore objects sorted by priority (P0 > P1 > P2) then by normalized_score

    Example:
        >>> scores = [score1, score2, score3]
        >>> sorted_scores = compare_debt_scores(scores)
        >>> for s in sorted_scores:
        ...     print(f"{s.priority}: {s.normalized_score:.2f}")
        P0: 8.05
        P1: 5.70
        P1: 5.15
    """
    # Define priority order
    priority_order = {"P0": 0, "P1": 1, "P2": 2}

    # Sort by priority first, then by normalized_score (descending)
    return sorted(
        scores,
        key=lambda s: (priority_order[s.priority], -s.normalized_score),
    )
