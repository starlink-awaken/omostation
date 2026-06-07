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
# Hypothesis Pipeline ≡ Pipeline
# 内涵 ≝ {Hypothesis, Pipeline}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, HypothesisPipeline)}
# 功能 ⊢ {Hypothesis_Pipeline, Init_Hypothesis, Validate_Pipeline}
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
class Hypothesis:
    hyp_id: str
    statement: str
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    confidence: float = 0.5
    status: str = "open"


class HypothesisPipeline:
    """Pipeline for proposing, testing, and resolving hypotheses."""

    def __init__(self) -> None:
        super().__init__()
        self._hypotheses: dict[str, Hypothesis] = {}

    def propose(self, statement: str) -> Hypothesis:
        hyp_id = uuid.uuid4().hex[:12]
        hyp = Hypothesis(hyp_id=hyp_id, statement=statement)
        self._hypotheses[hyp_id] = hyp
        _log.info("Proposed hypothesis %s: %s", hyp_id, statement)
        return hyp

    def add_evidence(self, hyp_id: str, evidence: str, supports: bool) -> None:
        hyp = self._hypotheses.get(hyp_id)
        if hyp is None:
            raise KeyError(f"Hypothesis {hyp_id} not found")
        if supports:
            hyp.evidence_for.append(evidence)
        else:
            hyp.evidence_against.append(evidence)

    def evaluate(self, hyp_id: str) -> float:
        hyp = self._hypotheses.get(hyp_id)
        if hyp is None:
            raise KeyError(f"Hypothesis {hyp_id} not found")
        total_for = len(hyp.evidence_for)
        total_against = len(hyp.evidence_against)
        total = total_for + total_against
        if total == 0:
            hyp.confidence = 0.5
        else:
            hyp.confidence = total_for / total
        return hyp.confidence

    def accept(self, hyp_id: str) -> None:
        hyp = self._hypotheses.get(hyp_id)
        if hyp is None:
            raise KeyError(f"Hypothesis {hyp_id} not found")
        hyp.status = "accepted"

    def reject(self, hyp_id: str) -> None:
        hyp = self._hypotheses.get(hyp_id)
        if hyp is None:
            raise KeyError(f"Hypothesis {hyp_id} not found")
        hyp.status = "rejected"

    def get_hypothesis(self, hyp_id: str) -> Hypothesis | None:
        return self._hypotheses.get(hyp_id)

    def list_open(self) -> list[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.status == "open"]

    def get_strongest(self) -> Hypothesis | None:
        open_hyps = self.list_open()
        if not open_hyps:
            return None
        return max(open_hyps, key=lambda h: h.confidence)

    def get_competing(self, hyp_id: str) -> list[Hypothesis]:
        hyp = self._hypotheses.get(hyp_id)
        if hyp is None:
            raise KeyError(f"Hypothesis {hyp_id} not found")
        target_evidence = set(hyp.evidence_for) | set(hyp.evidence_against)
        competing: list[Hypothesis] = []
        for other in self._hypotheses.values():
            if other.hyp_id == hyp_id:
                continue
            other_evidence = set(other.evidence_for) | set(other.evidence_against)
            if target_evidence & other_evidence:
                competing.append(other)
        return competing
