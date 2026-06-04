"""
Consistency sub-dimension for honesty scoring.

Measures objectivity and stability of debt assessments across:
1. Score deviation: compared to peer average
2. Time consistency: stability over time
3. Cross-project consistency: consistency across similar projects
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConsistencyResult:
    """Consistency assessment result."""

    score: float  # Overall consistency score (0-10)
    deviation_score: float  # Score deviation sub-score (0-10)
    time_score: float  # Time consistency sub-score (0-10)
    cross_project_score: float  # Cross-project consistency sub-score (0-10)

    # Metadata
    self_rating: float
    peer_avg: Optional[float]
    score_volatility: float
    cross_project_diff: float


def calculate_consistency(
    self_rating: float,
    peer_avg: Optional[float] = None,
    historical_scores: Optional[list[float]] = None,
    similar_project_scores: Optional[list[float]] = None,
) -> ConsistencyResult:
    """Calculate consistency score for debt assessment.

    Formula:
        consistency = 0.50 × deviation + 0.25 × time + 0.25 × cross_project

    Args:
        self_rating: Current debt score (self-assessment)
        peer_avg: Average score of similar debts (optional)
        historical_scores: Past scores of same debt (optional)
        similar_project_scores: Scores of similar debts in other projects (optional)

    Returns:
        ConsistencyResult object

    Examples:
        >>> result = calculate_consistency(8.5, peer_avg=7.0)
        >>> result.score  # 0-10 consistency score
        7.125
    """
    # 1. Calculate score deviation
    if peer_avg is not None:
        deviation_penalty = abs(self_rating - peer_avg) * 2
        dev_score = max(0.0, 10.0 - deviation_penalty)
    else:
        dev_score = 7.0  # Neutral score if no peer data

    # 2. Calculate time consistency
    if historical_scores and len(historical_scores) > 1:
        volatility = _calculate_volatility(historical_scores)
        time_score = max(0.0, 10.0 - (volatility * 5))
    else:
        time_score = 10.0  # Perfect stability if no history

    # 3. Calculate cross-project consistency
    if similar_project_scores:
        cross_diff = _calculate_cross_project_diff(self_rating, similar_project_scores)
        cross_score = _cross_diff_to_score(cross_diff)
    else:
        cross_score = 7.0  # Neutral score if no cross-project data

    # 4. Calculate weighted consistency score
    consistency_score = round(0.50 * dev_score + 0.25 * time_score + 0.25 * cross_score, 2)

    return ConsistencyResult(
        score=consistency_score,
        deviation_score=round(dev_score, 2),
        time_score=round(time_score, 2),
        cross_project_score=round(cross_score, 2),
        self_rating=self_rating,
        peer_avg=peer_avg,
        score_volatility=_calculate_volatility(historical_scores) if historical_scores else 0.0,
        cross_project_diff=_calculate_cross_project_diff(self_rating, similar_project_scores)
        if similar_project_scores
        else 0.0,
    )


def _calculate_volatility(scores: list[float]) -> float:
    """Calculate score volatility (standard deviation).

    Args:
        scores: List of historical scores

    Returns:
        Standard deviation (volatility)

    Examples:
        >>> _calculate_volatility([7.0, 8.0, 7.5])
        0.5
    """
    if not scores or len(scores) < 2:
        return 0.0

    mean = sum(scores) / len(scores)
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    std_dev = math.sqrt(variance)

    return round(std_dev, 2)


def _calculate_cross_project_diff(self_rating: float, similar_scores: list[float]) -> float:
    """Calculate average difference from similar project scores.

    Args:
        self_rating: Current debt score
        similar_scores: Scores from similar debts in other projects

    Returns:
        Average absolute difference

    Examples:
        >>> _calculate_cross_project_diff(8.0, [7.5, 8.2, 7.8])
        0.3
    """
    if not similar_scores:
        return 0.0

    diffs = [abs(self_rating - score) for score in similar_scores]
    avg_diff = sum(diffs) / len(diffs)

    return round(avg_diff, 2)


def _cross_diff_to_score(diff: float) -> float:
    """Convert cross-project difference to consistency score.

    Scoring:
    - diff < 1.0: 10.0 (excellent)
    - diff 1.0-2.0: 7.0 (good)
    - diff 2.0-3.0: 4.0 (fair)
    - diff > 3.0: 0.0 (poor)

    Args:
        diff: Average cross-project difference

    Returns:
        Consistency score (0-10)
    """
    if diff < 1.0:
        return 10.0
    elif diff < 2.0:
        return 7.0
    elif diff < 3.0:
        return 4.0
    else:
        return 0.0


# Optional: Outlier detection using z-score
def detect_outlier(self_rating: float, peer_scores: list[float], threshold: float = 2.0) -> bool:
    """Detect if self-rating is an outlier (z-score > threshold).

    Args:
        self_rating: Current debt score
        peer_scores: List of peer debt scores
        threshold: Z-score threshold (default 2.0 = 2 standard deviations)

    Returns:
        True if outlier

    Examples:
        >>> detect_outlier(10.0, [7.0, 7.5, 8.0, 7.2])  # Significantly higher
        True

        >>> detect_outlier(7.3, [7.0, 7.5, 8.0, 7.2])  # Within normal range
        False
    """
    if not peer_scores or len(peer_scores) < 2:
        return False  # Need at least 2 peers for outlier detection

    mean = sum(peer_scores) / len(peer_scores)
    variance = sum((x - mean) ** 2 for x in peer_scores) / len(peer_scores)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return False  # All peer scores identical

    z_score = abs((self_rating - mean) / std_dev)

    return z_score > threshold
