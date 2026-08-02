"""brain_core 单元测试 — 验证 DRY 重构后功能正确."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# 确保 cockpit 包可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cockpit.brain_core import (
    ask,
    build_brain_prompt,
    format_sources_cli,
    get_history,
    get_preferences,
    kos_search,
    parse_fact,
    store_conversation,
    store_preference,
)


class TestParseFact:
    """偏好解析."""

    def test_colon_separator(self):
        key, value = parse_fact("format: markdown")
        assert key == "format"
        assert value == "markdown"

    def test_chinese_colon_separator(self):
        key, value = parse_fact("格式：Markdown")
        assert key == "格式"
        assert value == "Markdown"

    def test_no_colon_uses_prefix(self):
        key, value = parse_fact("我喜欢用 Markdown 写周报")
        assert key == "我喜欢用 Markdown 写周报"[:20]
        assert value == "我喜欢用 Markdown 写周报"


class TestBuildBrainPrompt:
    """Prompt 构建."""

    def test_includes_question(self):
        prompt = build_brain_prompt("测试问题", [], [], [])
        assert "测试问题" in prompt

    def test_includes_knowledge(self):
        results = [{"title": "文档A", "snippet": "内容A"}]
        prompt = build_brain_prompt("问题", results, [], [])
        assert "文档A" in prompt
        assert "内容A" in prompt

    def test_includes_preferences(self):
        prefs = [{"key": "format", "value": "markdown"}]
        prompt = build_brain_prompt("问题", [], prefs, [])
        assert "format" in prompt
        assert "markdown" in prompt

    def test_includes_history(self):
        history = [{"role": "user", "content": "之前的问题"}]
        prompt = build_brain_prompt("问题", [], [], history)
        assert "之前的问题" in prompt


class TestFormatSourcesCli:
    """来源格式化."""

    def test_empty_results(self):
        result = format_sources_cli([])
        assert "无外部知识来源" in result

    def test_with_results(self):
        results = [
            {"id": "doc1", "title": "测试文档", "score": 0.95, "snippet": "摘要内容"},
        ]
        output = format_sources_cli(results)
        assert "测试文档" in output
        assert "0.950" in output
        assert "摘要内容" in output


class TestAsk:
    """核心问答流程."""

    @patch("cockpit.brain_core.llm_complete")
    @patch("cockpit.brain_core.kos_search")
    def test_ask_with_kos_results(self, mock_search, mock_llm):
        """验证 KOS 结果被正确注入并返回."""
        mock_search.return_value = {"results": [{"id": "doc1", "title": "测试文档", "snippet": "内容", "score": 0.95}]}
        mock_llm.return_value = "根据文档，答案是 X"

        result = ask("测试问题")

        assert result["fallback"] is False
        assert result["answer"] == "根据文档，答案是 X"
        assert len(result["sources"]) == 1
        assert result["sources"][0]["title"] == "测试文档"
        assert result["memory_used"]["preferences"] >= 0

    @patch("cockpit.brain_core.llm_complete")
    @patch("cockpit.brain_core.kos_search")
    def test_ask_kos_unavailable(self, mock_search, mock_llm):
        """验证 KOS 不可用时降级."""
        mock_search.return_value = {"error": "Connection refused", "results": []}
        mock_llm.return_value = "降级回答"

        result = ask("测试问题")

        assert result["sources"] == []
        assert result["fallback"] is False  # LLM 可用所以不是 fallback

    @patch("cockpit.brain_core.llm_complete")
    @patch("cockpit.brain_core.kos_search")
    def test_ask_llm_unavailable(self, mock_search, mock_llm):
        """验证 LLM 不可用时返回 fallback."""
        mock_search.return_value = {"results": [{"id": "d1", "title": "文档"}]}
        mock_llm.return_value = ""

        result = ask("测试问题")

        assert result["fallback"] is True
        assert result["answer"] == ""


class TestStorage:
    """存储功能."""

    def test_store_and_get_preference(self, tmp_path, monkeypatch):
        """验证偏好存储 + 读取."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("HOME", str(tmp_path))

        # 注意: _db_path 用 Path.home()，需要 mock
        with patch("cockpit.brain_core._db_path", return_value=db_path):
            store_preference("test_key", "test_value")
            prefs = get_preferences()

            assert len(prefs) >= 1
            assert any(p["key"] == "test_key" and p["value"] == "test_value" for p in prefs)

    def test_store_conversation(self, tmp_path):
        """验证对话存储."""
        db_path = tmp_path / "test.db"

        with patch("cockpit.brain_core._db_path", return_value=db_path):
            store_conversation("user", "你好")
            store_conversation("assistant", "你好！有什么可以帮你的？")

            history = get_history(limit=10)
            assert len(history) == 2
            roles = {h["role"] for h in history}
            assert roles == {"user", "assistant"}
