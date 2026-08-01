"""brain_memory 单元测试 — 偏好提取 + 自动存储."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cockpit.brain_memory import (
    auto_extract_and_store,
    extract_preferences,
    store_preferences,
)


class TestExtractPreferences:
    """偏好提取."""

    def test_simple_preference(self):
        prefs = extract_preferences("我喜欢用 Markdown 写周报")
        assert len(prefs) >= 1
        assert any("Markdown" in v for _, v in prefs)

    def test_multiple_preferences(self):
        text = "我喜欢简洁的回答，不要用 PDF 格式"
        prefs = extract_preferences(text)
        assert len(prefs) >= 2

    def test_remember_pattern(self):
        prefs = extract_preferences("记住我是卫健委借调人员")
        assert len(prefs) == 1
        assert "卫健委" in prefs[0][1]

    def test_no_preference(self):
        prefs = extract_preferences("今天天气怎么样")
        assert len(prefs) == 0

    def test_english_preference(self):
        prefs = extract_preferences("I like concise answers")
        assert len(prefs) == 1
        assert "concise" in prefs[0][1].lower()

    def test_empty_text(self):
        assert extract_preferences("") == []

    def test_duplicate_dedup(self):
        """相同 key 的偏好去重."""
        text = "我喜欢 Markdown，我喜欢 Markdown"
        prefs = extract_preferences(text)
        # 相同内容提取两次，但 normalize 后 key 相同，只保留一个
        keys = [k for k, _ in prefs]
        assert len(keys) == len(set(keys))


class TestStorePreferences:
    """偏好存储."""

    def test_store_and_recall(self, tmp_path):
        db_path = tmp_path / "test.db"
        with patch("cockpit.brain_core._db_path", return_value=db_path):
            count = store_preferences([("fmt", "markdown"), ("lang", "zh")])
            assert count == 2

    def test_store_empty(self, tmp_path):
        db_path = tmp_path / "test.db"
        with patch("cockpit.brain_core._db_path", return_value=db_path):
            count = store_preferences([])
            assert count == 0


class TestAutoExtractAndStore:
    """端到端: 提取 + 存储."""

    def test_auto_store(self, tmp_path):
        db_path = tmp_path / "test.db"
        with patch("cockpit.brain_core._db_path", return_value=db_path):
            prefs = auto_extract_and_store("我喜欢用 Markdown，不要 PDF")
            assert len(prefs) >= 2
            # 验证确实存入了
            from cockpit.brain_core import get_preferences
            stored = get_preferences()
            assert len(stored) >= 2


class TestBrainWeekly:
    """周报素材生成 (Phase 49 T3)."""

    @patch("cockpit.commands.brain.llm_complete")
    @patch("cockpit.commands.brain.get_history")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    def test_weekly_outputs_structure(self, mock_rec, mock_hist, mock_llm):
        from cockpit.commands.brain import cmd_brain_weekly
        import argparse

        mock_rec.return_value = [{"title": "政策A", "score": 0.9}]
        mock_hist.return_value = [{"role": "user", "content": "测试对话"}]
        mock_llm.return_value = "本周重点：..."

        args = argparse.Namespace(days=7)
        result = cmd_brain_weekly(args)
        assert result == 0

    @patch("cockpit.commands.brain.llm_complete")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    def test_weekly_fallback_when_llm_unavailable(self, mock_rec, mock_llm):
        from cockpit.commands.brain import cmd_brain_weekly
        import argparse

        mock_rec.return_value = [{"title": "政策A", "score": 0.9}]
        mock_llm.return_value = None  # LLM 不可用

        args = argparse.Namespace(days=7)
        result = cmd_brain_weekly(args)
        assert result == 0  # 仍应成功退出


class TestBrainGongwen:
    """公文辅助 (Phase 49 T3)."""

    @patch("cockpit.commands.brain.llm_complete")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    def test_gongwen_with_topic(self, mock_rec, mock_llm):
        from cockpit.commands.brain import cmd_brain_gongwen
        import argparse

        mock_rec.return_value = [{"title": "规范A", "snippet": "摘要"}]
        mock_llm.return_value = "大纲：..."

        args = argparse.Namespace(topic=["卫健委", "通知"])
        result = cmd_brain_gongwen(args)
        assert result == 0

    def test_gongwen_no_topic_fails(self):
        from cockpit.commands.brain import cmd_brain_gongwen
        import argparse

        args = argparse.Namespace(topic=[])
        result = cmd_brain_gongwen(args)
        assert result == 1

    @patch("cockpit.commands.brain.llm_complete")
    @patch("cockpit.knowledge_activation.recommend_for_context")
    def test_gongwen_fallback_when_llm_unavailable(self, mock_rec, mock_llm):
        from cockpit.commands.brain import cmd_brain_gongwen
        import argparse

        mock_rec.return_value = [{"title": "规范A", "snippet": "摘要"}]
        mock_llm.return_value = None

        args = argparse.Namespace(topic=["测试主题"])
        result = cmd_brain_gongwen(args)
        assert result == 0
