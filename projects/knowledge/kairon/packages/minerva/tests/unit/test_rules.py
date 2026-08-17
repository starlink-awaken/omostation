"""Tests for knowledge rule engine (Datalog replacement)."""

from datetime import UTC, datetime, timedelta


class TestRuleCondition:
    def test_exists(self):
        from minerva.knowledge.rules import RuleCondition

        c = RuleCondition("name", "exists")
        assert c.operator == "exists"

    def test_older_than(self):
        from minerva.knowledge.rules import RuleCondition

        c = RuleCondition("last_verified", "older_than", 365)
        assert c.value == 365


class TestRuleEngine:
    def test_default_rules_registered(self):
        from minerva.knowledge.rules import RuleEngine

        engine = RuleEngine()
        assert len(engine.rules) >= 3

    def test_evaluate_entity_passes(self):
        from minerva.knowledge.rules import RuleEngine

        engine = RuleEngine()
        entity = {
            "id": "e1",
            "name": "OpenAI",
            "type": "Organization",
            "confidence": "HIGH",
            "last_verified": datetime.now(UTC).isoformat(),
            "source_ids": ["https://example.com"],
        }
        results = engine.evaluate_one(entity)
        assert all(r.passed for r in results)

    def test_evaluate_low_confidence_no_source(self):
        from minerva.knowledge.rules import RuleEngine

        engine = RuleEngine()
        entity = {
            "id": "e2",
            "name": "Unknown",
            "type": "Concept",
            "confidence": "LOW",
            "source_ids": [],
        }
        results = engine.evaluate_one(entity)
        failures = [r for r in results if not r.passed]
        assert len(failures) > 0

    def test_evaluate_stale_entity(self):
        from minerva.knowledge.rules import RuleEngine

        engine = RuleEngine()
        stale_date = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        entity = {
            "id": "e3",
            "name": "Old",
            "last_verified": stale_date,
            "confidence": "MEDIUM",
            "source_ids": ["src"],
        }
        results = engine.evaluate_one(entity)
        failures = [r for r in results if not r.passed]
        assert len(failures) > 0

    def test_rule_and_logic(self):
        from minerva.knowledge.rules import Rule, RuleCondition, RuleEngine, RuleSeverity

        engine = RuleEngine()
        engine.rules = []  # Clear defaults
        engine.add_rule(
            Rule(
                name="test_and",
                description="Both conditions must match",
                conditions=[
                    RuleCondition("confidence", "eq", "LOW"),
                    RuleCondition("source_ids", "empty"),
                ],
                logic="AND",
                severity=RuleSeverity.WARNING,
            )
        )
        entity = {"id": "e4", "confidence": "LOW", "source_ids": []}
        results = engine.evaluate_one(entity)
        assert not results[0].passed  # Should fail

        entity_ok = {"id": "e5", "confidence": "HIGH", "source_ids": ["src"]}
        results = engine.evaluate_one(entity_ok)
        assert results[0].passed

    def test_rule_or_logic(self):
        from minerva.knowledge.rules import Rule, RuleCondition, RuleEngine, RuleSeverity

        engine = RuleEngine()
        engine.rules = []
        engine.add_rule(
            Rule(
                name="test_or",
                description="Either condition triggers",
                conditions=[
                    RuleCondition("confidence", "eq", "LOW"),
                    RuleCondition("name", "eq", "TestFlag"),
                ],
                logic="OR",
                severity=RuleSeverity.WARNING,
            )
        )
        entity = {"id": "e6", "confidence": "MEDIUM", "name": "TestFlag"}
        results = engine.evaluate_one(entity)
        assert not results[0].passed  # name matches TestFlag

    def test_run_maintenance_rules(self):
        from minerva.knowledge.rules import run_maintenance_rules

        entities = [
            {
                "id": "e1",
                "name": "A",
                "confidence": "HIGH",
                "source_ids": ["s1"],
                "last_verified": datetime.now(UTC).isoformat(),
            },
            {"id": "e2", "name": "B", "confidence": "LOW", "source_ids": []},
        ]
        result = run_maintenance_rules(entities)
        assert result["total_entities"] == 2
        assert result["failures"] >= 1
