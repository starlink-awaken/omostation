"""Age sub-dimension for legacy scoring."""

from __future__ import annotations


def calculate_age_score(age_months: int, stable_months: int) -> float:
    """Calculate age score on a 0-10 scale."""
    if age_months < 0:
        raise ValueError(f"age_months must be >= 0, got {age_months}")
    if stable_months < 0:
        raise ValueError(f"stable_months must be >= 0, got {stable_months}")

    if age_months <= 3:
        base_score = 9.5
    elif age_months <= 12:
        base_score = 8.0
    elif age_months <= 36:
        base_score = 6.0
    else:
        base_score = 4.0

    if stable_months > 12:
        base_score -= 1.0

    return max(0.0, min(round(base_score, 2), 10.0))
