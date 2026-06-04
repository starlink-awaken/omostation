"""Migration-path sub-dimension for legacy scoring."""

from __future__ import annotations


def calculate_migration_path_score(
    solution_clarity: float,
    incremental: bool,
    has_migration_docs: bool,
) -> float:
    """Calculate migration-path score on a 0-10 scale."""
    if not 0 <= solution_clarity <= 10:
        raise ValueError(f"solution_clarity must be between 0 and 10, got {solution_clarity}")

    incremental_score = 8.0 if incremental else 4.0
    docs_score = 8.0 if has_migration_docs else 4.0

    score = solution_clarity * 0.5 + incremental_score * 0.3 + docs_score * 0.2
    return round(score, 2)
