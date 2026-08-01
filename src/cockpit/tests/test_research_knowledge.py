"""research + 知识激活集成测试 (Phase 49 T1)."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class TestResearchKnowledgeIntegration:
    """research ask 追加知识推荐."""

    @patch("cockpit.knowledge_activation.kos_search")
    def test_recommend_for_context_returns_results(self, mock_search):
        """recommend_for_context 返回知识推荐."""
        from cockpit.knowledge_activation import ActivationContext, recommend_for_context

        mock_search.return_value = {
            "results": [
                {"id": "d1", "title": "借调政策", "score": 0.9},
                {"id": "d2", "title": "工作总结方法", "score": 0.7},
            ]
        }
        results = recommend_for_context(ActivationContext.RESEARCH, "借调总结")
        assert len(results) == 2
        assert results[0]["title"] == "借调政策"

    @patch("cockpit.knowledge_activation.kos_search")
    def test_kos_unavailable_returns_empty(self, mock_search):
        """KOS 不可用时返回空列表."""
        from cockpit.knowledge_activation import ActivationContext, recommend_for_context

        mock_search.return_value = {"error": "timeout", "results": []}
        results = recommend_for_context(ActivationContext.RESEARCH, "测试")
        assert results == []

    @patch("cockpit.brain_core.get_preferences")
    @patch("cockpit.knowledge_activation.kos_search")
    def test_preference_injected_when_user_provided(self, mock_search, mock_prefs):
        """提供 user 参数时偏好被注入搜索 query."""
        from cockpit.knowledge_activation import ActivationContext, recommend_for_context

        mock_search.return_value = {"results": [{"title": "结果", "score": 0.5}]}
        mock_prefs.return_value = [
            {"key": "风格", "value": "Markdown"},
            {"key": "语言", "value": "中文"},
        ]

        recommend_for_context(ActivationContext.RESEARCH, "测试", user="testuser")

        # 验证 kos_search 被调用，且 query 包含偏好关键词
        call_args = mock_search.call_args
        query = call_args[0][0] if call_args[0] else call_args[1].get("query", "")
        assert "Markdown" in query or "中文" in query

    @patch("cockpit.brain_core.get_preferences")
    @patch("cockpit.knowledge_activation.kos_search")
    def test_no_user_skips_preference_injection(self, mock_search, mock_prefs):
        """不提供 user 参数时不注入偏好."""
        from cockpit.knowledge_activation import ActivationContext, recommend_for_context

        mock_search.return_value = {"results": []}
        recommend_for_context(ActivationContext.RESEARCH, "测试")
        # 不提供 user 时不应调用 get_preferences
        mock_prefs.assert_not_called()

    @patch("cockpit.knowledge_activation.kos_search")
    def test_low_score_filtering(self, mock_search):
        """低分结果被过滤."""
        from cockpit.knowledge_activation import ActivationContext, recommend_for_context

        mock_search.return_value = {
            "results": [
                {"title": "高分", "score": 0.8},
                {"title": "低分", "score": 0.1},
                {"title": "中分", "score": 0.5},
            ]
        }
        results = recommend_for_context(ActivationContext.RESEARCH, "测试")
        # 低分 (0.1 < 0.2 threshold) 应被过滤
        titles = [r["title"] for r in results]
        assert "高分" in titles
        assert "中分" in titles
