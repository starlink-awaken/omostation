"""Symbolic Research Operations — state machine primitives for research paradigms.

Models research as a Turing-machine-like state machine:
- Σ (states): 12 research states from QUESTION to CONCLUSION
- O (operations): 10 atomic research actions
- δ (transitions): 12 base transition rules with gate conditions

A paradigm is a ParadigmProgram composed from these atoms — not a fixed template.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════
# State Symbols
# ═══════════════════════════════════════════════════════════════════════


class ResearchState(Enum):
    """All possible states in a research state machine."""

    QUESTION = "question"
    DECOMPOSED = "decomposed"
    HYPOTHESIS = "hypothesis"
    SEARCHING = "searching"
    EVIDENCE = "evidence"
    CLAIM = "claim"
    CONTRADICTION = "contradiction"
    SYNTHESIS = "synthesis"
    VERIFIED = "verified"
    GAP = "gap"
    CONCLUSION = "conclusion"
    ITERATING = "iterating"


# ═══════════════════════════════════════════════════════════════════════
# Atomic Operations
# ═══════════════════════════════════════════════════════════════════════


class AtomicOp(Enum):
    """Irreducible research operations — building blocks of any paradigm."""

    DECOMPOSE = "decompose"
    SEARCH = "search"
    EXTRACT = "extract"
    COMPARE = "compare"
    HYPOTHESIZE = "hypothesize"
    VERIFY = "verify"
    SYNTHESIZE = "synthesize"
    ELIMINATE = "eliminate"
    ITERATE = "iterate"
    CONCLUDE = "conclude"

    @classmethod
    def from_string(cls, s: str) -> AtomicOp | None:
        """Case-insensitive lookup from string value."""
        for member in cls:
            if member.value == s.lower():
                return member
        return None


# ═══════════════════════════════════════════════════════════════════════
# Transition Rule
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class TransitionRule:
    """δ(from_state, operation) → (to_state, gate, on_fail)

    A transition is a single step in the state machine. The gate function
    receives a context dict with keys like source_count, entity_count,
    quality_score, contradiction_count. Returns True if the transition
    should proceed to to_state; False routes to on_fail instead.
    """

    from_state: ResearchState
    operation: AtomicOp
    to_state: ResearchState
    gate: Callable[[dict], bool]
    on_fail: ResearchState
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Gate Functions (public — consumed by execution engines)
# ═══════════════════════════════════════════════════════════════════════


def gate_always(ctx: dict) -> bool:
    return True


def gate_has_sources(ctx: dict) -> bool:
    return bool(ctx.get("source_count", 0) >= 2)


def gate_has_entities(ctx: dict) -> bool:
    return bool(ctx.get("entity_count", 0) > 0)


def gate_has_contradictions(ctx: dict) -> bool:
    return bool(ctx.get("contradiction_count", 0) > 0)


def gate_quality_pass(ctx: dict) -> bool:
    return bool(ctx.get("quality_score", 0) >= 60)


# ═══════════════════════════════════════════════════════════════════════
# Base Transition Rules (canonical set)
# ═══════════════════════════════════════════════════════════════════════

BASE_TRANSITIONS: list[TransitionRule] = [
    TransitionRule(
        ResearchState.QUESTION,
        AtomicOp.DECOMPOSE,
        ResearchState.DECOMPOSED,
        gate_always,
        ResearchState.QUESTION,
        "Decompose question into sub-questions",
    ),
    TransitionRule(
        ResearchState.DECOMPOSED,
        AtomicOp.HYPOTHESIZE,
        ResearchState.HYPOTHESIS,
        gate_always,
        ResearchState.DECOMPOSED,
        "Formulate tentative answer",
    ),
    TransitionRule(
        ResearchState.HYPOTHESIS,
        AtomicOp.SEARCH,
        ResearchState.SEARCHING,
        gate_always,
        ResearchState.HYPOTHESIS,
        "Search for evidence",
    ),
    TransitionRule(
        ResearchState.SEARCHING,
        AtomicOp.EXTRACT,
        ResearchState.EVIDENCE,
        gate_has_sources,
        ResearchState.GAP,
        "Extract claims from sources; if no sources → GAP",
    ),
    TransitionRule(
        ResearchState.EVIDENCE,
        AtomicOp.VERIFY,
        ResearchState.VERIFIED,
        gate_has_sources,
        ResearchState.GAP,
        "Verify claims against sources",
    ),
    TransitionRule(
        ResearchState.VERIFIED,
        AtomicOp.COMPARE,
        ResearchState.CLAIM,
        gate_has_entities,
        ResearchState.VERIFIED,
        "Compare multiple claims; re-verify if no entities",
    ),
    TransitionRule(
        ResearchState.CLAIM,
        AtomicOp.VERIFY,
        ResearchState.CONTRADICTION,
        gate_has_contradictions,
        ResearchState.CLAIM,
        "Check for contradictions; if present → CONTRADICTION branch",
    ),
    TransitionRule(
        ResearchState.CLAIM,
        AtomicOp.ELIMINATE,
        ResearchState.VERIFIED,
        gate_has_contradictions,
        ResearchState.CONTRADICTION,
        "Eliminate disproven claim; if contradictions → CONTRADICTION",
    ),
    TransitionRule(
        ResearchState.CLAIM,
        AtomicOp.SYNTHESIZE,
        ResearchState.SYNTHESIS,
        gate_quality_pass,
        ResearchState.GAP,
        "Synthesize claims; if quality low → GAP",
    ),
    TransitionRule(
        ResearchState.GAP,
        AtomicOp.ITERATE,
        ResearchState.SEARCHING,
        gate_always,
        ResearchState.GAP,
        "Gap detected → re-search with refined parameters",
    ),
    TransitionRule(
        ResearchState.SYNTHESIS,
        AtomicOp.CONCLUDE,
        ResearchState.CONCLUSION,
        gate_always,
        ResearchState.SYNTHESIS,
        "Finalize answer",
    ),
    TransitionRule(
        ResearchState.CONTRADICTION,
        AtomicOp.SYNTHESIZE,
        ResearchState.SYNTHESIS,
        gate_quality_pass,
        ResearchState.CONTRADICTION,
        "Synthesize despite contradictions",
    ),
    TransitionRule(
        ResearchState.GAP,
        AtomicOp.CONCLUDE,
        ResearchState.CONCLUSION,
        gate_always,
        ResearchState.GAP,
        "Conclude with documented gaps",
    ),
]


# ═══════════════════════════════════════════════════════════════════════
# Paradigm Program (composable, serializable)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ParadigmProgram:
    """A research paradigm defined as a state machine program.

    Composed from atomic operations and transition rules. Can be serialized
    via to_dict() / from_dict() for storage in learner traces.
    """

    name: str
    description: str = ""
    operations: list[AtomicOp] = field(default_factory=list)
    transitions: list[TransitionRule] = field(default_factory=list)
    initial_state: ResearchState = ResearchState.QUESTION
    terminal_states: list[ResearchState] = field(default_factory=lambda: [ResearchState.CONCLUSION])
    max_iterations: int = 3
    metadata: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Check consistency between operations and transitions. Returns list of issues."""
        issues = []
        if not self.operations:
            issues.append("No operations defined")
        if not self.transitions:
            issues.append("No transitions defined")
        op_set = set(self.operations)
        trans_ops = {t.operation for t in self.transitions}
        if op_set - trans_ops:
            missing = [o.value for o in (op_set - trans_ops)]
            issues.append(f"Operations without transitions: {missing}")
        return issues

    @property
    def state_count(self) -> int:
        return len({t.from_state for t in self.transitions} | {t.to_state for t in self.transitions})

    def to_dict(self, include_query: str = "") -> dict:
        d = {
            "name": self.name,
            "description": self.description,
            "ops": [op.value for op in self.operations],
            "state_count": self.state_count,
            "transition_count": len(self.transitions),
            "max_iterations": self.max_iterations,
            "mermaid": self.to_mermaid(),
        }
        if include_query:
            d["query"] = include_query
        return d

    @classmethod
    def from_dict(cls, data: dict, transitions: list[TransitionRule] | None = None) -> ParadigmProgram:
        """Deserialize from dict. Reconstructs operations from op strings.
        Transitions must be provided separately since gate functions (Callable)
        cannot be serialized. Use recompile_from_dict() to recover transitions.
        """
        ops = []
        for o in data.get("ops", []):
            op = AtomicOp.from_string(o)
            if op:
                ops.append(op)
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            operations=ops,
            transitions=transitions or [],
            max_iterations=data.get("max_iterations", 3),
        )

    def to_mermaid(self) -> str:
        """Export paradigm as a Mermaid state diagram."""
        lines = ["stateDiagram-v2"]
        seen = set()
        for t in self.transitions:
            key = (t.from_state.value, t.operation.value, t.to_state.value)
            if key in seen:
                continue
            seen.add(key)
            gate_name = t.gate.__name__.replace("gate_", "")
            lines.append(f"    {t.from_state.value} --> {t.to_state.value} : {t.operation.value} [{gate_name}]")
        for ts in self.terminal_states:
            lines.append(f"    {ts.value} --> [*]")
        return "\n".join(lines)

    def diff(self, other: ParadigmProgram) -> dict:
        """Compare two ParadigmPrograms, returning the delta."""
        self_ops = {op.value for op in self.operations}
        other_ops = {op.value for op in other.operations}
        return {
            "name": {"self": self.name, "other": other.name},
            "added_ops": sorted(other_ops - self_ops),
            "removed_ops": sorted(self_ops - other_ops),
            "common_ops": sorted(self_ops & other_ops),
            "self_state_count": self.state_count,
            "other_state_count": other.state_count,
            "self_transitions": len(self.transitions),
            "other_transitions": len(other.transitions),
        }
