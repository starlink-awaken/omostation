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
# Inference Engine ≡ Engine
# 内涵 ≝ {Inference, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, InferenceEngine)}
# 功能 ⊢ {Inference_Engine, Init_Inference, Validate_Engine}
# =============================================================================

# ---
# domain: D-Intelligence
# layer: organ
# status: active
# ---

import logging
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class Rule:
    rule_id: str
    conditions: list[str]
    conclusion: str
    confidence: float = 1.0
    priority: int = 0


@dataclass
class Fact:
    name: str
    value: Any = True
    confidence: float = 1.0


class InferenceEngine:
    """Forward- and backward-chaining inference engine."""

    def __init__(self) -> None:
        super().__init__()
        self._rules: list[Rule] = []
        self._facts: dict[str, Fact] = {}
        self._derivation: dict[str, list[str]] = {}  # fact_name -> [rule_ids that derived it]

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def assert_fact(self, fact: Fact) -> None:
        self._facts[fact.name] = fact

    def retract_fact(self, name: str) -> None:
        self._facts.pop(name, None)
        self._derivation.pop(name, None)

    def infer(self) -> list[Fact]:
        new_facts: list[Fact] = []
        changed = True
        while changed:
            changed = False
            for rule in self._rules:
                if rule.conclusion in self._facts:
                    continue
                if all(c in self._facts for c in rule.conditions):
                    cond_confidences = [self._facts[c].confidence for c in rule.conditions]
                    derived_confidence = min(cond_confidences) * rule.confidence
                    new_fact = Fact(
                        name=rule.conclusion,
                        value=True,
                        confidence=derived_confidence,
                    )
                    self._facts[new_fact.name] = new_fact
                    self._derivation.setdefault(new_fact.name, []).append(rule.rule_id)
                    new_facts.append(new_fact)
                    changed = True
        return new_facts

    def query(self, conclusion: str) -> float | None:
        if conclusion in self._facts:
            return self._facts[conclusion].confidence
        for rule in self._rules:
            if rule.conclusion == conclusion:
                cond_confs: list[float] = []
                all_met = True
                for cond in rule.conditions:
                    c = self.query(cond)
                    if c is None:
                        all_met = False
                        break
                    cond_confs.append(c)
                if all_met and cond_confs:
                    return min(cond_confs) * rule.confidence
        return None

    def explain(self, fact_name: str) -> list[str]:
        chain: list[str] = []
        if fact_name not in self._facts:
            return chain
        rule_ids = self._derivation.get(fact_name, [])
        if not rule_ids:
            chain.append(f"{fact_name} is an asserted fact")
            return chain
        for rid in rule_ids:
            rule = next((r for r in self._rules if r.rule_id == rid), None)
            if rule:
                chain.append(f"Rule '{rule.rule_id}': {' AND '.join(rule.conditions)} => {rule.conclusion}")
                for cond in rule.conditions:
                    chain.extend(self.explain(cond))
        return chain

    def get_facts(self) -> list[Fact]:
        return list(self._facts.values())

    def get_rules(self) -> list[Rule]:
        return list(self._rules)

    def reset(self) -> None:
        self._rules.clear()
        self._facts.clear()
        self._derivation.clear()
