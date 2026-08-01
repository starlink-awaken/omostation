"""knowledge_activation 单元测试."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cockpit.knowledge_activation import (
    ActivationContext,
    format_recommendations,
    get_top_suggestions,
    recommend_for_context,
)


class TestRecommendForContext:
    """知识推荐."""

    @patch("cockpit.knowledge_activation.kos_search")
    def test_returns_results(self, mock_search):
        mock_search.return_value = {
            "results": [
                {"id": "d1", "title": "文档1", "score": 0.9},
                {"id": "d2", "title": "文档2", "score": 0.8},
            ]
        }
        results = recommend_for_context(ActivationContext.RESEARCH, "借调总结")
        assert len(results) == 2
        assert results[0]["title"] == "文档1"

    @patch("cockpit.knowledge_activation.kos_search")
    def test_kos_unavailable_returns_empty(self, mock_search):
        mock_search.return_value = {"error:": "fail", "results": []}
        results = recommend_for_context(ActivationContext.NOTE)
        assert results == []

    @patch("cockpit.knowledge_activation.kos_search")
    def test_limit_respected(self, mock_search):
        mock_search.return_value = {"results": [{"title": f"d{i}"} for i in range(10)]}
        recommend_for_context(ActivationContext.DOCUMENT, limit=3)
        # kos_search is called with limit=3
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        # limit may be positional or keyword
        assert call_args[1].get("limit") == 3 or (len(call_args[0]) > 1 and call_args[0][1] == 3)


class TestFormatRecommendations:
    """格式化输出."""

    def test_empty_results(self):
        assert format_recommendations([], ActivationContext.NOTE) == ""

    def test_with_results(self):
        results = [
            {"title": "测试文档", "score": 0.95, "snippet": "摘要内容"},
        ]
        output = format_recommendations(results, ActivationContext.RESEARCH)
        assert "测试文档" in output
        assert "0.95" in output
        assert "摘要内容" in output

    def test_context_label(self):
        results = [{"title": "文档", "score": 0.5}]
        output = format_recommendations(results, ActivationContext.WEEKLY_REPORT)
        assert "周报" in output


class TestGetTopSuggestions:
    """简洁接口."""

    @patch("cockpit.knowledge_activation.kos_search")
    def test_returns_titles(self, mock_search):
        mock_search.return_value = {
            "results": [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        }
        titles = get_top_suggestions(ActivationContext.DOCUMENT, limit=3)
        assert titles == ["A", "B", "C"]

    @patch("cockpit.knowledge_activation.kos_search")
    def test_filters_empty(self, mock_search):
        mock_search.return_value = {
            "results": [{"title": "A"}, {"name": ""}, {"title": ""}]
        }
        titles = get_top_suggestions(ActivationContext.NOTE)
        assert "A" in titles
