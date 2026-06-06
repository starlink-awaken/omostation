"""Tests for MCP Registry QualityScorer — composite quality evaluation."""

from datetime import UTC, datetime, timedelta

from agora.mcp_registry.evaluator import QualityScorer

# ── Tests: normalize_stars ─────────────────────────────────────────────


class TestNormalizeStars:
    def test_5000_plus(self):
        assert QualityScorer.normalize_stars(5000) == 1.0
        assert QualityScorer.normalize_stars(10000) == 1.0

    def test_1000_4999(self):
        assert QualityScorer.normalize_stars(1000) == 0.9
        assert QualityScorer.normalize_stars(4999) == 0.9

    def test_500_999(self):
        assert QualityScorer.normalize_stars(500) == 0.8
        assert QualityScorer.normalize_stars(999) == 0.8
        assert QualityScorer.normalize_stars(750) == 0.8

    def test_100_499(self):
        assert QualityScorer.normalize_stars(100) == 0.6
        assert QualityScorer.normalize_stars(499) == 0.6

    def test_10_99(self):
        assert QualityScorer.normalize_stars(10) == 0.4
        assert QualityScorer.normalize_stars(99) == 0.4

    def test_1_9(self):
        assert QualityScorer.normalize_stars(1) == 0.2
        assert QualityScorer.normalize_stars(9) == 0.2

    def test_zero(self):
        assert QualityScorer.normalize_stars(0) == 0.0

    def test_negative(self):
        assert QualityScorer.normalize_stars(-1) == 0.0


# ── Tests: normalize_freshness ─────────────────────────────────────────


class TestNormalizeFreshness:
    def test_none(self):
        """None input should return default 0.5."""
        assert QualityScorer.normalize_freshness(None) == 0.5

    def test_within_30_days(self):
        dt = (datetime.now(UTC) - timedelta(days=15)).isoformat()
        assert QualityScorer.normalize_freshness(dt) == 1.0

    def test_within_90_days(self):
        dt = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        assert QualityScorer.normalize_freshness(dt) == 0.9

    def test_within_180_days(self):
        dt = (datetime.now(UTC) - timedelta(days=120)).isoformat()
        assert QualityScorer.normalize_freshness(dt) == 0.7

    def test_within_365_days(self):
        dt = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        assert QualityScorer.normalize_freshness(dt) == 0.5

    def test_over_365_days(self):
        dt = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        assert QualityScorer.normalize_freshness(dt) == 0.2

    def test_z_suffix(self):
        """ISO format with Z suffix should be handled."""
        dt = (datetime.now(UTC) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
        assert QualityScorer.normalize_freshness(dt) == 1.0

    def test_invalid_format(self):
        """Invalid date format should return default 0.5."""
        assert QualityScorer.normalize_freshness("not-a-date") == 0.5

    def test_empty_string(self):
        assert QualityScorer.normalize_freshness("") == 0.5


# ── Tests: normalize_version ───────────────────────────────────────────


class TestNormalizeVersion:
    def test_none(self):
        assert QualityScorer.normalize_version(None) == 0.3

    def test_full_semver(self):
        assert QualityScorer.normalize_version("1.2.3") == 1.0

    def test_v_prefix(self):
        assert QualityScorer.normalize_version("v1.2.3") == 1.0

    def test_major_minor(self):
        assert QualityScorer.normalize_version("1.2") == 0.7

    def test_just_major(self):
        assert QualityScorer.normalize_version("1") == 0.4

    def test_empty_string(self):
        assert QualityScorer.normalize_version("") == 0.3

    def test_long_version(self):
        assert QualityScorer.normalize_version("1.2.3.4") == 1.0  # >= 3 parts


# ── Tests: normalize_local_usage ───────────────────────────────────────


class TestNormalizeLocalUsage:
    def test_100_plus(self):
        assert QualityScorer.normalize_local_usage(100) == 1.0
        assert QualityScorer.normalize_local_usage(500) == 1.0

    def test_50_99(self):
        assert QualityScorer.normalize_local_usage(50) == 0.9
        assert QualityScorer.normalize_local_usage(99) == 0.9

    def test_20_49(self):
        assert QualityScorer.normalize_local_usage(20) == 0.7
        assert QualityScorer.normalize_local_usage(49) == 0.7

    def test_10_19(self):
        assert QualityScorer.normalize_local_usage(10) == 0.5
        assert QualityScorer.normalize_local_usage(19) == 0.5

    def test_3_9(self):
        assert QualityScorer.normalize_local_usage(3) == 0.3
        assert QualityScorer.normalize_local_usage(9) == 0.3

    def test_1_2(self):
        assert QualityScorer.normalize_local_usage(1) == 0.1
        assert QualityScorer.normalize_local_usage(2) == 0.1

    def test_zero(self):
        assert QualityScorer.normalize_local_usage(0) == 0.0


# ── Tests: composite evaluate ──────────────────────────────────────────


class TestEvaluate:
    def test_high_quality(self):
        """A tool with maximum scores should approach 1.0."""
        score = QualityScorer.evaluate(
            {
                "stars": 5000,
                "version": "2.0.0",
                "usage_count": 100,
                "metadata": {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "verified": True,
                },
                "success_rate": 1.0,
            }
        )
        # Should be very close to 1.0 (all weights sum to 1.0)
        assert 0.9 <= score <= 1.0

    def test_low_quality(self):
        """A tool with minimum scores should approach 0.0."""
        score = QualityScorer.evaluate(
            {
                "stars": 0,
                "version": "",
                "usage_count": 0,
                "metadata": {},
                "success_rate": 0.0,
            }
        )
        assert 0.0 <= score <= 0.5

    def test_recency_decay_old(self):
        """Tools not used for >30 days should get a 0.8 multiplier."""
        score = QualityScorer.evaluate(
            {
                "stars": 100,
                "version": "1.0.0",
                "usage_count": 10,
                "last_used": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
                "metadata": {"updated_at": datetime.now(UTC).isoformat()},
                "success_rate": 0.5,
            }
        )
        # Score should be reduced by decay
        assert 0.0 <= score <= 0.8

    def test_recency_decay_recent(self):
        """Tools used within 30 days should NOT be penalized."""
        score = QualityScorer.evaluate(
            {
                "stars": 100,
                "version": "1.0.0",
                "usage_count": 10,
                "last_used": datetime.now(UTC).isoformat(),
                "metadata": {"updated_at": datetime.now(UTC).isoformat()},
                "success_rate": 0.5,
            }
        )
        assert score > 0

    def test_recency_decay_invalid_date(self):
        """Invalid last_used format should not raise."""
        score = QualityScorer.evaluate(
            {
                "stars": 100,
                "version": "1.0.0",
                "usage_count": 10,
                "last_used": "not-a-date",
                "metadata": {},
                "success_rate": 0.5,
            }
        )
        assert score > 0

    def test_missing_keys(self):
        """Evaluate should handle missing optional keys gracefully."""
        score = QualityScorer.evaluate({})
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_minimal_input(self):
        """Evaluate with just a name should not crash."""
        score = QualityScorer.evaluate({"name": "test-tool"})
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_weight_sum(self):
        """Weights should sum to 1.0 for correct scoring."""
        total = sum(QualityScorer.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"


# ── Tests: evaluate_batch ──────────────────────────────────────────────


class TestEvaluateBatch:
    def test_batch_sorts_by_score(self):
        tools = [
            {
                "stars": 5000,
                "version": "2.0.0",
                "metadata": {},
                "usage_count": 100,
                "success_rate": 1.0,
                "name": "best",
            },
            {"stars": 0, "version": "", "metadata": {}, "usage_count": 0, "success_rate": 0.0, "name": "worst"},
            {"stars": 100, "version": "1.0.0", "metadata": {}, "usage_count": 10, "success_rate": 0.5, "name": "mid"},
        ]
        result = QualityScorer.evaluate_batch(tools)
        assert len(result) == 3
        assert result[0]["name"] == "best"
        assert result[-1]["name"] == "worst"

    def test_batch_empty(self):
        result = QualityScorer.evaluate_batch([])
        assert result == []

    def test_batch_adds_quality_score(self):
        tools = [{"name": "t1", "stars": 100, "metadata": {}, "usage_count": 0, "success_rate": 0.5}]
        result = QualityScorer.evaluate_batch(tools)
        assert "quality_score" in result[0]
        assert isinstance(result[0]["quality_score"], float)
