"""Tests for kronos ETL pipeline — adapters + dispatcher data flow."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kronos.adapters import to_knowledge_card, to_knowledge_card_from_browser_fetch
from kronos.dispatcher import (
    _domain_dir,
    wps_blockquote,
    wps_columns,
    wps_heading,
    wps_highlight,
    wps_key_points,
    wps_summary_note,
)


class TestAdaptersKnowledgeCard:
    """Extraction dict → Eidos KnowledgeCard conversion."""

    def test_basic_conversion(self):
        """to_knowledge_card produces expected shape."""
        extraction = {
            "title": "测试文章",
            "summary": "这是一篇测试文章。",
            "key_points": ["点A", "点B"],
            "content_type": "文章",
            "tags": ["test"],
        }
        card = to_knowledge_card(extraction, "https://example.com")
        assert card["schema_type"] == "KnowledgeCard"
        assert card["title"] == "测试文章"
        assert card["source"] == "https://example.com"
        assert card["source_type"] == "article"
        assert card["id"].startswith("KC-")
        assert len(card["id"]) == 15  # KC- + 12 hex chars

    def test_content_field_combines_summary_and_points(self):
        """Content auto-assembles from summary + key_points."""
        extraction = {
            "title": "T",
            "summary": "S",
            "key_points": ["K1", "K2"],
            "content_type": "文章",
        }
        card = to_knowledge_card(extraction, "src")
        assert "S" in card["content"]
        assert "K1" in card["content"]

    def test_explicit_content_overrides(self):
        """Passing content= overrides auto-combination."""
        extraction = {"title": "T", "summary": "S", "key_points": ["K1"], "content_type": "文章"}
        card = to_knowledge_card(extraction, "src", content="EXPLICIT")
        assert card["content"] == "EXPLICIT"

    def test_source_type_mapping(self):
        """content_type → source_type mapping."""
        for ct, expected in [("论文", "paper"), ("快讯", "news"), ("技术文档", "documentation")]:
            card = to_knowledge_card({"title": "T", "content_type": ct}, "src")
            assert card["source_type"] == expected, f"{ct} → {expected}"

    def test_source_type_override(self):
        """source_type= overrides mapping."""
        extraction = {"title": "T", "content_type": "文章"}
        card = to_knowledge_card(extraction, "src", source_type="custom")
        assert card["source_type"] == "custom"

    def test_fallback_title(self):
        """Missing/empty title → 未命名."""
        card = to_knowledge_card({}, "src")
        assert card["title"] == "未命名"

    def test_browser_fetch_conversion(self):
        """to_knowledge_card_from_browser_fetch produces card."""
        card = to_knowledge_card_from_browser_fetch(
            "https://example.com",
            "# Hello",
            "Example Page",
        )
        assert card["schema_type"] == "KnowledgeCard"
        assert card["id"].startswith("KC-")
        assert card["source_type"] == "article"
        assert "# Hello" in card["content"]


class TestDispatcherDomainDir:
    """Content type → vault directory mapping."""

    def test_article_dir(self):
        assert "20-知识域" in _domain_dir("文章")

    def test_paper_dir(self):
        assert "50-参考资料" in _domain_dir("论文")

    def test_news_dir(self):
        assert "10-收件箱" in _domain_dir("快讯")

    def test_unknown_dir(self):
        assert _domain_dir("未知类型") == "10-收件箱"


class TestDispatcherWPSTemplates:
    """WPS XML template generation."""

    def test_blockquote(self):
        result = wps_blockquote("https://x.com", "X")
        assert "https://x.com" in result
        assert "X" in result
        assert "blockquote" in result

    def test_heading(self):
        result = wps_heading("核心观点")
        assert "<h2>核心观点</h2>" in result

    def test_highlight(self):
        result = wps_highlight("注意这里", bg="#FFF", border="#CCC", emoji="⚠️")
        assert "highlightBlock" in result
        assert "注意这里" in result

    def test_key_points(self):
        result = wps_key_points(["A", "B"])
        assert result.count('listType="bullet"') == 2

    def test_columns(self):
        result = wps_columns("左", "右", left_bg="#EEE", right_bg="#DDD")
        assert "columns" in result
        assert "左" in result
        assert "右" in result

    def test_summary_note(self):
        result = wps_summary_note(
            title="测试",
            summary="摘要",
            key_points=["K1"],
            source_url="https://example.com",
            source_label="例",
            quotes=["金句"],
            thinking="思考",
            todos=["行动"],
        )
        # title is used as WPS note_title, not in XML body
        assert "摘要" in result
        assert "K1" in result
        assert "金句" in result
        assert "思考" in result
        assert "行动" in result

    def test_summary_note_no_optional(self):
        """No quotes/thinking/todos → no missing key errors."""
        result = wps_summary_note(
            title="T",
            summary="S",
            key_points=["K"],
            source_url="https://x.com",
        )
        assert "T" in result
        assert "S" in result
