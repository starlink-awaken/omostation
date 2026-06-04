"""Legacy (L) dimension for 4P3V1L1H framework."""

from omo_debt.legacy.age import calculate_age_score
from omo_debt.legacy.core import adjust_score_with_legacy, calculate_legacy_score
from omo_debt.legacy.migration import calculate_migration_path_score
from omo_debt.legacy.resistance import calculate_refactoring_resistance_score

__all__ = [
    "calculate_age_score",
    "calculate_refactoring_resistance_score",
    "calculate_migration_path_score",
    "calculate_legacy_score",
    "adjust_score_with_legacy",
]
