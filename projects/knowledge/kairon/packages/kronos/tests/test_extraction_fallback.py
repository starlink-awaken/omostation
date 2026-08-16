"""Tests for kronos extractor — 3-level fallback: LLM → rules → default."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kronos.extractor import (
    ExtractedContent,
    _default_result,
    _detect_content_type,
    _extract_entities,
    _extract_key_points,
    _extract_summary,
    _extract_title,
    extract,
    extract_with_rules,
)


class TestDetectContentType:
    """Content-type classification (rule-based)."""

    def test_detect_paper(self):
        """Text with 3+ paper keywords → 论文."""
        text = "DOI: 10.1234/abc\nAbstract\nIntroduction\nMethodology\nExperiment\nConclusion"
        assert _detect_content_type(text) == "论文"

    def test_detect_news(self):
        """Text with news keywords → 快讯."""
        text = "据新华社报道，记者获悉，今日快讯"
        assert _detect_content_type(text) == "快讯"

    def test_detect_tech(self):
        """Text with 3+ tech keywords → 技术文档."""
        text = "API function class parameter config install usage"
        assert _detect_content_type(text) == "技术文档"

    def test_detect_article(self):
        """Generic text without strong signal → 文章."""
        text = "今天天气真好，适合出门散步。"
        assert _detect_content_type(text) == "文章"


class TestExtractTitle:
    """Rule-based title extraction."""

    def test_markdown_heading(self):
        """# heading → extracted as title."""
        text = "# 这是一篇测试文章\n\n正文内容……"
        assert _extract_title(text) == "这是一篇测试文章"

    def test_first_short_line(self):
        """First non-empty short line → title fallback (min 5 chars)."""
        text = "\n\n短标题在这里\n正文内容……"
        assert _extract_title(text) == "短标题在这里"

    def test_truncated_long_text(self):
        """Very long text without explicit title → truncated."""
        text = "A" * 100
        result = _extract_title(text)
        assert len(result) <= 63  # 60 + "..."

    def test_empty_text(self):
        """Empty string → empty result."""
        assert _extract_title("") == ""


class TestExtractSummary:
    """Rule-based summary extraction."""

    def test_summary_first_two_sentences(self):
        """Takes first 2 meaningful sentences (>10 chars each)."""
        text = "第一句有意义的话非常重要。第二句也很重要需要记住。第三句无关。"
        result = _extract_summary(text)
        assert "第一句有意义的话非常重要" in result
        assert "第二句也很重要需要记住" in result

    def test_summary_truncates_long(self):
        """Long summary truncated at 150 chars."""
        text = "A" * 200 + "。B" * 100 + "。"
        result = _extract_summary(text)
        assert len(result) <= 153  # 150 + "..."

    def test_summary_short_text(self):
        """Very short text (<10 chars) filtered → empty."""
        text = "太短了会被过滤掉因为不满十一个字。"
        result = _extract_summary(text)
        assert isinstance(result, str)


class TestExtractKeyPoints:
    """Rule-based key points extraction."""

    def test_bullet_list(self):
        """Bullet items → extracted as key points."""
        text = "- 第一点\n- 第二点\n- 第三点"
        points = _extract_key_points(text)
        assert len(points) == 3
        assert "第一点" in points[0]

    def test_numbered_list(self):
        """Numbered items → extracted as key points."""
        text = "1. 第一步\n2. 第二步\n3. 第三步"
        points = _extract_key_points(text)
        assert len(points) >= 2

    def test_no_list_fallback(self):
        """No list items → search for definitional sentences (>10 chars)."""
        text = "核心是提升系统运行效率和稳定性。关键是减少不必要的资源浪费。这意味着性能大幅提升。"
        points = _extract_key_points(text)
        assert len(points) > 0

    def test_empty_text(self):
        """Empty text → fallback message."""
        assert _extract_key_points("") == ["提取失败 — 请切换 LLM 模式"]


class TestExtractEntities:
    """Rule-based entity extraction."""

    def test_chinese_names(self):
        """Chinese surnames → person entities (surname + 1~3 trailing chars)."""
        text = "张三和与李四讨论王五的方案。"
        entities = _extract_entities(text)
        assert len(entities["persons"]) > 0

    def test_organizations(self):
        """Org suffixes → organization entities."""
        text = "阿里巴巴集团和清华大学签署合作协议。"
        entities = _extract_entities(text)
        orgs = " ".join(entities["organizations"])
        assert "阿里巴巴集团" in orgs or "清华大学" in orgs

    def test_concepts(self):
        """Quoted terms → concept entities."""
        text = "「数字化转型」和「人工智能」是关键。"
        entities = _extract_entities(text)
        assert "数字化转型" in entities["concepts"]
        assert "人工智能" in entities["concepts"]


class TestExtractWithRules:
    """Full rule-based extraction pipeline."""

    def test_basic_extraction(self):
        """extract_with_rules returns structured result."""
        text = "# 测试标题\n\n- 要点A\n- 要点B\n\n核心是验证。"
        result = extract_with_rules(text)
        assert result["title"] == "测试标题"
        assert len(result["key_points"]) == 2
        assert result["content_type"] == "文章"
        assert result["_fallback"] == "rules"  # type: ignore[reportTypedDictNotRequiredAccess]

    def test_default_result(self):
        """_default_result returns safe fallback with empty fields."""
        result = _default_result("test reason")
        assert result["title"] == "未命名"
        assert result["_fallback"] == "default"  # type: ignore[reportTypedDictNotRequiredAccess]
        assert "test reason" in result["fallback_reason"]  # type: ignore[reportTypedDictNotRequiredAccess]


class TestExtract:
    """Top-level extract() with fallback chain."""

    def test_empty_text_returns_default(self):
        """Empty text → immediate default fallback."""
        result = extract("")  # empty
        assert result["_fallback"] == "default"  # type: ignore[reportTypedDictNotRequiredAccess]
        assert result["title"] == "未命名"

    def test_whitespace_only_returns_default(self):
        """Whitespace-only text → immediate default fallback."""
        result = extract("   \n  \t  ")
        assert result["_fallback"] == "default"  # type: ignore[reportTypedDictNotRequiredAccess]

    def test_nonempty_text_returns_result(self, monkeypatch):
        """Non-empty text returns a result (rules path, LLM mocked off).

        单元测试不该依赖 Ollama 外部服务 (曾 flaky: Ollama 在跑时走 llm 路径,
        LLM 生成 title 不确定, 硬断言 == '规则提取测试' 随机 fail). Mock 掉
        extract_with_ollama 强制走 rules 路径, 确定性 + 稳定.
        """
        text = "# 规则提取测试\n\n- 要点1\n\n本研究介绍了一个新方法。"
        monkeypatch.setattr(
            "kronos.extractor.extract_with_ollama",
            lambda *_args, **_kwargs: {"error": "mocked off (unit test)"},
        )
        result = extract(text)
        assert result["_fallback"] == "rules"  # type: ignore[reportTypedDictNotRequiredAccess]
        assert result["title"]
        assert result["title"] == "规则提取测试"


class TestExtractedContent:
    """ExtractedContent wrapper class."""

    def test_init_with_valid_data(self):
        """Construct from extraction dict."""
        raw = {
            "title": "Test",
            "summary": "A summary",
            "key_points": ["A", "B"],
            "entities": {"persons": ["张三"]},
            "content_type": "文章",
            "importance": "high",
            "tags": ["test"],
        }
        ec = ExtractedContent(raw)
        assert ec.title == "Test"
        assert ec.summary == "A summary"
        assert ec.is_valid

    def test_init_with_empty_data(self):
        """Construct with missing fields → defaults."""
        ec = ExtractedContent({})
        assert ec.title == "未命名"
        assert not ec.is_valid

    def test_to_markdown(self):
        """to_markdown produces Obsidian-compatible output."""
        raw = {"title": "T", "summary": "S", "key_points": ["K1"], "tags": ["tag1"]}
        ec = ExtractedContent(raw)
        md = ec.to_markdown("http://example.com", "test")
        assert 'title: "T"' in md
        assert "S" in md
        assert "K1" in md
        assert "source_url" in md
        assert "test" in md
