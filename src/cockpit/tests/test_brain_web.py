"""Brain Web API 测试 (Phase 49 T2)."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class TestBrainWebAPI:
    """Brain Web API 端点测试 (Phase 49 T2)."""

    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.web.api_brain.llm_complete")
    @patch("cockpit.web.api_brain.kos_search_sync")
    def test_ask_returns_knowledge_suggestions(self, mock_kos, mock_llm, mock_rec):
        """ask 端点返回 knowledge_suggestions."""
        from cockpit.web.api_brain import brain_ask

        mock_kos.return_value = {
            "results": [{"id": "d1", "title": "知识A", "score": 0.9}],
        }
        mock_llm.return_value = "测试回答"
        mock_rec.return_value = [
            {"title": "推荐文档", "score": 0.85, "snippet": "摘要"},
        ]

        import asyncio

        result = asyncio.run(brain_ask({"question": "测试问题"}))
        assert "knowledge_suggestions" in result
        assert len(result["knowledge_suggestions"]) == 1
        assert result["knowledge_suggestions"][0]["title"] == "推荐文档"

    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.web.api_brain.llm_complete")
    @patch("cockpit.web.api_brain.kos_search_sync")
    def test_ask_kos_unavailable_no_crash(self, mock_kos, mock_llm, mock_rec):
        """KOS 推荐不可用时 ask 不崩溃，返回空推荐."""
        from cockpit.web.api_brain import brain_ask

        mock_kos.return_value = {"results": []}
        mock_llm.return_value = "降级回答"
        mock_rec.side_effect = Exception("KOS unavailable")

        import asyncio

        result = asyncio.run(brain_ask({"question": "测试"}))
        # KOS 推荐不可用时 knowledge_suggestions 应为空数组
        assert result["knowledge_suggestions"] == []
        # 主回答仍应正常返回
        assert result["answer"] == "降级回答"
        assert result["fallback"] is False

    @patch("cockpit.web.api_brain.kos_search_sync")
    def test_ask_empty_question_raises_400(self, mock_kos):
        """空 question 返回 400."""
        import asyncio

        from fastapi import HTTPException

        from cockpit.web.api_brain import brain_ask

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(brain_ask({"question": ""}))
        assert exc_info.value.status_code == 400

    def test_history_endpoint_returns_list(self):
        """history 端点返回列表格式."""
        import asyncio

        from cockpit.web.api_brain import brain_history

        result = asyncio.run(brain_history(limit=10))
        # 验证返回的是列表（可能有历史数据）
        assert isinstance(result, list)
        if len(result) > 0:
            assert "role" in result[0]
            assert "content" in result[0]
