"""
omo-debt honesty dimension module

Implements the Honesty (H) dimension for 4P3V1L1H framework integration.

Sub-dimensions:
- Completeness: Coverage of technical debt disclosure
- Consistency: Objectivity and accuracy of assessments
- Verifiability: Traceability and evidence support
"""

from omo_debt.honesty.completeness import calculate_completeness
from omo_debt.honesty.consistency import calculate_consistency
from omo_debt.honesty.core import calculate_honesty_score
from omo_debt.honesty.verifiability import calculate_verifiability

__all__ = [
    "calculate_completeness",
    "calculate_consistency",
    "calculate_verifiability",
    "calculate_honesty_score",
]
