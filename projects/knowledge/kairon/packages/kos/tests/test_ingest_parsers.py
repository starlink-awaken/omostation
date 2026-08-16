# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""解析器单元测试。"""

from __future__ import annotations

import importlib
import json
import tempfile
from pathlib import Path

import pytest

# ── 微信解析测试 ──


class TestWechatParser:
    def test_parse_valid_line(self, wechat_parser):
        """测试解析有效微信消息行。"""
        line = "2026-04-20 14:30:22 老王: 今天看了个Rust的异步编程视频"
        result = wechat_parser.parse_line(line)
        assert result is not None
        assert result["sender"] == "老王"
        assert "Rust" in result["topics"]
        assert result["urls"] == []

    def test_parse_line_with_url(self, wechat_parser):
        """测试带URL的消息行。"""
        line = "2026-04-21 09:20:33 小张: 看这里 https://gobyexample.com/"
        result = wechat_parser.parse_line(line)
        assert result is not None
        assert "https://gobyexample.com/" in result["urls"]

    def test_parse_invalid_line(self, wechat_parser):
        """测试无效行格式。"""
        assert wechat_parser.parse_line("invalid line") is None
        assert wechat_parser.parse_line("") is None

    def test_parse_file(self, wechat_parser):
        """测试解析完整文件。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("2026-04-20 14:30:22 老王: 学习Rust\n")
            f.write("2026-04-21 09:00:00 小张: 学习Go\n")
            fpath = f.name
        try:
            messages = wechat_parser.parse_file(fpath)
            assert len(messages) == 2
        finally:
            Path(fpath).unlink()

    def test_to_jsonld_structure(self, wechat_parser):
        """测试JSON-LD输出结构。"""
        messages = [
            {
                "timestamp": "2026-04-20T14:30:22",
                "sender": "老王",
                "content": "学习Rust",
                "urls": [],
                "topics": ["Rust"],
            }
        ]
        jsonld = wechat_parser.to_jsonld(messages)
        assert jsonld["source"] == "wechat_export"
        assert len(jsonld["facts"]) == 1
        assert jsonld["facts"][0]["@type"] == "ChatMessage"

    def test_empty_file(self, wechat_parser):
        """测试空文件。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("")
            fpath = f.name
        try:
            messages = wechat_parser.parse_file(fpath)
            assert len(messages) == 0
        finally:
            Path(fpath).unlink()

    def test_non_existent_file(self, wechat_parser):
        """测试不存在的文件。"""
        with pytest.raises(FileNotFoundError):
            wechat_parser.parse_file("/nonexistent/file.txt")


# ── 笔记解析测试 ──


class TestNotesParser:
    def test_parse_topics(self, notes_parser):
        md = "# Rust 学习笔记\n## 所有权\n- 每个值有唯一所有者\n- 所有权可以转移"
        facts = notes_parser.parse_markdown(md)
        types = [f["@type"] for f in facts]
        assert "Topic" in types
        assert "SubTopic" in types
        assert "KnowledgePoint" in types

    def test_parse_code_block(self, notes_parser):
        md = "# Go\n```go\nfunc main() {}\n```"
        facts = notes_parser.parse_markdown(md)
        code_facts = [f for f in facts if f["@type"] == "CodeSnippet"]
        assert len(code_facts) >= 1
        assert code_facts[0]["metadata"]["language"] == "go"

    def test_empty_content(self, notes_parser):
        facts = notes_parser.parse_markdown("")
        assert len(facts) == 0

    def test_mixed_content(self, notes_parser):
        md = "# Go 并发\n\n## Goroutine\n- 轻量级线程\n\n```go\nfunc main() {}\n```"
        facts = notes_parser.parse_markdown(md)
        assert len(facts) >= 3

    def test_file_not_found(self, notes_parser):
        with pytest.raises(FileNotFoundError):
            notes_parser.parse_file("/nonexistent/file.md")


# ── 书签解析测试 ──


class TestBookmarksParser:
    def test_parse_bookmarks(self, bookmarks_parser):
        bookmarks = [
            {"title": "Test", "url": "https://test.com", "tags": ["test"], "folder": "Test", "date_added": "2026-01-01"}
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(bookmarks, f)
            fpath = f.name
        try:
            facts = bookmarks_parser.parse_file(fpath)
            assert len(facts) == 1
            assert facts[0]["pred"] == "bookmarked"
        finally:
            Path(fpath).unlink()

    def test_empty_bookmarks(self, bookmarks_parser):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([], f)
            fpath = f.name
        try:
            facts = bookmarks_parser.parse_file(fpath)
            assert len(facts) == 0
        finally:
            Path(fpath).unlink()

    def test_non_existent_file(self, bookmarks_parser):
        with pytest.raises(FileNotFoundError):
            bookmarks_parser.parse_file("/nonexistent/file.json")


# ── Fixtures ──


@pytest.fixture
def wechat_parser():
    return importlib.import_module("kos.ingest.parsers.wechat")


@pytest.fixture
def notes_parser():
    return importlib.import_module("kos.ingest.parsers.notes")


@pytest.fixture
def bookmarks_parser():
    return importlib.import_module("kos.ingest.parsers.bookmarks")
