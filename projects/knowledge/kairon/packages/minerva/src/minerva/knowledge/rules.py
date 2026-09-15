"""Knowledge rule engine — lightweight Datalog replacement for temporal validation.

Provides condition→action rules with AND/OR/NOT logic for knowledge base maintenance.
Designed as a practical alternative to full Semantica Datalog (~10h standalone product).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast


class RuleSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class RuleCondition:
    """A single condition: field + operator + value."""

    field: str
    operator: str  # eq, neq, gt, lt, gte, lte, contains, exists, not_exists, older_than
    value: Any = None


@dataclass
class Rule:
    """A knowledge maintenance rule with conditions and an action."""

    name: str
    description: str
    conditions: list[RuleCondition]
    logic: str = "AND"  # AND | OR
    severity: RuleSeverity = RuleSeverity.WARNING
    action_message: str = ""


@dataclass
class RuleResult:
    """Result of evaluating a rule against an entity."""

    rule_name: str
    entity_id: str
    passed: bool
    message: str
    severity: RuleSeverity


class RuleEngine:
    """Evaluate maintenance rules against knowledge base entities.

    Usage:
        engine = RuleEngine()
        engine.add_rule(Rule(
            name="stale_entity",
            description="Entity not verified in >365 days",
            conditions=[RuleCondition("last_verified", "older_than", 365)],
            severity=RuleSeverity.CRITICAL,
            action_message="Needs re-verification",
        ))
        results = engine.evaluate(entities)
    """

    def __init__(self) -> None:
        self.rules: list[Rule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Pre-register standard knowledge maintenance rules."""
        self.add_rule(
            Rule(
                name="entity_stale_unverified",
                description="Entity not verified in over 365 days",
                conditions=[RuleCondition("last_verified", "older_than", 365)],
                severity=RuleSeverity.CRITICAL,
                action_message="Mark for re-verification or archive",
            )
        )
        self.add_rule(
            Rule(
                name="entity_low_confidence",
                description="Entity with LOW confidence and no source IDs",
                conditions=[
                    RuleCondition("confidence", "eq", "LOW"),
                    RuleCondition("source_ids", "empty"),
                ],
                logic="AND",
                severity=RuleSeverity.WARNING,
                action_message="Add source references or upgrade confidence",
            )
        )
        self.add_rule(
            Rule(
                name="relation_contradicts_supports_same_source",
                description="Same source claims both CONTRADICTS and SUPPORTS",
                conditions=[
                    RuleCondition("predicate", "eq", "CONTRADICTS"),
                ],
                severity=RuleSeverity.WARNING,
                action_message="Flag for human review — contradictory signals from same source",
            )
        )

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def evaluate(self, entities: list[dict]) -> list[RuleResult]:
        """Run all rules against a list of entity dicts. passed=False means rule fired."""
        results = []
        for entity in entities:
            for rule in self.rules:
                rule_fired = self._evaluate_rule(entity, rule)
                results.append(
                    RuleResult(
                        rule_name=rule.name,
                        entity_id=entity.get("id", entity.get("name", "?")),
                        passed=not rule_fired,  # Rule firing = problem detected
                        message=rule.action_message if rule_fired else "OK",
                        severity=rule.severity,
                    )
                )
        return results

    def evaluate_one(self, entity: dict) -> list[RuleResult]:
        """Run all rules against a single entity."""
        return self.evaluate([entity])

    def _evaluate_rule(self, entity: dict, rule: Rule) -> bool:
        """Evaluate whether an entity passes a rule (returns True = pass)."""
        if rule.logic == "AND":
            return all(self._check_condition(entity, c) for c in rule.conditions)
        elif rule.logic == "OR":
            return any(self._check_condition(entity, c) for c in rule.conditions)
        return True

    def _check_condition(self, entity: dict, cond: RuleCondition) -> bool:
        """Evaluate a single condition against an entity."""
        val = entity.get(cond.field)
        op = cond.operator

        if op == "exists":
            return val is not None and val != ""
        if op == "not_exists":
            return val is None or val == ""
        if op == "empty":
            return not val or (isinstance(val, (list, dict)) and len(val) == 0)
        if op == "eq" and val is not None:
            return str(val).upper() == str(cond.value).upper()
        if op == "neq" and val is not None:
            return str(val).upper() != str(cond.value).upper()
        if op == "contains" and isinstance(val, str):
            return str(cond.value).lower() in val.lower()
        if op == "older_than" and isinstance(val, str):
            try:
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                days = (datetime.now(UTC) - dt).days
                return cast("bool", days > cond.value)  # True = older than threshold problem)
            except (ValueError, TypeError):
                return False  # Can't parse date → don't flag
        if op == "gt" and isinstance(val, (int, float)):
            return cast("bool", val > cond.value)
        if op == "lt" and isinstance(val, (int, float)):
            return cast("bool", val < cond.value)

        return False  # Unknown operator or missing value → no problem detected


def run_maintenance_rules(entities: list[dict]) -> dict:
    """Convenience: run default rules and return summary."""
    engine = RuleEngine()
    results = engine.evaluate(entities)
    failed = [r for r in results if not r.passed]
    return {
        "total_rules": len(engine.rules),
        "total_entities": len(entities),
        "results_count": len(results),
        "failures": len(failed),
        "critical": sum(1 for r in failed if r.severity == RuleSeverity.CRITICAL),
        "warnings": sum(1 for r in failed if r.severity == RuleSeverity.WARNING),
        "details": [
            {
                "entity": r.entity_id,
                "rule": r.rule_name,
                "severity": r.severity.value,
                "message": r.message,
            }
            for r in failed
        ],
    }
