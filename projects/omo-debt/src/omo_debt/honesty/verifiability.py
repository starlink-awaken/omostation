"""
Verifiability sub-dimension for honesty scoring.

Measures traceability and evidence support for debt assessments:
1. Evidence completeness: presence of supporting evidence
2. Data traceability: references to commits/issues/docs
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VerifiabilityResult:
    """Verifiability assessment result."""

    score: float  # Overall verifiability score (0-10)
    evidence_score: float  # Evidence completeness sub-score (0-10)
    traceability_score: float  # Data traceability sub-score (0-10)

    # Metadata
    has_impact_evidence: bool
    has_frequency_evidence: bool
    has_cost_evidence: bool
    referenced_commits: int
    referenced_issues: int
    referenced_docs: int
    total_claims: int


def calculate_verifiability(
    has_impact_evidence: bool = False,
    has_frequency_evidence: bool = False,
    has_cost_evidence: bool = False,
    evidence_commits: Optional[list[str]] = None,
    evidence_issues: Optional[list[str]] = None,
    evidence_refs: Optional[list[str]] = None,
    total_claims: int = 1,
) -> VerifiabilityResult:
    """Calculate verifiability score for debt assessment.

    Formula:
        verifiability = 0.60 × evidence + 0.40 × traceability

    Args:
        has_impact_evidence: Impact factor has supporting evidence
        has_frequency_evidence: Frequency factor has supporting evidence
        has_cost_evidence: Cost factor has supporting evidence
        evidence_commits: List of referenced commit SHAs
        evidence_issues: List of referenced issue IDs
        evidence_refs: List of referenced document paths
        total_claims: Total number of claims made in debt description

    Returns:
        VerifiabilityResult object

    Examples:
        >>> result = calculate_verifiability(
        ...     has_impact_evidence=True,
        ...     has_frequency_evidence=True,
        ...     evidence_commits=["abc123", "def456"],
        ...     evidence_issues=["#42"],
        ...     total_claims=3
        ... )
        >>> result.score
        7.33
    """
    # Default to empty lists if None
    evidence_commits = evidence_commits or []
    evidence_issues = evidence_issues or []
    evidence_refs = evidence_refs or []

    # 1. Calculate evidence completeness score
    evidence_count = sum(
        [
            has_impact_evidence,
            has_frequency_evidence,
            has_cost_evidence,
        ]
    )

    if evidence_count >= 3:
        evidence_score = 10.0
    elif evidence_count == 2:
        evidence_score = 6.0
    elif evidence_count == 1:
        evidence_score = 3.0
    else:
        evidence_score = 0.0

    # 2. Calculate traceability score
    total_references = len(evidence_commits) + len(evidence_issues) + len(evidence_refs)

    if total_claims > 0:
        trace_ratio = total_references / total_claims
        trace_score = min(10.0, trace_ratio * 10)
    else:
        trace_score = 0.0  # No claims = no traceability

    # 3. Calculate weighted verifiability score
    verifiability_score = round(0.60 * evidence_score + 0.40 * trace_score, 2)

    return VerifiabilityResult(
        score=verifiability_score,
        evidence_score=evidence_score,
        traceability_score=round(trace_score, 2),
        has_impact_evidence=has_impact_evidence,
        has_frequency_evidence=has_frequency_evidence,
        has_cost_evidence=has_cost_evidence,
        referenced_commits=len(evidence_commits),
        referenced_issues=len(evidence_issues),
        referenced_docs=len(evidence_refs),
        total_claims=total_claims,
    )


# Helper functions for evidence detection


def detect_impact_evidence(description: str, evidence_refs: list[str]) -> bool:
    """Detect if impact factor has supporting evidence.

    Evidence indicators:
    - Code file references
    - User feedback/bug reports
    - Performance metrics

    Args:
        description: Debt item description
        evidence_refs: List of referenced documents/files

    Returns:
        True if impact evidence found
    """
    # Check for code references
    if any(ref.endswith((".py", ".js", ".ts", ".java", ".go")) for ref in evidence_refs):
        return True

    # Check for evidence keywords in description
    evidence_keywords = [
        "error",
        "bug",
        "crash",
        "fail",
        "issue",
        "user report",
        "performance",
        "slow",
        "latency",
        "memory",
        "cpu",
        "security",
        "vulnerability",
        "exploit",
    ]

    desc_lower = description.lower()
    return any(keyword in desc_lower for keyword in evidence_keywords)


def detect_frequency_evidence(description: str, evidence_commits: list[str], evidence_refs: list[str]) -> bool:
    """Detect if frequency factor has supporting evidence.

    Evidence indicators:
    - Git commit statistics
    - Log frequency data
    - Monitoring metrics

    Args:
        description: Debt item description
        evidence_commits: List of referenced commits
        evidence_refs: List of referenced documents

    Returns:
        True if frequency evidence found
    """
    # Check for multiple commit references (frequency proxy)
    if len(evidence_commits) >= 2:
        return True

    # Check for frequency keywords
    frequency_keywords = [
        "every",
        "daily",
        "weekly",
        "often",
        "frequently",
        "repeatedly",
        "times",
        "occurrences",
        "hits",
        "log",
        "metric",
        "monitor",
        "stat",
    ]

    desc_lower = description.lower()
    return any(keyword in desc_lower for keyword in frequency_keywords)


def detect_cost_evidence(description: str, evidence_refs: list[str]) -> bool:
    """Detect if cost factor has supporting evidence.

    Evidence indicators:
    - Time estimates
    - Similar case references
    - Complexity analysis

    Args:
        description: Debt item description
        evidence_refs: List of referenced documents

    Returns:
        True if cost evidence found
    """
    # Check for estimation keywords (stricter matching)
    cost_keywords = [
        "hour",
        "day",
        "week",
        "month",
        "estimate",
        "effort",
        "similar",
        "previous",
        "last time",
        "complexity",
        "difficult",
        "risky",
    ]

    desc_lower = description.lower()
    # Exclude generic "work" keyword to avoid false positives
    return any(keyword in desc_lower for keyword in cost_keywords)


def count_claims(description: str) -> int:
    """Count total claims made in debt description.

    Heuristic: count sentences with assertion keywords.

    Args:
        description: Debt item description

    Returns:
        Number of claims (minimum 1)
    """
    # Simple heuristic: count sentences
    sentences = [s.strip() for s in description.split(".") if s.strip()]

    # Count sentences with assertion keywords
    assertion_keywords = ["is", "are", "will", "cause", "lead", "result", "require"]

    claim_count = 0
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in assertion_keywords):
            claim_count += 1

    # At least 1 claim (the debt itself)
    return max(1, claim_count)
