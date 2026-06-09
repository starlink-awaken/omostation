"""Tests for SSOT rule engine (engine.py).

Covers: CheckerRegistry, RuleEngine, execution, dependency validation.
"""

from sot_bridge.ssot_kernel.engine import CheckerRegistry, RuleEngine
from sot_bridge.ssot_kernel.meta_model import DomainConfig, Entity, Fact, MetaType, Rule
from sot_bridge.ssot_kernel.patterns.base import (
    BasePattern,
    CheckResult,
    DependencyValidator,
    DerivationReport,
)

# ── Helper: a simple test pattern ───────────────────────────────────────────


class PassPattern(BasePattern):
    """A pattern that always passes."""

    @property
    def pattern_name(self) -> str:
        return "test_pass"

    def evaluate(self, rule, domain, context=None) -> CheckResult:
        return CheckResult(
            protocol_id=rule.id,
            name=rule.name or rule.id,
            passed=True,
            severity="INFO",
            details=["Always passes"],
        )


class FailPattern(BasePattern):
    """A pattern that always fails."""

    @property
    def pattern_name(self) -> str:
        return "test_fail"

    def evaluate(self, rule, domain, context=None) -> CheckResult:
        return CheckResult(
            protocol_id=rule.id,
            name=rule.name or rule.id,
            passed=False,
            severity="ERROR",
            details=["Always fails"],
        )


# ── Tests ───────────────────────────────────────────────────────────────────


class TestCheckerRegistry:
    def test_init_empty(self):
        """Registry starts empty before discovery."""
        registry = CheckerRegistry()
        assert registry.list_patterns() == []

    def test_register_and_get(self):
        registry = CheckerRegistry()
        pattern = PassPattern()
        registry.register("test_pass", pattern)
        assert registry.get("test_pass") is pattern
        assert "test_pass" in registry.list_patterns()

    def test_get_nonexistent(self):
        registry = CheckerRegistry()
        assert registry.get("nonexistent") is None

    def test_register_overwrites(self):
        registry = CheckerRegistry()
        p1 = PassPattern()
        p2 = PassPattern()
        registry.register("test_pass", p1)
        registry.register("test_pass", p2)
        assert registry.get("test_pass") is p2


class TestRuleEngine:
    def test_init_has_registry(self):
        engine = RuleEngine()
        assert hasattr(engine, "registry")
        assert isinstance(engine.registry, CheckerRegistry)

    def test_execute_no_rules(self):
        """Executing with no rules returns an empty report."""
        engine = RuleEngine()
        engine.registry = CheckerRegistry()  # clear built-in discovery
        config = DomainConfig()
        report = engine.execute(config)
        assert isinstance(report, DerivationReport)
        assert report.total_rules == 0
        assert report.all_passed

    def test_execute_with_registered_pattern(self):
        engine = RuleEngine()
        # Clear and register our pattern
        engine.registry = CheckerRegistry()
        engine.registry.register("test_pass", PassPattern())

        config = DomainConfig(
            domain={"name": "test"},
            rules=[Rule(id="R-001", pattern="test_pass", name="Test Rule")],
        )
        report = engine.execute(config)
        assert report.total_rules == 1
        assert report.passed == 1
        assert report.all_passed

    def test_execute_with_failing_pattern(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()
        engine.registry.register("test_fail", FailPattern())

        config = DomainConfig(
            domain={"name": "test"},
            rules=[Rule(id="R-001", pattern="test_fail", name="Fail Rule")],
        )
        report = engine.execute(config)
        assert report.total_rules == 1
        assert report.passed == 0
        assert not report.all_passed
        assert report.error == 1

    def test_execute_unknown_pattern_skips(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()

        config = DomainConfig(
            domain={"name": "test"},
            rules=[Rule(id="R-001", pattern="nonexistent", name="Unknown")],
        )
        report = engine.execute(config)
        assert report.total_rules == 1
        # Unknown patterns produce a WARN result with passed=True
        assert report.results[0].passed is True
        assert report.results[0].severity == "WARN"

    def test_execute_multiple_rules(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()
        engine.registry.register("test_pass", PassPattern())
        engine.registry.register("test_fail", FailPattern())

        config = DomainConfig(
            domain={"name": "test"},
            rules=[
                Rule(id="R-001", pattern="test_pass", name="Pass"),
                Rule(id="R-002", pattern="test_fail", name="Fail"),
                Rule(id="R-003", pattern="test_pass", name="Pass2"),
            ],
        )
        report = engine.execute(config)
        assert report.total_rules == 3
        assert report.passed == 2
        assert report.error == 1

    def test_execute_with_custom_rules_param(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()
        engine.registry.register("test_pass", PassPattern())

        config = DomainConfig(domain={"name": "test"})
        custom_rules = [Rule(id="C-001", pattern="test_pass", name="Custom")]
        report = engine.execute(config, rules=custom_rules)
        assert report.total_rules == 1

    def test_execute_with_context(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()
        engine.registry.register("test_pass", PassPattern())

        config = DomainConfig(
            domain={"name": "test"},
            rules=[Rule(id="R-001", pattern="test_pass", name="Test")],
        )
        report = engine.execute(config, context={"extra": "data"})
        assert report.total_rules == 1

    def test_execute_multiple_rounds(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()
        engine.registry.register("test_pass", PassPattern())

        config = DomainConfig(
            domain={"name": "test"},
            rules=[Rule(id="R-001", pattern="test_pass", name="Test")],
        )
        report = engine.execute(config, rounds=3)
        assert report.total_rules == 3  # 1 rule * 3 rounds
        assert report.passed == 3

    def test_execute_dependency_check(self):
        engine = RuleEngine()
        engine.registry = CheckerRegistry()
        engine.registry.register("test_pass", PassPattern())

        # Rule references non-existent entity via condition
        config = DomainConfig(
            domain={"name": "test"},
            rules=[
                Rule(
                    id="R-001",
                    pattern="test_pass",
                    name="Missing Dep",
                    premises=[{"condition": 'entity_attr("MISSING-ORG", "name")'}],
                )
            ],
        )
        report = engine.execute(config)
        # Dependency check should create a BLOCKER result
        assert report.total_rules == 1
        assert report.blocker == 1
        assert not report.all_passed


class TestDependencyValidator:
    def test_no_deps_no_missing(self):
        config = DomainConfig(
            entities=[
                Entity(
                    id="ORG-A",
                    name="A",
                    meta_type=MetaType.DOMAIN,
                    entity_type="Organization",
                )
            ],
        )
        validator = DependencyValidator(config)
        rule = Rule(id="R-001", pattern="test", premises=[])
        assert validator.validate_rule(rule) is None

    def test_missing_entity_attr_ref(self):
        config = DomainConfig()
        validator = DependencyValidator(config)
        rule = Rule(
            id="R-001",
            pattern="test",
            name="Test",
            premises=[{"condition": 'entity_attr("MISSING", "name")'}],
        )
        result = validator.validate_rule(rule)
        assert result is not None
        assert not result.passed
        assert result.severity == "BLOCKER"

    def test_missing_fact_ratio_ref(self):
        config = DomainConfig(
            facts=[Fact(id="DAT-001", title="Existing")],
        )
        validator = DependencyValidator(config)
        rule = Rule(
            id="R-002",
            pattern="test",
            premises=[{"condition": 'fact_ratio("DAT-001", "MISSING-DAT")'}],
        )
        result = validator.validate_rule(rule)
        assert result is not None
        assert not result.passed

    def test_existing_entity_attr_ref(self):
        config = DomainConfig(
            entities=[
                Entity(
                    id="ORG-A",
                    name="A",
                    meta_type=MetaType.DOMAIN,
                    entity_type="Organization",
                )
            ],
        )
        validator = DependencyValidator(config)
        rule = Rule(
            id="R-001",
            pattern="test",
            premises=[{"condition": 'entity_attr("ORG-A", "name")'}],
        )
        assert validator.validate_rule(rule) is None

    def test_prefix_exists(self):
        config = DomainConfig(
            entities=[
                Entity(
                    id="ORG-A",
                    name="A",
                    meta_type=MetaType.DOMAIN,
                    entity_type="Organization",
                )
            ],
        )
        validator = DependencyValidator(config)
        rule = Rule(
            id="R-003",
            pattern="test",
            premises=[{"condition": 'entity_exists("ORG-", "name")'}],
        )
        assert validator.validate_rule(rule) is None

    def test_prefix_missing(self):
        config = DomainConfig()
        validator = DependencyValidator(config)
        rule = Rule(
            id="R-004",
            pattern="test",
            premises=[{"condition": 'entity_exists("NON-", "name")'}],
        )
        result = validator.validate_rule(rule)
        assert result is not None
        assert not result.passed
