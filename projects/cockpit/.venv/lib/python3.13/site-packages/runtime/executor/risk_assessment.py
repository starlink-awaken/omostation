"""Risk assessment and DF-CEA decision path selection for PhaseStateMachine.

Migrated from agentmesh state-machine.ts (assessRisk, selectDecisionPath).

Provides risk heuristics and decision path mapping to be used by
PhaseStateMachine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from runtime.executor.state_machine import DecisionPath, RiskLevel

# ====================================================================
# Risk assessment context
# ====================================================================


@dataclass
class RiskAssessmentContext:
    """Context for risk assessment heuristics."""
    description: str = ""
    goals: list[str] = field(default_factory=list)
    complexity: str = "standard"
    constraints: list[str] = field(default_factory=list)
    file_count: int | None = None
    has_security_scope: bool = False
    has_infrastructure_scope: bool = False


# ====================================================================
# Constants
# ====================================================================

SECURITY_KEYWORDS = [
    "security", "auth", "payment", "encrypt", "credential", "token", "secret",
    "permission", "rbac", "oauth", "certificate", "ssl", "tls", "firewall",
    "vulnerability", "compliance", "gdpr", "hipaa", "pci",
]

INFRA_KEYWORDS = [
    "database", "migration", "deploy", "production", "infrastructure",
    "kubernetes", "scaling", "cluster", "replication", "failover", "dns",
    "load-balancer", "cdn",
]

RISK_LEVELS: list[RiskLevel] = [
    RiskLevel.VERY_LOW, RiskLevel.LOW, RiskLevel.MEDIUM,
    RiskLevel.HIGH, RiskLevel.CRITICAL,
]

RISK_TO_PATH: dict[RiskLevel, DecisionPath] = {
    RiskLevel.VERY_LOW: DecisionPath.EXPRESS,
    RiskLevel.LOW: DecisionPath.QUICK,
    RiskLevel.MEDIUM: DecisionPath.STANDARD,
    RiskLevel.HIGH: DecisionPath.DEEP,
    RiskLevel.CRITICAL: DecisionPath.FULL,
}


# ====================================================================
# Assessment functions
# ====================================================================


def assess_risk(context: RiskAssessmentContext) -> RiskLevel:
    """Assess project risk based on complexity, keywords, and flags.

    Heuristics:
      1. Complexity baseline.
      2. Security keyword scan.
      3. Infrastructure keyword scan.
      4. File count heuristic.
      5. Explicit security/infra scope flags.
    """
    score = _complexity_score(context.complexity)
    corpus = " ".join([context.description] + context.goals + context.constraints).lower()

    sec_hits = sum(1 for kw in SECURITY_KEYWORDS if kw in corpus)
    score += 2 if sec_hits >= 3 else 1 if sec_hits >= 1 else 0

    infra_hits = sum(1 for kw in INFRA_KEYWORDS if kw in corpus)
    score += 2 if infra_hits >= 3 else 1 if infra_hits >= 1 else 0

    if context.has_security_scope:
        score += 1
    if context.has_infrastructure_scope:
        score += 1
    if context.file_count is not None:
        if context.file_count > 500:
            score += 2
        elif context.file_count > 100:
            score += 1

    score = max(0, min(len(RISK_LEVELS) - 1, score))
    return RISK_LEVELS[score]


def select_decision_path(risk: RiskLevel) -> DecisionPath:
    """Map risk level to the appropriate decision path."""
    return RISK_TO_PATH[risk]


def evaluate_and_select_path(context: RiskAssessmentContext) -> dict:
    """Convenience: assess risk and select path in one call."""
    risk = assess_risk(context)
    path = select_decision_path(risk)
    return {"risk_level": risk.value, "decision_path": path.value}


def _complexity_score(complexity: str) -> int:
    mapping = {"simple": 0, "standard": 2, "advanced": 3, "enterprise": 4}
    return mapping.get(complexity, 2)
