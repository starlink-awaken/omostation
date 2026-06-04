"""Unit tests for legacy dimension (4P3V1L1H L)."""

import pytest
from click.testing import CliRunner

from omo_debt.cli import cli
from omo_debt.legacy.age import calculate_age_score
from omo_debt.legacy.core import adjust_score_with_legacy, calculate_legacy_score
from omo_debt.legacy.migration import calculate_migration_path_score
from omo_debt.legacy.resistance import calculate_refactoring_resistance_score


class TestLegacyCore:
    """Test legacy score aggregation and priority adjustment."""

    def test_calculate_legacy_score_weighted(self):
        """Legacy score should use 40/35/25 weighted average."""
        result = calculate_legacy_score(age_score=9.0, resistance_score=6.0, path_score=8.0)
        assert result == 7.7  # 9*0.4 + 6*0.35 + 8*0.25 = 7.7

    def test_adjust_score_with_legacy_boost(self):
        """High legacy score should boost priority by 15%."""
        adjusted = adjust_score_with_legacy(base_score=80.0, legacy_score=8.5)
        assert adjusted == 92.0

    def test_adjust_score_with_legacy_penalty(self):
        """Low legacy score should reduce priority by 10%."""
        adjusted = adjust_score_with_legacy(base_score=80.0, legacy_score=3.5)
        assert adjusted == 72.0

    def test_adjust_score_with_legacy_neutral(self):
        """Middle legacy score should keep priority unchanged."""
        adjusted = adjust_score_with_legacy(base_score=80.0, legacy_score=6.0)
        assert adjusted == 80.0

    def test_legacy_score_out_of_range_rejected(self):
        """Out-of-range sub scores should raise ValueError."""
        with pytest.raises(ValueError, match="age_score must be between 0 and 10"):
            calculate_legacy_score(age_score=11.0, resistance_score=5.0, path_score=5.0)


class TestLegacySubDimensions:
    """Test legacy sub-dimension helpers."""

    def test_age_score_for_new_debt(self):
        """New debt (<3 months) should have high age score."""
        score = calculate_age_score(age_months=2, stable_months=0)
        assert score == 9.5

    def test_age_score_with_long_stability_penalty(self):
        """Long-stable old debt should be penalized by 1 point."""
        score = calculate_age_score(age_months=40, stable_months=18)
        assert score == 3.0

    def test_refactoring_resistance_weighted(self):
        """Resistance score should use weighted dependency/coupling/risk."""
        score = calculate_refactoring_resistance_score(
            dependency_score=8.0,
            coupling_score=6.0,
            technical_risk=7.0,
        )
        assert score == 7.0  # 8*0.4 + 6*0.4 + 7*0.2

    def test_migration_path_weighted(self):
        """Path score should use weighted clarity/incremental/docs."""
        score = calculate_migration_path_score(
            solution_clarity=7.0,
            incremental=True,
            has_migration_docs=False,
        )
        assert score == 6.7  # 7*0.5 + 8*0.3 + 4*0.2


class TestLegacyCLI:
    """Test legacy CLI command."""

    def test_assess_legacy_command(self):
        """CLI should provide assess-legacy command with computed score."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "assess-legacy",
                "--age-months",
                "2",
                "--stable-months",
                "0",
                "--dependency-score",
                "8",
                "--coupling-score",
                "6",
                "--technical-risk",
                "7",
                "--solution-clarity",
                "7",
                "--incremental",
                "--no-migration-docs",
                "--base-priority",
                "80",
            ],
        )
        assert result.exit_code == 0
        assert "Legacy Score" in result.output
        assert "7.92" in result.output
        assert "Adjusted Priority" in result.output

    def test_assess_legacy_rejects_base_priority_out_of_range(self):
        """CLI should reject base priority outside 0-100."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "assess-legacy",
                "--age-months",
                "2",
                "--stable-months",
                "0",
                "--dependency-score",
                "8",
                "--coupling-score",
                "6",
                "--technical-risk",
                "7",
                "--solution-clarity",
                "7",
                "--incremental",
                "--no-migration-docs",
                "--base-priority",
                "120",
            ],
        )
        assert result.exit_code == 1
        assert "base_priority must be between 0 and 100" in result.output

    def test_assess_legacy_clamps_adjusted_priority_to_100(self):
        """CLI should cap adjusted priority at 100."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "assess-legacy",
                "--age-months",
                "1",
                "--stable-months",
                "0",
                "--dependency-score",
                "10",
                "--coupling-score",
                "10",
                "--technical-risk",
                "10",
                "--solution-clarity",
                "10",
                "--incremental",
                "--has-migration-docs",
                "--base-priority",
                "95",
            ],
        )
        assert result.exit_code == 0
        assert "Adjusted Priority" in result.output
        assert "100.00" in result.output
