from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Reasoning Engine ≡ Engine
# 内涵 ≝ {Reasoning, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ReasoningEngine)}
# 功能 ⊢ {Reasoning_Engine, Init_Reasoning, Validate_Engine}
# =============================================================================

# ---
# domain: D-Intelligence
# layer: organ
# status: active
# ---

import logging
import uuid
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    step_id: str
    type: str
    input_data: dict
    output_data: dict | None = None
    confidence: float = 0.0


@dataclass
class ReasoningChain:
    chain_id: str
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str | None = None
    confidence: float = 0.0


class ReasoningEngine:
    """Unified reasoning engine for building and evaluating reasoning chains."""

    def __init__(self) -> None:
        super().__init__()
        self._chains: dict[str, ReasoningChain] = {}

    def create_chain(self, goal: str) -> ReasoningChain:
        chain_id = uuid.uuid4().hex[:12]
        chain = ReasoningChain(chain_id=chain_id)
        self._chains[chain_id] = chain
        _log.info("Created reasoning chain %s for goal: %s", chain_id, goal)
        return chain

    def add_step(self, chain_id: str, step_type: str, input_data: dict) -> ReasoningStep:
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        step_id = uuid.uuid4().hex[:8]
        step = ReasoningStep(step_id=step_id, type=step_type, input_data=input_data)
        chain.steps.append(step)
        return step

    def evaluate_step(self, chain_id: str, step_id: str, output: dict, confidence: float) -> None:
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        for step in chain.steps:
            if step.step_id == step_id:
                step.output_data = output
                step.confidence = confidence
                return
        raise KeyError(f"Step {step_id} not found in chain {chain_id}")

    def get_chain(self, chain_id: str) -> ReasoningChain | None:
        return self._chains.get(chain_id)

    def conclude(self, chain_id: str, conclusion: str, confidence: float) -> None:
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        chain.conclusion = conclusion
        chain.confidence = confidence

    def get_confidence(self, chain_id: str) -> float:
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        if not chain.steps:
            return 0.0
        evaluated = [s for s in chain.steps if s.output_data is not None]
        if not evaluated:
            return 0.0
        return sum(s.confidence for s in evaluated) / len(evaluated)

    def get_weakest_link(self, chain_id: str) -> ReasoningStep | None:
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        evaluated = [s for s in chain.steps if s.output_data is not None]
        if not evaluated:
            return None
        return min(evaluated, key=lambda s: s.confidence)

    def validate_chain(self, chain_id: str) -> tuple[bool, list[str]]:
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        issues: list[str] = []
        if not chain.steps:
            issues.append("Chain has no steps")
        unevaluated = [s for s in chain.steps if s.output_data is None]
        if unevaluated:
            issues.append(f"{len(unevaluated)} step(s) not evaluated")
        low_conf = [s for s in chain.steps if s.output_data is not None and s.confidence < 0.3]
        if low_conf:
            issues.append(f"{len(low_conf)} step(s) with low confidence (<0.3)")
        if chain.conclusion is None:
            issues.append("Chain has no conclusion")
        return (len(issues) == 0, issues)
