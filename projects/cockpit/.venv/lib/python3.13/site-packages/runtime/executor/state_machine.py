"""
Phase State Machine -- agentmesh to kairon migration.

Simplified 5-phase lifecycle: INIT -> PLAN -> EXECUTE -> VALIDATE -> COMPLETE
With special states PAUSED and FAILED, plus DF-CEA risk-based decision paths.

Ported from agentmesh/packages/engine/src/state-machine.ts (575 lines).
Kept: transition table validation, PAUSE/RESUME, event hooks, serialization.
Simplified: 9-phase agentmesh model reduced to 5 core phases.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ============================================================
# Enums
# ============================================================


class Phase(StrEnum):
    """Core execution phases (simplified from agentmesh 9-phase)."""

    INIT = "INIT"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    COMPLETE = "COMPLETE"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class DecisionPath(StrEnum):
    """DF-CEA decision paths determining which phases may be skipped.

    EXPRESS  -- INIT -> EXECUTE (skip PLAN)
    QUICK    -- full flow but fast-tracked
    STANDARD -- full linear flow
    DEEP     -- full flow, VALIDATE -> EXECUTE retry allowed
    FULL     -- full flow with extra review gates
    """

    EXPRESS = "express"
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"
    FULL = "full"


class RiskLevel(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# Transition Table
# ============================================================

TRANSITION_TABLE: dict[Phase, list[Phase]] = {
    Phase.INIT: [Phase.PLAN, Phase.EXECUTE, Phase.PAUSED, Phase.FAILED],
    Phase.PLAN: [Phase.EXECUTE, Phase.PLAN, Phase.PAUSED, Phase.FAILED],
    Phase.EXECUTE: [Phase.VALIDATE, Phase.PAUSED, Phase.FAILED],
    Phase.VALIDATE: [Phase.COMPLETE, Phase.EXECUTE, Phase.PAUSED, Phase.FAILED],
    Phase.COMPLETE: [],
    Phase.FAILED: [Phase.INIT],
    Phase.PAUSED: [Phase.INIT, Phase.PLAN, Phase.EXECUTE, Phase.VALIDATE],
}

LINEAR_PHASE_ORDER: list[Phase] = [
    Phase.INIT,
    Phase.PLAN,
    Phase.EXECUTE,
    Phase.VALIDATE,
    Phase.COMPLETE,
]

SKIPPABLE_PHASES: dict[DecisionPath, list[Phase]] = {
    DecisionPath.EXPRESS: [Phase.PLAN],
    DecisionPath.QUICK: [],
    DecisionPath.STANDARD: [],
    DecisionPath.DEEP: [],
    DecisionPath.FULL: [],
}

RISK_TO_PATH: dict[RiskLevel, DecisionPath] = {
    RiskLevel.VERY_LOW: DecisionPath.EXPRESS,
    RiskLevel.LOW: DecisionPath.QUICK,
    RiskLevel.MEDIUM: DecisionPath.STANDARD,
    RiskLevel.HIGH: DecisionPath.DEEP,
    RiskLevel.CRITICAL: DecisionPath.FULL,
}


# ============================================================
# PhaseRecord
# ============================================================


@dataclass
class PhaseRecord:
    """Immutable record of a phase transition."""

    from_phase: Phase
    to_phase: Phase
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    decision_path: DecisionPath = DecisionPath.STANDARD
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_phase.value,
            "to": self.to_phase.value,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "decision_path": self.decision_path.value,
            "metadata": self.metadata,
        }


# ============================================================
# Event Hooks
# ============================================================


@dataclass
class PhaseHooks:
    """Optional callbacks invoked on phase transitions."""

    on_enter: dict[Phase, Callable[[PhaseRecord], None] | None] = field(default_factory=dict)
    on_exit: dict[Phase, Callable[[PhaseRecord], None] | None] = field(default_factory=dict)
    on_error: Callable[[Phase, Exception], None] | None = None


# ============================================================
# PhaseStateMachine
# ============================================================


class PhaseStateMachine:
    """Manages phase transitions with guard conditions and event hooks.

    Simplified from agentmesh Honeycomb v2 PhaseStateMachine:
      - 5 core phases instead of 9
      - DF-CEA decision path selection
      - PAUSED/FAILED bookkeeping
      - Full transition audit trail
      - Serialization to/from dict
    """

    def __init__(
        self,
        initial_phase: Phase = Phase.INIT,
        decision_path: DecisionPath = DecisionPath.STANDARD,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        hooks: PhaseHooks | None = None,
    ) -> None:
        self._current = initial_phase
        self._history: list[PhaseRecord] = []
        self._decision_path = decision_path
        self._risk_level = risk_level
        self._phase_before_pause: Phase | None = None
        self._hooks = hooks or PhaseHooks()

    # -- Properties --

    @property
    def current_phase(self) -> Phase:
        return self._current

    @property
    def decision_path(self) -> DecisionPath:
        return self._decision_path

    @property
    def risk_level(self) -> RiskLevel:
        return self._risk_level

    @property
    def history(self) -> list[PhaseRecord]:
        return list(self._history)

    @property
    def phase_before_pause(self) -> Phase | None:
        return self._phase_before_pause

    # -- Transition logic --

    def can_transition_to(self, target: Phase) -> bool:
        """Check whether the transition is legal."""
        if target is self._current:
            return False
        return target in TRANSITION_TABLE.get(self._current, [])

    def transition_to(
        self,
        target: Phase,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PhaseRecord:
        """Attempt a phase transition.  Raises ValueError if illegal."""
        if not self.can_transition_to(target):
            allowed = [p.value for p in TRANSITION_TABLE.get(self._current, [])]
            raise ValueError(
                f"Invalid phase transition: {self._current.value} -> {target.value}. "
                f"Allowed targets: {allowed}"
            )

        from_phase = self._current

        # on_exit hook
        on_exit = self._hooks.on_exit.get(from_phase)
        if on_exit:
            try:
                on_exit(PhaseRecord(from_phase=from_phase, to_phase=target, reason=reason))
            except Exception:
                pass

        # PAUSE/RESUME bookkeeping
        if target is Phase.PAUSED:
            self._phase_before_pause = from_phase
        elif self._current is Phase.PAUSED:
            self._phase_before_pause = None

        record = PhaseRecord(
            from_phase=from_phase,
            to_phase=target,
            reason=reason,
            decision_path=self._decision_path,
            metadata=metadata or {},
        )
        self._current = target
        self._history.append(record)

        # on_enter hook
        on_enter = self._hooks.on_enter.get(target)
        if on_enter:
            try:
                on_enter(record)
            except Exception:
                pass

        return record

    def pause(self, reason: str = "Paused") -> PhaseRecord:
        return self.transition_to(Phase.PAUSED, reason)

    def resume(self, target: Phase | None = None, reason: str = "Resumed") -> PhaseRecord:
        if self._current is not Phase.PAUSED:
            raise ValueError(f"Cannot resume: current is {self._current.value}, not PAUSED")
        dest = target or self._phase_before_pause
        if dest is None:
            raise ValueError("Cannot resume: no previous phase recorded and no override")
        return self.transition_to(dest, reason)

    def fail(self, reason: str = "", metadata: dict[str, Any] | None = None) -> PhaseRecord:
        return self.transition_to(Phase.FAILED, reason, metadata)

    def advance(self, reason: str = "", metadata: dict[str, Any] | None = None) -> PhaseRecord:
        """Advance to the next phase in the effective sequence."""
        nxt = self._get_next_phase()
        if nxt is None:
            raise ValueError(
                f"Cannot advance from {self._current.value}: "
                f"sequence is {[p.value for p in self.effective_sequence]}"
            )
        return self.transition_to(nxt, reason, metadata)

    # -- Effective sequence (decision-path aware) --

    @property
    def skipped_phases(self) -> list[Phase]:
        return list(SKIPPABLE_PHASES.get(self._decision_path, []))

    @property
    def effective_sequence(self) -> list[Phase]:
        skipped = set(self.skipped_phases)
        return [p for p in LINEAR_PHASE_ORDER if p not in skipped]

    @property
    def available_transitions(self) -> list[Phase]:
        return [t for t in TRANSITION_TABLE.get(self._current, []) if self.can_transition_to(t)]

    def _get_next_phase(self) -> Phase | None:
        seq = self.effective_sequence
        try:
            idx = seq.index(self._current)
            return seq[idx + 1] if idx + 1 < len(seq) else None
        except ValueError:
            return None

    # -- DF-CEA: Risk Assessment & Path Selection --

    def assess_risk(self, description: str, goals: list[str], file_count: int = 0) -> RiskLevel:
        """Keyword-based risk assessment (matches agentmesh heuristics)."""
        corpus = (description + " " + " ".join(goals)).lower()

        security_kw = [
            "security", "auth", "payment", "encrypt", "credential", "token",
            "secret", "permission", "rbac", "oauth", "certificate", "ssl", "tls",
            "firewall", "vulnerability", "compliance", "gdpr", "hipaa", "pci",
        ]
        infra_kw = [
            "database", "migration", "deploy", "production", "infrastructure",
            "kubernetes", "scaling", "cluster", "replication", "failover",
            "dns", "load-balancer", "cdn",
        ]

        score = 2  # baseline MEDIUM
        sec = sum(1 for kw in security_kw if kw in corpus)
        if sec >= 3:
            score += 2
        elif sec >= 1:
            score += 1

        inf = sum(1 for kw in infra_kw if kw in corpus)
        if inf >= 3:
            score += 2
        elif inf >= 1:
            score += 1

        if file_count > 500:
            score += 2
        elif file_count > 100:
            score += 1

        levels = list(RiskLevel)
        clamped = max(0, min(len(levels) - 1, score))
        self._risk_level = levels[clamped]
        return self._risk_level

    def select_decision_path(self, risk_level: RiskLevel | None = None) -> DecisionPath:
        rl = risk_level or self._risk_level
        self._decision_path = RISK_TO_PATH.get(rl, DecisionPath.STANDARD)
        self._risk_level = rl
        return self._decision_path

    def evaluate_and_select(
        self, description: str, goals: list[str], file_count: int = 0
    ) -> tuple[RiskLevel, DecisionPath]:
        risk = self.assess_risk(description, goals, file_count)
        path = self.select_decision_path(risk)
        return risk, path

    # -- Serialization --

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_phase": self._current.value,
            "history": [r.to_dict() for r in self._history],
            "decision_path": self._decision_path.value,
            "risk_level": self._risk_level.value,
            "phase_before_pause": self._phase_before_pause.value if self._phase_before_pause else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], hooks: PhaseHooks | None = None) -> PhaseStateMachine:
        sm = cls(
            initial_phase=Phase(data["current_phase"]),
            decision_path=DecisionPath(data.get("decision_path", "standard")),
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            hooks=hooks,
        )
        sm._history = [
            PhaseRecord(
                from_phase=Phase(r["from"]),
                to_phase=Phase(r["to"]),
                timestamp=r.get("timestamp", 0.0),
                reason=r.get("reason", ""),
                decision_path=DecisionPath(r.get("decision_path", "standard")),
                metadata=r.get("metadata", {}),
            )
            for r in data.get("history", [])
        ]
        pbp = data.get("phase_before_pause")
        sm._phase_before_pause = Phase(pbp) if pbp else None
        return sm


# ============================================================
# Factory
# ============================================================


def create_state_machine(
    initial_phase: Phase = Phase.INIT,
    decision_path: DecisionPath = DecisionPath.STANDARD,
    hooks: PhaseHooks | None = None,
) -> PhaseStateMachine:
    """Create a new PhaseStateMachine instance."""
    return PhaseStateMachine(initial_phase=initial_phase, decision_path=decision_path, hooks=hooks)
