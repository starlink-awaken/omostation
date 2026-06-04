"""
Unit tests for honesty dimension (4P3V1L1H framework).

Tests all three sub-dimensions and core integration.
"""

import pytest

from omo_debt.honesty.completeness import CompletenessResult, calculate_completeness
from omo_debt.honesty.consistency import ConsistencyResult, calculate_consistency, detect_outlier
from omo_debt.honesty.core import (
    adjust_score_with_honesty,
    calculate_honesty_score,
)
from omo_debt.honesty.verifiability import (
    VerifiabilityResult,
    calculate_verifiability,
    count_claims,
    detect_cost_evidence,
    detect_frequency_evidence,
    detect_impact_evidence,
)


class TestHonestyCore:
    """Test core honesty score calculation."""

    def test_calculate_honesty_score_balanced(self):
        """Test balanced honesty score calculation."""
        result = calculate_honesty_score(
            completeness=7.0,
            consistency=6.5,
            verifiability=8.0,
        )

        # Formula: 0.40×7.0 + 0.35×6.5 + 0.25×8.0 = 2.8 + 2.275 + 2.0 = 7.075
        assert result.score == 7.08
        assert result.completeness == 7.0
        assert result.consistency == 6.5
        assert result.verifiability == 8.0

    def test_calculate_honesty_score_perfect(self):
        """Test perfect honesty score."""
        result = calculate_honesty_score(10.0, 10.0, 10.0)

        assert result.score == 10.0
        assert result.grade == "优秀"

    def test_calculate_honesty_score_poor(self):
        """Test poor honesty score."""
        result = calculate_honesty_score(2.0, 1.5, 3.0)

        # Formula: 0.40×2.0 + 0.35×1.5 + 0.25×3.0 = 0.8 + 0.525 + 0.75 = 2.075
        assert result.score == 2.08
        assert result.grade == "危险"

    def test_honesty_bonus_calculation(self):
        """Test honesty bonus calculation."""
        result = calculate_honesty_score(10.0, 10.0, 10.0)
        assert result.bonus == 0.25  # (10-5)/20 = 0.25

        result = calculate_honesty_score(5.0, 5.0, 5.0)
        assert result.bonus == 0.0  # (5-5)/20 = 0.0

        result = calculate_honesty_score(0.0, 0.0, 0.0)
        assert result.bonus == -0.25  # (0-5)/20 = -0.25

    def test_honesty_grade_classification(self):
        """Test honesty grade classification."""
        assert calculate_honesty_score(9.0, 9.0, 9.0).grade == "优秀"
        assert calculate_honesty_score(7.5, 7.0, 7.0).grade == "良好"
        assert calculate_honesty_score(5.5, 5.0, 5.5).grade == "一般"
        assert calculate_honesty_score(3.5, 3.0, 4.0).grade == "较差"
        assert calculate_honesty_score(2.0, 2.0, 2.0).grade == "危险"

    def test_adjust_score_with_honesty_boost(self):
        """Test score adjustment with high honesty (boost)."""
        # Perfect honesty (+25% boost)
        adjusted = adjust_score_with_honesty(8.0, 10.0)
        assert adjusted == 10.0  # 8.0 × 1.25 = 10.0

    def test_adjust_score_with_honesty_neutral(self):
        """Test score adjustment with average honesty (no change)."""
        adjusted = adjust_score_with_honesty(8.0, 5.0)
        assert adjusted == 8.0  # 8.0 × 1.0 = 8.0

    def test_adjust_score_with_honesty_penalty(self):
        """Test score adjustment with poor honesty (penalty)."""
        adjusted = adjust_score_with_honesty(8.0, 0.0)
        assert adjusted == 6.0  # 8.0 × 0.75 = 6.0

    def test_out_of_range_scores_rejected(self):
        """Test that out-of-range scores raise ValueError."""
        with pytest.raises(ValueError, match="completeness must be between 0 and 10"):
            calculate_honesty_score(11.0, 5.0, 5.0)

        with pytest.raises(ValueError, match="consistency must be between 0 and 10"):
            calculate_honesty_score(5.0, -1.0, 5.0)

        with pytest.raises(ValueError, match="verifiability must be between 0 and 10"):
            calculate_honesty_score(5.0, 5.0, 15.0)


class TestCompleteness:
    """Test completeness sub-dimension."""

    def test_calculate_completeness_perfect(self):
        """Test perfect completeness (all debts disclosed)."""
        result = calculate_completeness(
            project_path=".",
            debt_files=["src/main.py", "src/auth.py"],
            disclosed_issues=["#1", "#2", "#3"],
        )

        # Should have high completeness
        assert isinstance(result, CompletenessResult)
        assert 0 <= result.score <= 10
        assert result.debt_files_count == 2
        assert result.disclosed_issues == 3

    def test_calculate_completeness_no_data(self):
        """Test completeness with no debt data."""
        result = calculate_completeness(
            project_path=".",
            debt_files=[],
            disclosed_issues=[],
        )

        # Should have low completeness
        assert isinstance(result, CompletenessResult)
        assert result.debt_files_count == 0
        assert result.disclosed_issues == 0


class TestConsistency:
    """Test consistency sub-dimension."""

    def test_calculate_consistency_perfect(self):
        """Test perfect consistency (aligned with peers)."""
        result = calculate_consistency(
            self_rating=7.0,
            peer_avg=7.0,
            historical_scores=[7.0, 7.0, 7.0],
            similar_project_scores=[7.0, 7.1, 6.9],
        )

        assert isinstance(result, ConsistencyResult)
        assert result.score >= 9.0  # Should be very high
        assert result.deviation_score == 10.0  # Perfect alignment
        assert result.time_score == 10.0  # No volatility

    def test_calculate_consistency_outlier(self):
        """Test consistency with significant deviation."""
        result = calculate_consistency(
            self_rating=10.0,
            peer_avg=5.0,
            historical_scores=[10.0, 4.0, 9.0, 5.0],  # High volatility
        )

        assert isinstance(result, ConsistencyResult)
        assert result.deviation_score == 0.0  # |10-5|×2 = 10, max(0, 10-10) = 0
        assert result.time_score < 5.0  # High volatility

    def test_detect_outlier_true(self):
        """Test outlier detection (positive)."""
        is_outlier = detect_outlier(10.0, [7.0, 7.5, 8.0, 7.2])
        assert is_outlier is True

    def test_detect_outlier_false(self):
        """Test outlier detection (negative)."""
        is_outlier = detect_outlier(7.3, [7.0, 7.5, 8.0, 7.2])
        assert is_outlier is False


class TestVerifiability:
    """Test verifiability sub-dimension."""

    def test_calculate_verifiability_full_evidence(self):
        """Test verifiability with complete evidence."""
        result = calculate_verifiability(
            has_impact_evidence=True,
            has_frequency_evidence=True,
            has_cost_evidence=True,
            evidence_commits=["abc123", "def456"],
            evidence_issues=["#42"],
            evidence_refs=["doc/arch.md"],
            total_claims=4,
        )

        assert isinstance(result, VerifiabilityResult)
        assert result.evidence_score == 10.0  # All 3 factors
        assert result.traceability_score == 10.0  # 4 refs / 4 claims = 1.0
        assert result.score == 10.0  # 0.6×10 + 0.4×10 = 10

    def test_calculate_verifiability_partial_evidence(self):
        """Test verifiability with partial evidence."""
        result = calculate_verifiability(
            has_impact_evidence=True,
            has_frequency_evidence=True,
            has_cost_evidence=False,
            evidence_commits=["abc123"],
            total_claims=3,
        )

        assert result.evidence_score == 6.0  # 2/3 factors
        # trace = 1 ref / 3 claims = 0.33, score = 3.33
        assert 3.0 <= result.traceability_score <= 4.0
        # 0.6×6 + 0.4×3.33 = 3.6 + 1.33 = 4.93
        assert 4.5 <= result.score <= 5.5

    def test_calculate_verifiability_no_evidence(self):
        """Test verifiability with no evidence."""
        result = calculate_verifiability(
            has_impact_evidence=False,
            has_frequency_evidence=False,
            has_cost_evidence=False,
            total_claims=5,
        )

        assert result.evidence_score == 0.0
        assert result.traceability_score == 0.0
        assert result.score == 0.0

    def test_detect_impact_evidence(self):
        """Test impact evidence detection."""
        # Positive cases
        assert detect_impact_evidence("causes crash error", ["src/main.py"])
        assert detect_impact_evidence("security vulnerability", [])

        # Negative case
        assert not detect_impact_evidence("refactor needed", [])

    def test_detect_frequency_evidence(self):
        """Test frequency evidence detection."""
        # Positive cases
        assert detect_frequency_evidence("happens daily", [], [])
        assert detect_frequency_evidence("occurs often", ["a", "b"], [])

        # Negative case
        assert not detect_frequency_evidence("single incident", [], [])

    def test_detect_cost_evidence(self):
        """Test cost evidence detection."""
        # Positive cases
        assert detect_cost_evidence("estimated 2 days effort", [])
        assert detect_cost_evidence("complex and risky", [])

        # Negative case
        assert not detect_cost_evidence("needs work", [])

    def test_count_claims(self):
        """Test claim counting."""
        desc = "This is a problem. It will cause errors. Performance will degrade."
        count = count_claims(desc)
        assert count >= 2  # At least 2 assertion sentences


class TestIntegration:
    """Integration tests for full honesty assessment."""

    def test_full_honesty_assessment_pipeline(self):
        """Test complete honesty assessment workflow."""
        # 1. Calculate completeness
        comp = calculate_completeness(
            project_path=".",
            debt_files=["src/main.py"],
            disclosed_issues=["#1", "#2"],
        )

        # 2. Calculate consistency
        cons = calculate_consistency(
            self_rating=7.5,
            peer_avg=7.0,
            historical_scores=[7.2, 7.5, 7.8],
        )

        # 3. Calculate verifiability
        verif = calculate_verifiability(
            has_impact_evidence=True,
            has_frequency_evidence=True,
            has_cost_evidence=False,
            evidence_commits=["abc123"],
            evidence_issues=["#42"],
            total_claims=2,
        )

        # 4. Calculate overall honesty
        honesty = calculate_honesty_score(
            completeness=comp.score,
            consistency=cons.score,
            verifiability=verif.score,
        )

        # 5. Adjust debt score with honesty
        base_score = 8.0
        adjusted = adjust_score_with_honesty(base_score, honesty.score)

        # Assertions
        assert 0 <= honesty.score <= 10
        assert adjusted != base_score  # Should be adjusted
        assert honesty.grade in ["优秀", "良好", "一般", "较差", "危险"]

    def test_honesty_prevents_priority_inflation(self):
        """Test that low honesty downgrades inflated priorities."""
        # High impact debt with poor honesty
        base_score = 9.0  # Would be P0 (≥7.0)
        honesty_score = 2.0  # Poor honesty

        adjusted = adjust_score_with_honesty(base_score, honesty_score)

        # 9.0 × (1 + (2-5)/20) = 9.0 × 0.85 = 7.65
        assert adjusted < base_score
        assert 7.5 <= adjusted <= 7.7

    def test_honesty_rewards_thorough_disclosure(self):
        """Test that high honesty boosts well-documented debts."""
        # Moderate debt with excellent honesty
        base_score = 6.0  # Would be P1 (5.0-6.9)
        honesty_score = 9.5  # Excellent honesty

        adjusted = adjust_score_with_honesty(base_score, honesty_score)

        # 6.0 × (1 + (9.5-5)/20) = 6.0 × 1.225 = 7.35
        assert adjusted > base_score
        assert adjusted >= 7.0  # Promoted to P0 threshold
