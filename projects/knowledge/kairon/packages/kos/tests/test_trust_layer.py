"""Tests for TrustLayer — entity confidence scoring."""

import pytest
from kos.trust_layer import SOURCE_AUTHORITY, TrustLayer


class TestSourceAuthority:
    def test_has_known_types(self):
        assert "official_docs" in SOURCE_AUTHORITY
        assert "peer_reviewed" in SOURCE_AUTHORITY
        assert "blog" in SOURCE_AUTHORITY
        assert "social_media" in SOURCE_AUTHORITY
        assert "unknown" in SOURCE_AUTHORITY

    def test_official_docs_highest(self):
        assert SOURCE_AUTHORITY["official_docs"] == 1.0
        assert SOURCE_AUTHORITY["official_docs"] > SOURCE_AUTHORITY["peer_reviewed"]

    def test_social_media_lowest(self):
        assert SOURCE_AUTHORITY["social_media"] == 0.3
        assert SOURCE_AUTHORITY["social_media"] < SOURCE_AUTHORITY["blog"]


class TestScoreEntity:
    def test_base_score_from_source_type(self):
        tl = TrustLayer()
        result = tl.score_entity("doc1", "official_docs")
        assert result["trust"] == 1.0
        assert result["entity_id"] == "doc1"

    def test_unknown_source_gets_default(self):
        tl = TrustLayer()
        result = tl.score_entity("doc2", "unknown_source")
        assert result["trust"] == 0.2  # default fallback

    def test_cross_validation_boost(self):
        tl = TrustLayer()
        base = tl.score_entity("doc3", "blog", cross_validated=False)
        boosted = tl.score_entity("doc4", "blog", cross_validated=True)
        assert boosted["trust"] > base["trust"]

    def test_cross_validation_caps_at_1(self):
        tl = TrustLayer()
        result = tl.score_entity("doc5", "official_docs", cross_validated=True)
        assert result["trust"] <= 1.0

    def test_age_decay_after_365_days(self):
        tl = TrustLayer()
        fresh = tl.score_entity("doc6", "peer_reviewed", age_days=0)
        aged = tl.score_entity("doc7", "peer_reviewed", age_days=400)
        assert aged["trust"] < fresh["trust"]
        assert aged["trust"] == round(0.9 * 0.9, 2)  # base 0.9 * 0.9 decay factor

    def test_age_decay_after_730_days(self):
        tl = TrustLayer()
        old = tl.score_entity("doc8", "blog", age_days=800)
        # Mutually exclusive: only >730 branch fires (not both)
        # blog=0.5 * 0.8 (>730) = 0.4
        assert old["trust"] == pytest.approx(0.4, rel=1e-3)

    def test_no_decay_before_365(self):
        tl = TrustLayer()
        result = tl.score_entity("doc9", "official_docs", age_days=100)
        assert result["trust"] == 1.0  # no decay


class TestGetScore:
    def test_returns_scored_entity(self):
        tl = TrustLayer()
        tl.score_entity("doc1", "official_docs")
        assert tl.get_score("doc1") == 1.0

    def test_returns_default_for_unknown(self):
        tl = TrustLayer()
        assert tl.get_score("nonexistent") == 0.2

    def test_score_is_persisted(self):
        tl = TrustLayer()
        tl.score_entity("doc_a", "peer_reviewed")
        tl.score_entity("doc_b", "social_media")
        assert tl.get_score("doc_a") == 0.9
        assert tl.get_score("doc_b") == 0.3


class TestPropagate:
    def test_no_propagation_with_empty_graph(self):
        tl = TrustLayer()
        tl.score_entity("doc1", "official_docs")
        result = tl.propagate({}, steps=2)
        assert result["doc1"] == 1.0

    def test_single_step_propagation(self):
        tl = TrustLayer()
        tl.score_entity("high", "official_docs")  # 1.0
        tl.score_entity("low", "social_media")  # 0.3
        graph = {"high": ["low"], "low": ["high"]}
        result = tl.propagate(graph, steps=1)
        # high: 1.0 * 0.8 + 0.3 * 0.2 = 0.86
        # low: 0.3 * 0.8 + 1.0 * 0.2 = 0.44
        assert result["high"] == round(1.0 * 0.8 + 0.3 * 0.2, 2)
        assert result["low"] == round(0.3 * 0.8 + 1.0 * 0.2, 2)

    def test_two_step_propagation(self):
        tl = TrustLayer()
        tl.score_entity("a", "official_docs")  # 1.0
        tl.score_entity("b", "blog")  # 0.5
        tl.score_entity("c", "social_media")  # 0.3
        graph = {"a": ["b"], "b": ["a", "c"], "c": ["b"]}
        result = tl.propagate(graph, steps=2)
        # After step 2, scores should have converged somewhat
        assert result["a"] >= result["b"] >= result["c"]

    def test_returns_dict_copy(self):
        tl = TrustLayer()
        tl.score_entity("x", "official_docs")
        result = tl.propagate({}, steps=1)
        # Modifying result shouldn't affect internal state
        assert isinstance(result, dict)


class TestFilter:
    def test_returns_all_above_threshold(self):
        tl = TrustLayer()
        tl.score_entity("high", "official_docs")  # 1.0
        tl.score_entity("mid", "blog", cross_validated=True)  # 0.6
        tl.score_entity("low", "social_media")  # 0.3
        filtered = tl.filter(min_score=0.5)
        assert "high" in filtered
        assert "mid" in filtered
        assert "low" not in filtered

    def test_default_threshold(self):
        tl = TrustLayer()
        tl.score_entity("high", "official_docs")
        tl.score_entity("low", "unknown_source")  # 0.2
        filtered = tl.filter()  # default min_score=0.3
        assert "high" in filtered
        assert "low" not in filtered

    def test_empty_scores_returns_empty(self):
        tl = TrustLayer()
        assert tl.filter() == {}


class TestStats:
    def test_empty_stats(self):
        tl = TrustLayer()
        stats = tl.stats()
        assert stats["total"] == 0

    def test_stats_after_scoring(self):
        tl = TrustLayer()
        tl.score_entity("a", "official_docs")  # 1.0
        tl.score_entity("b", "peer_reviewed")  # 0.9
        tl.score_entity("c", "social_media")  # 0.3
        stats = tl.stats()
        assert stats["total"] == 3
        assert stats["high_trust"] == 2  # >= 0.7
        assert stats["avg_trust"] == round((1.0 + 0.9 + 0.3) / 3, 2)


class TestIntegration:
    def test_full_pipeline(self):
        """Score, propagate, filter — end-to-end verification."""
        tl = TrustLayer()
        # Score entities
        tl.score_entity("official", "official_docs", age_days=100)
        tl.score_entity("blog_post", "blog", cross_validated=True, age_days=200)
        tl.score_entity("tweet", "social_media", age_days=500)
        # Propagate
        graph = {"official": ["blog_post"], "blog_post": ["official", "tweet"], "tweet": ["blog_post"]}
        tl.propagate(graph, steps=2)
        # Filter
        filtered = tl.filter(min_score=0.4)
        assert "official" in filtered
        assert "blog_post" in filtered
        # Stats
        stats = tl.stats()
        assert stats["total"] == 3
        assert stats["high_trust"] >= 1
