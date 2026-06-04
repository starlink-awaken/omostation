"""Refactoring resistance sub-dimension for legacy scoring."""

from __future__ import annotations


def calculate_refactoring_resistance_score(
    dependency_score: float,
    coupling_score: float,
    technical_risk: float,
) -> float:
    """Calculate refactoring resistance score on a 0-10 scale."""
    for name, value in [
        ("dependency_score", dependency_score),
        ("coupling_score", coupling_score),
        ("technical_risk", technical_risk),
    ]:
        if not 0 <= value <= 10:
            raise ValueError(f"{name} must be between 0 and 10, got {value}")

    score = dependency_score * 0.4 + coupling_score * 0.4 + technical_risk * 0.2
    return round(score, 2)
