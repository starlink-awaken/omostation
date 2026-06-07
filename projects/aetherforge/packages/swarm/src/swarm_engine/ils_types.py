from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ._compat import Infrastructure

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for ils_types.py'
Tags:
- auto-metadata
Authority: organs/D-Execution/AGENTS.md
---
"""

_log = logging.getLogger(__name__)
Type: Infrastructure

"""
Type: Infrastructure
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L0-L2
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/ils_types.py'
Tags:
- auto-metadata

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================
"""

# duplicated from __future__ import annotations removed

_log = logging.getLogger(__name__)


class DecisionEnum(StrEnum):
    PERMIT = "permit"
    DENY = "deny"
    CONDITIONAL = "conditional"


class RiskLevel(StrEnum):
    SAFE = "safe"
    RISKY = "risky"
    CRITICAL = "critical"


class EventType(StrEnum):
    AUTHORIZATION = "authorization"
    GOVERNANCE = "governance"
    VALIDATION = "validation"
    RISK_ASSESSMENT = "risk_assessment"
    SYSTEM = "system"


@dataclass
class ActionIntent:
    id: str
    actor: str
    target_path: str
    operation: str
    target_layer: int
    actor_layer: int
    reversible: bool = True
    priority: int = 2
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationResult:
    decision: DecisionEnum
    reason: str
    rule_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceDecision:
    permitted: bool
    # Engine uses policies_applied / constraints_violated (not reason/policy_id)
    policies_applied: list[str] = field(default_factory=list)
    constraints_violated: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        """Convenience accessor: first violated constraint or 'permitted'."""
        if self.constraints_violated:
            return f"Violated: {', '.join(self.constraints_violated)}"
        return "permitted"


@dataclass
class ValidationResult:
    valid: bool
    # Engine uses 'errors' and 'sanitized_data' (not 'violations')
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_data: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def violations(self) -> list[str]:
        """Alias kept for compatibility — same as errors."""
        return self.errors


@dataclass
class RiskAssessment:
    risk_level: RiskLevel
    score: float
    factors: list[str] = field(default_factory=list)
    remediation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    id: str
    event_type: EventType
    actor: str
    action: str
    target: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class AuthorizationError(Exception):
    """Raised when an action is denied by the LAW pillar."""


class ValidationError(Exception):
    """Raised when content fails governance validation."""
