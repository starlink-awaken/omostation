"""T3: brain weekly / gongwen 子命令测试 (Phase 49).

验证 cockpit brain weekly 输出结构化周报素材,
cockpit brain gongwen "主题" 返回 KOS 引用 + 大纲.

注意: brain.py 内部通过 local import 引入 recommend_for_context/format_recommendations,
因此 mock 必须指向 cockpit.knowledge_activation 源模块, 而非 cockpit.commands.brain.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestBrainWeekly:
    """cockpit brain weekly — 周报素材生成."""

    @patch("cockpit.knowledge_activation.format_recommendations")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.commands.brain.get_history")
    @patch("cockpit.commands.brain.llm_complete")
    def test_weekly_outputs_structure(
        self,
        mock_llm,
        mock_history,
        mock_recommend,
        mock_format,
        capsys,
    ):
        """weekly 输出包含结构化周报素材."""
        mock_history.return_value = [
            {"role": "user", "content": "本周完成了借调手续"},
        ]
        mock_recommend.return_value = [
            {"title": "借调政策", "score": 0.9},
        ]
        mock_format.return_value = "📚 周报知识推荐:\n  1. 借调政策 (0.90)"
        mock_llm.return_value = "本周重点：\n1. 借调手续办理"

        from cockpit.commands.brain import cmd_brain_weekly

        mock_args = MagicMock()
        mock_args.days = 7

        result = cmd_brain_weekly(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "周报素材" in captured.out or "本周重点" in captured.out

    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.commands.brain.get_history")
    @patch("cockpit.commands.brain.llm_complete")
    def test_weekly_llm_unavailable_fallback(
        self,
        mock_llm,
        mock_history,
        mock_recommend,
        capsys,
    ):
        """LLM 不可用时 fallback 到知识推荐."""
        mock_history.return_value = [{"role": "user", "content": "对话"}]
        mock_recommend.return_value = [
            {"title": "政策A", "score": 0.85},
        ]
        mock_llm.return_value = None

        from cockpit.commands.brain import cmd_brain_weekly

        mock_args = MagicMock()
        mock_args.days = 7

        result = cmd_brain_weekly(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "LLM 暂不可用" in captured.out or "知识推荐" in captured.out

    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.commands.brain.get_history")
    @patch("cockpit.commands.brain.llm_complete")
    def test_weekly_uses_days_param(
        self,
        mock_llm,
        mock_history,
        mock_recommend,
    ):
        """get_history 被调用时 limit=50."""
        mock_history.return_value = []
        mock_recommend.return_value = []
        mock_llm.return_value = "输出"

        from cockpit.commands.brain import cmd_brain_weekly

        mock_args = MagicMock()
        mock_args.days = 14

        cmd_brain_weekly(mock_args)

        mock_history.assert_called_once_with(limit=50)


class TestBrainGongwen:
    """cockpit brain gongwen — 公文写作辅助."""

    @patch("cockpit.knowledge_activation.format_recommendations")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.commands.brain.llm_complete")
    def test_gongwen_with_topic(
        self,
        mock_llm,
        mock_recommend,
        mock_format,
        capsys,
    ):
        """gongwen 带主题时输出大纲."""
        mock_recommend.return_value = [
            {"title": "国资委13号令", "snippet": "规范内容"},
        ]
        mock_format.return_value = "📚 公文知识推荐:\n  1. 国资委13号令"
        mock_llm.return_value = "写作大纲：\n1. 背景介绍\n2. 政策依据"

        from cockpit.commands.brain import cmd_brain_gongwen

        mock_args = MagicMock()
        mock_args.topic = ["卫健委通知"]

        result = cmd_brain_gongwen(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "公文写作辅助" in captured.out
        assert "卫健委通知" in captured.out

    def test_gongwen_no_topic_fails(self, capsys):
        """无主题时返回错误退出码."""
        from cockpit.commands.brain import cmd_brain_gongwen

        mock_args = MagicMock()
        mock_args.topic = []

        result = cmd_brain_gongwen(mock_args)

        assert result == 1
        captured = capsys.readouterr()
        assert "请提供公文主题" in captured.out

    @patch("cockpit.knowledge_activation.format_recommendations")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.commands.brain.llm_complete")
    def test_gongwen_llm_unavailable_fallback(
        self,
        mock_llm,
        mock_recommend,
        mock_format,
        capsys,
    ):
        """LLM 不可用时 gongwen 显示相关知识."""
        mock_recommend.return_value = [{"title": "规范A", "snippet": "摘要"}]
        mock_format.return_value = "📚 公文知识推荐:\n  1. 规范A"
        mock_llm.return_value = None

        from cockpit.commands.brain import cmd_brain_gongwen

        mock_args = MagicMock()
        mock_args.topic = ["通知"]

        result = cmd_brain_gongwen(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "LLM 暂不可用" in captured.out

    @patch("cockpit.knowledge_activation.recommend_for_context")
    @patch("cockpit.commands.brain.llm_complete")
    def test_gongwen_calls_document_context(
        self,
        mock_llm,
        mock_recommend,
    ):
        """gongwen 使用 ActivationContext.DOCUMENT."""
        mock_recommend.return_value = []
        mock_llm.return_value = "输出"

        from cockpit.commands.brain import cmd_brain_gongwen

        mock_args = MagicMock()
        mock_args.topic = ["借调规定"]

        cmd_brain_gongwen(mock_args)

        call_args = mock_recommend.call_args
        from cockpit.knowledge_activation import ActivationContext

        assert call_args[0][0] == ActivationContext.DOCUMENT
        assert "借调规定" in call_args[1].get("content", "")
