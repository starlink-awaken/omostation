"""Core legacy score calculation module."""

from __future__ import annotations


def calculate_legacy_score(age_score: float, resistance_score: float, path_score: float) -> float:
    """Calculate overall legacy score from sub-dimensions."""
    for name, score in [
        ("age_score", age_score),
        ("resistance_score", resistance_score),
        ("path_score", path_score),
    ]:
        if not 0 <= score <= 10:
            raise ValueError(f"{name} must be between 0 and 10, got {score}")

    return round(age_score * 0.4 + resistance_score * 0.35 + path_score * 0.25, 2)


def adjust_score_with_legacy(base_score: float, legacy_score: float) -> float:
    """Adjust base priority score with legacy modifier."""
    if not 0 <= base_score <= 100:
        raise ValueError(f"base_priority must be between 0 and 100, got {base_score}")

    if legacy_score >= 8.0:
        adjusted = base_score * 1.15
    elif legacy_score <= 4.0:
        adjusted = base_score * 0.9
    else:
        adjusted = base_score
    adjusted = max(0.0, min(adjusted, 100.0))
    return round(adjusted, 2)
