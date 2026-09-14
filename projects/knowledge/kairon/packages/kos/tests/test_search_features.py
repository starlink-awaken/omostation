"""Tests for KOS search features: suggestions, clustering, related searches, history."""

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"

sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))

from kos.search_features import SearchFeatures


class TestSearchSuggestions:
    """Test search suggestion feature."""

    def test_suggest_returns_results(self):
        features = SearchFeatures()
        result = features.suggest("test", limit=5)
        assert "suggestions" in result
        assert "prefix" in result
        assert result["prefix"] == "test"

    def test_suggest_chinese(self):
        features = SearchFeatures()
        result = features.suggest("数字", limit=5)
        assert result["count"] >= 0

    def test_suggest_empty_prefix(self):
        features = SearchFeatures()
        result = features.suggest("", limit=5)
        assert result["suggestions"] == []

    def test_suggest_limit(self):
        features = SearchFeatures()
        result = features.suggest("test", limit=3)
        assert result["count"] <= 3


class TestSearchClustering:
    """Test search result clustering."""

    def test_cluster_empty_results(self):
        features = SearchFeatures()
        result = features.cluster([])
        assert result["clusters"] == []
        assert result["ungrouped"] == []

    def test_cluster_with_results(self):
        features = SearchFeatures()
        # Mock results with doc_ids
        mock_results = [
            {"doc_id": "test1", "title": "Test 1"},
            {"doc_id": "test2", "title": "Test 2"},
        ]
        result = features.cluster(mock_results)
        assert "clusters" in result
        assert "ungrouped" in result


class TestRelatedSearches:
    """Test related search feature."""

    def test_related_returns_results(self):
        features = SearchFeatures()
        result = features.related("test", limit=5)
        assert "related" in result
        assert "query" in result

    def test_related_chinese(self):
        features = SearchFeatures()
        result = features.related("数字化", limit=5)
        assert result["count"] >= 0

    def test_related_short_query(self):
        features = SearchFeatures()
        result = features.related("a", limit=5)
        assert result["related"] == []


class TestSearchHistory:
    """Test search history feature."""

    def test_history_add(self):
        features = SearchFeatures()
        result = features.history("add", query="test_query")
        assert result["action"] == "add"
        assert result["query"] == "test_query"

    def test_history_list(self):
        features = SearchFeatures()
        features.history("add", query="test_list")
        result = features.history("list")
        assert "history" in result
        assert result["count"] > 0

    def test_history_clear(self):
        features = SearchFeatures()
        features.history("add", query="test_clear")
        result = features.history("clear")
        assert result["action"] == "clear"
        assert result["count"] == 0

    def test_history_popular(self):
        features = SearchFeatures()
        features.history("add", query="popular_query")
        features.history("add", query="popular_query")
        result = features.history("popular")
        assert "popular" in result


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
