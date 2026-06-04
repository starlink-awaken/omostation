"""Project lifecycle stage identification module.

Implements Pattern 09 v2.0 stage identification algorithm based on Git commit history.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

StageType = Literal["rapid_evolution", "stable_growth", "maintenance"]
ConfidenceType = Literal["high", "medium", "low"]


class StageInfo:
    """Project stage identification result."""

    def __init__(
        self,
        monthly_avg: float,
        stage: StageType,
        confidence: ConfidenceType,
        total_commits: int,
        months_analyzed: int,
    ):
        self.monthly_avg = monthly_avg
        self.stage = stage
        self.confidence = confidence
        self.total_commits = total_commits
        self.months_analyzed = months_analyzed

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "monthly_avg": self.monthly_avg,
            "stage": self.stage,
            "confidence": self.confidence,
            "total_commits": self.total_commits,
            "months_analyzed": self.months_analyzed,
            "threshold": self._get_threshold_description(),
            "recommendation": self._get_recommendation(),
        }

    def _get_threshold_description(self) -> str:
        """Get human-readable threshold description."""
        if self.stage == "rapid_evolution":
            return ">30 commits/month"
        elif self.stage == "stable_growth":
            return "10-30 commits/month"
        else:
            return "<10 commits/month"

    def _get_recommendation(self) -> str:
        """Get weight recommendation based on stage."""
        weights = {
            "rapid_evolution": "使用权重 0.35/0.40/0.25（频繁优先），归一化系数 1.0",
            "stable_growth": "使用权重 0.40/0.30/0.30（平衡发展），归一化系数 1.1",
            "maintenance": "使用权重 0.50/0.20/0.30（影响优先），归一化系数 1.2",
        }
        return weights[self.stage]


def identify_project_stage(
    repo_path: str | Path,
    months: int = 6,
) -> StageInfo:
    """
    Identify project lifecycle stage based on Git commit history.

    Algorithm:
        1. Analyze commit history over the last N months (default: 6)
        2. Calculate monthly average commit count
        3. Determine stage:
           - Rapid evolution: >30 commits/month
           - Stable growth: 10-30 commits/month
           - Maintenance: <10 commits/month
        4. Calculate confidence level based on boundary proximity

    Args:
        repo_path: Path to Git repository
        months: Number of months to analyze (default: 6)

    Returns:
        StageInfo: Stage identification result with metadata

    Raises:
        InvalidGitRepositoryError: If path is not a valid Git repository
        ValueError: If months < 1

    Example:
        >>> stage_info = identify_project_stage("/path/to/gbrain", months=6)
        >>> print(f"Stage: {stage_info.stage}, Monthly avg: {stage_info.monthly_avg:.1f}")
        Stage: rapid_evolution, Monthly avg: 37.3
    """
    if months < 1:
        raise ValueError(f"months must be >= 1, got {months}")

    repo_path = Path(repo_path)
    if not repo_path.exists():
        raise FileNotFoundError(f"Path does not exist: {repo_path}")

    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError as e:
        raise InvalidGitRepositoryError(f"Not a valid Git repository: {repo_path}") from e

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)  # Approximate month = 30 days

    # Get commits in date range
    try:
        commits = list(repo.iter_commits(since=start_date.isoformat(), until=end_date.isoformat()))
    except GitCommandError:
        # Handle empty repository or no commits in range
        commits = []

    total_commits = len(commits)
    monthly_avg = total_commits / months

    # Determine stage
    if monthly_avg > 30:
        stage: StageType = "rapid_evolution"
    elif monthly_avg >= 10:
        stage = "stable_growth"
    else:
        stage = "maintenance"

    # Calculate confidence
    # Medium confidence if monthly_avg is near boundaries (±3 commits)
    confidence: ConfidenceType
    if 27 <= monthly_avg <= 33 or 7 <= monthly_avg <= 13:
        confidence = "medium"
    elif total_commits < 10:  # Very few commits, low confidence
        confidence = "low"
    else:
        confidence = "high"

    return StageInfo(
        monthly_avg=monthly_avg,
        stage=stage,
        confidence=confidence,
        total_commits=total_commits,
        months_analyzed=months,
    )


def get_stage_weights(stage: StageType) -> tuple[float, float, float]:
    """
    Get dynamic weights for a given project stage.

    Args:
        stage: Project lifecycle stage

    Returns:
        Tuple of (impact_weight, frequency_weight, cost_weight)

    Example:
        >>> w_impact, w_freq, w_cost = get_stage_weights("rapid_evolution")
        >>> print(f"Impact: {w_impact}, Frequency: {w_freq}, Cost: {w_cost}")
        Impact: 0.35, Frequency: 0.40, Cost: 0.25
    """
    weights = {
        "rapid_evolution": (0.35, 0.40, 0.25),
        "stable_growth": (0.40, 0.30, 0.30),
        "maintenance": (0.50, 0.20, 0.30),
    }
    return weights[stage]


def get_normalization_factor(stage: StageType) -> float:
    """
    Get normalization factor for a given project stage.

    Args:
        stage: Project lifecycle stage

    Returns:
        Normalization factor (1.0 for rapid evolution, 1.1 for stable growth, 1.2 for maintenance)

    Example:
        >>> factor = get_normalization_factor("stable_growth")
        >>> print(f"Normalization: {factor}")
        Normalization: 1.1
    """
    factors = {
        "rapid_evolution": 1.0,
        "stable_growth": 1.1,
        "maintenance": 1.2,
    }
    return factors[stage]
