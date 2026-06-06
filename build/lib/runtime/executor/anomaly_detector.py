"""Anomaly detection rule engine (agentmesh engine anomaly-*.ts migration)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

RuleOperator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "matches", "in", "not_in"]
LogicalOperator = Literal["and", "or", "not"]
Severity = Literal["low", "medium", "high", "critical"]
InterventionAction = Literal["pause", "rollback", "scale", "alert", "ignore"]
SEVERITY: dict[str, int] = {"low": 1, "medium": 2, "high": 3, "critical": 4}
ACTION_PRI: dict[str, int] = {"pause": 5, "rollback": 4, "scale": 3, "alert": 2, "ignore": 1}


@dataclass
class RuleCondition:
    metric: str; operator: RuleOperator; value: Any; weight: float = 1.0  # noqa: E702


@dataclass
class AnomalyRule:
    id: str; name: str; description: str; status: str; category: str  # noqa: E702
    condition: RuleCondition; frequency: str; severity: Severity  # noqa: E702
    intervention_action: InterventionAction; requires_confirmation: bool; cooldown_ms: float  # noqa: E702
    window_size: int | None = None; burst_threshold: int | None = None  # noqa: E702
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0; updated_at: float = 0.0  # noqa: E702


@dataclass
class RuleResult:
    rule_id: str; rule_name: str; triggered: bool; score: float; message: str; timestamp: float = 0.0  # noqa: E702


@dataclass
class DetectionResult:
    has_anomaly: bool; triggered: list[RuleResult]; max_severity: Severity | Literal["none"]; action: InterventionAction; summary: str; timestamp: float  # noqa: E702


class AnomalyRuleEngine:
    """Rule-based anomaly detection with frequency control and caching."""

    def __init__(self) -> None:
        self._rules: dict[str, AnomalyRule] = {}
        self._triggers: list[dict] = []
        self._cache: dict[str, tuple[RuleResult, float]] = {}
        self._last: dict[str, float] = {}

    def register_rule(self, rule: AnomalyRule) -> None:
        self._rules[rule.id] = rule

    def get_active_rules(self) -> list[AnomalyRule]:
        return [r for r in self._rules.values() if r.status == "active"]

    def evaluate(self, metrics: dict[str, Any]) -> DetectionResult:
        now = time.time(); triggered = []  # noqa: E702
        for rule in self.get_active_rules():
            last = self._last.get(rule.id)
            if last and (now - last) * 1000 < rule.cooldown_ms:
                continue
            actual = self._get_metric(metrics, rule.condition.metric)
            matched = self._compare(actual, rule.condition.operator, rule.condition.value)
            if matched:
                self._last[rule.id] = now
                triggered.append(RuleResult(rule_id=rule.id, rule_name=rule.name, triggered=True, score=rule.condition.weight, message=f"Triggered: {rule.description}", timestamp=now))
        sev: Severity | Literal["none"] = "none"
        for t in triggered:
            r = self._rules.get(t.rule_id)
            if r and SEVERITY.get(r.severity, 0) > SEVERITY.get(sev, 0) if isinstance(sev, str) or SEVERITY.get(sev, 0) else False:
                sev = r.severity  # type: ignore[union-attr]
        action = "ignore"
        for t in triggered:
            r = self._rules.get(t.rule_id)
            if r and ACTION_PRI.get(r.intervention_action, 0) > ACTION_PRI.get(action, 0):
                action = r.intervention_action
        return DetectionResult(has_anomaly=len(triggered) > 0, triggered=triggered, max_severity=sev, action=action, summary=f"{len(triggered)} anomaly(ies)" if triggered else "Normal", timestamp=now)  # type: ignore[arg-type]

    @staticmethod
    def _get_metric(m: dict[str, Any], path: str) -> Any:
        for part in path.split("."):
            m = m.get(part) if isinstance(m, dict) else None  # type: ignore[assignment]
            if m is None: return None  # noqa: E701
        return m

    @staticmethod
    def _compare(actual: Any, op: RuleOperator, expected: Any) -> bool:
        if op == "eq": return actual == expected  # noqa: E701
        if op == "ne": return actual != expected  # noqa: E701
        if op == "gt": return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual > expected  # noqa: E701
        if op == "gte": return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual >= expected  # noqa: E701
        if op == "lt": return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual < expected  # noqa: E701
        if op == "lte": return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual <= expected  # noqa: E701
        if op == "contains": return isinstance(actual, str) and isinstance(expected, str) and expected in actual  # noqa: E701
        if op == "matches": return isinstance(actual, str) and isinstance(expected, str) and bool(re.search(expected, actual))  # noqa: E701
        if op == "in": return isinstance(expected, list) and actual in expected  # noqa: E701
        if op == "not_in": return isinstance(expected, list) and actual not in expected  # noqa: E701
        return False
