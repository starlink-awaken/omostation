"""Tests for SSOT patterns base module (patterns/base.py).

Covers: CheckResult, DerivationReport, BasePattern abstractness, DependencyValidator.
"""

import pytest
from sot_bridge.ssot_kernel.meta_model import DomainConfig, Rule
from sot_bridge.ssot_kernel.patterns.base import (
    BaseChecker,
    BasePattern,
    CheckResult,
    DependencyValidator,
    DerivationReport,
)


class TestCheckResult:
    def test_default_severity(self):
        r = CheckResult(protocol_id="R-001", name="Test", passed=True)
        assert r.severity == "WARN"

    def test_default_lists(self):
        r = CheckResult(protocol_id="R-001", name="Test", passed=True)
        assert r.details == []
        assert r.fixes == []

    def test_full_creation(self):
        r = CheckResult(
            protocol_id="R-001",
            name="Test",
            passed=False,
            severity="BLOCKER",
            details=["Error"],
            fixes=["Fix"],
        )
        assert r.severity == "BLOCKER"
        assert r.details == ["Error"]
        assert r.fixes == ["Fix"]


class TestDerivationReport:
    def test_defaults(self):
        r = DerivationReport()
        assert r.total_rules == 0
        assert r.passed == 0
        assert r.all_passed

    def test_summary_line(self):
        r = DerivationReport(passed=5, blocker=1, error=2, warn=0)
        line = r.summary_line
        assert "5" in line
        assert "1" in line
        assert "2" in line

    def test_all_passed_true(self):
        r = DerivationReport(blocker=0, error=0, all_passed=True)
        assert r.all_passed

    def test_all_passed_false_explicit(self):
        r = DerivationReport(blocker=1, error=0, all_passed=False)
        assert not r.all_passed


class TestBasePattern:
    def test_abstract_cannot_instantiate(self):
        """BasePattern is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BasePattern()


class TestBaseChecker:
    def test_abstract_cannot_instantiate(self):
        """BaseChecker is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseChecker()


class TestDependencyValidator:
    def test_no_deps_no_missing(self):
        config = DomainConfig()
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
        config = DomainConfig()
        validator = DependencyValidator(config)
        rule = Rule(
            id="R-002",
            pattern="test",
            premises=[{"condition": 'fact_ratio("DAT-001", "MISSING-DAT")'}],
        )
        result = validator.validate_rule(rule)
        assert result is not None
        assert not result.passed
