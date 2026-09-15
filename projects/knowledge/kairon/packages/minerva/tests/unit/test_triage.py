"""Tests for TriageRouter classification."""

from unittest.mock import AsyncMock

import pytest


class TestTriageRouter:
    """Tests for the triage router."""

    def test_rule_classify_basic(self):
        """Test rule-based classification with a simple query."""
        from minerva.triage.router import TriageRouter

        router = TriageRouter(llm_client=None)
        scores = router._rule_classify("What is Python?")

        assert 1 <= scores["domain_complexity"] <= 5
        assert 1 <= scores["timeliness"] <= 5
        assert 1 <= scores["depth_required"] <= 5
        assert 1 <= scores["multi_source"] <= 5
        assert 1 <= scores["privacy_sensitivity"] <= 5
        # Simple question should have low depth
        assert scores["depth_required"] <= 3

    def test_rule_classify_technical(self):
        """Test rule-based classification with technical query."""
        from minerva.triage.router import TriageRouter

        router = TriageRouter(llm_client=None)
        scores = router._rule_classify(
            "Compare the transformer architecture optimization algorithms for distributed training"
        )

        # Should score higher: "architecture", "transformer", "optimization", "distributed", "training"
        # = 5 tech terms → domain = 1 + 5//3 = 2
        assert scores["domain_complexity"] >= 2
        # "compare" is a depth keyword
        assert scores["depth_required"] >= 3

    def test_boost_patterns(self):
        """Test keyword boost patterns."""
        from minerva.triage.router import TriageRouter

        router = TriageRouter(llm_client=None)
        base = {
            "domain_complexity": 2,
            "timeliness": 2,
            "depth_required": 2,
            "multi_source": 2,
            "privacy_sensitivity": 1,
        }

        # "compare" should boost depth
        boosted = router._apply_boosts("compare X vs Y and analyze differences", base)
        assert boosted["depth_required"] > 2

        # "latest" should boost timeliness
        boosted = router._apply_boosts("latest research on AI", base)
        assert boosted["timeliness"] > 2

        # "paper" should boost multi_source
        boosted = router._apply_boosts("academic papers on deep learning", base)
        assert boosted["multi_source"] > 2

    def test_privacy_override(self):
        """Test that privacy >= 4 forces local-only (L1 max)."""
        from minerva.triage.router import ResearchLevel, TriageRouter

        router = TriageRouter(llm_client=None)
        scores = {
            "domain_complexity": 5,
            "timeliness": 5,
            "depth_required": 5,
            "multi_source": 5,
            "privacy_sensitivity": 4,
        }

        level = router._total_to_level(100.0, scores)  # total would be L4 normally
        assert level in (ResearchLevel.L0, ResearchLevel.L1)

    def test_extract_json(self):
        """Test JSON extraction from LLM responses."""
        from minerva.triage.router import TriageRouter

        # With markdown code block
        text = '```json\n{"domain_complexity": 3, "timeliness": 2}\n```'
        result = TriageRouter._extract_json(text)
        assert "domain_complexity" in result

        # Bare JSON
        text = '{"domain_complexity": 3, "timeliness": 2}'
        result = TriageRouter._extract_json(text)
        assert "domain_complexity" in result

    @pytest.mark.asyncio
    async def test_llm_classify_mock(self):
        """Test LLM classification with mocked client."""
        from minerva.triage.router import TriageRouter

        mock_client = AsyncMock()
        mock_client.generate.return_value = '{"domain_complexity": 3, "timeliness": 2, "depth_required": 4, "multi_source": 3, "privacy_sensitivity": 1}'

        router = TriageRouter(llm_client=mock_client)
        scores = await router._llm_classify("Analyze transformer architecture evolution")

        assert scores["domain_complexity"] == 3
        assert scores["timeliness"] == 2
        assert scores["depth_required"] == 4
        assert scores["multi_source"] == 3
        assert scores["privacy_sensitivity"] == 1
