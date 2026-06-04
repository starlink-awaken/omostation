"""
Core honesty score calculation module.

Implements Pattern 09 v2.1 honesty dimension.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class HonestyScore:
    """Honesty score result."""

    score: float  # Overall honesty score (0-10)
    completeness: float  # Completeness sub-score (0-10)
    consistency: float  # Consistency sub-score (0-10)
    verifiability: float  # Verifiability sub-score (0-10)
    assessed_at: str  # ISO timestamp

    # Evidence references
    evidence_commits: list[str] = None
    evidence_issues: list[str] = None
    evidence_refs: list[str] = None

    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.evidence_commits is None:
            self.evidence_commits = []
        if self.evidence_issues is None:
            self.evidence_issues = []
        if self.evidence_refs is None:
            self.evidence_refs = []

    @property
    def bonus(self) -> float:
        """Calculate priority bonus/penalty based on honesty score.

        Returns:
            float: Bonus multiplier (-0.25 to +0.25)
            - honesty=10 → +0.25 (25% boost)
            - honesty=5  → 0.00 (no change)
            - honesty=0  → -0.25 (25% penalty)
        """
        return (self.score - 5.0) / 20.0

    @property
    def grade(self) -> str:
        """Classify honesty grade.

        Returns:
            str: Grade (优秀/良好/一般/较差/危险)
        """
        if self.score >= 8.5:
            return "优秀"
        elif self.score >= 7.0:
            return "良好"
        elif self.score >= 5.0:
            return "一般"
        elif self.score >= 3.0:
            return "较差"
        else:
            return "危险"


def calculate_honesty_score(
    completeness: float,
    consistency: float,
    verifiability: float,
    assessed_at: Optional[str] = None,
    evidence_commits: Optional[list[str]] = None,
    evidence_issues: Optional[list[str]] = None,
    evidence_refs: Optional[list[str]] = None,
) -> HonestyScore:
    """Calculate overall honesty score from sub-dimensions.

    Formula:
        honesty = 0.40 × completeness + 0.35 × consistency + 0.25 × verifiability

    Args:
        completeness: Completeness score (0-10)
        consistency: Consistency score (0-10)
        verifiability: Verifiability score (0-10)
        assessed_at: ISO timestamp (default: current time)
        evidence_commits: List of commit references
        evidence_issues: List of issue references
        evidence_refs: List of document references

    Returns:
        HonestyScore object

    Raises:
        ValueError: If any score is out of range [0, 10]
    """
    # Validate inputs
    for name, score in [
        ("completeness", completeness),
        ("consistency", consistency),
        ("verifiability", verifiability),
    ]:
        if not 0 <= score <= 10:
            raise ValueError(f"{name} must be between 0 and 10, got {score}")

    # Calculate weighted sum
    overall_score = round(0.40 * completeness + 0.35 * consistency + 0.25 * verifiability, 2)

    # Default timestamp if not provided
    if assessed_at is None:
        from datetime import datetime, timezone

        assessed_at = datetime.now(timezone.utc).isoformat()

    return HonestyScore(
        score=overall_score,
        completeness=completeness,
        consistency=consistency,
        verifiability=verifiability,
        assessed_at=assessed_at,
        evidence_commits=evidence_commits or [],
        evidence_issues=evidence_issues or [],
        evidence_refs=evidence_refs or [],
    )


def adjust_score_with_honesty(base_score: float, honesty_score: float) -> float:
    """Adjust base debt score with honesty bonus/penalty.

    Pattern 09 v2.1 formula:
        adjusted_score = base_score × (1 + honesty_bonus)
        where honesty_bonus = (honesty_score - 5) / 20

    Args:
        base_score: Original debt score
        honesty_score: Honesty dimension score (0-10)

    Returns:
        float: Adjusted score

    Examples:
        >>> adjust_score_with_honesty(8.0, 10.0)  # Perfect honesty
        10.0  # 8.0 × 1.25 = 10.0

        >>> adjust_score_with_honesty(8.0, 5.0)  # Average honesty
        8.0  # 8.0 × 1.0 = 8.0

        >>> adjust_score_with_honesty(8.0, 0.0)  # Poor honesty
        6.0  # 8.0 × 0.75 = 6.0
    """
    bonus = (honesty_score - 5.0) / 20.0
    adjusted = round(base_score * (1.0 + bonus), 2)
    return adjusted
