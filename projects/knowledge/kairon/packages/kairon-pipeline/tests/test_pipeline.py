"""kairon-pipeline 单元测试 — QualityGate + SourceRegistry + RawContent + DownstreamTrigger。

以前仅有 5 个 import 测试。本文件补充 22 个行为测试，覆盖核心模块。
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from pathlib import Path

import pytest
from kairon_pipeline.downstream_trigger import DownstreamTrigger, get_downstream_trigger
from kairon_pipeline.extract_base import StructuredKnowledge
from kairon_pipeline.extract_html import HtmlContentExtractor
from kairon_pipeline.quality_gate import QualityGate, ValidationResult
from kairon_pipeline.source_connectors import RawContent
from kairon_pipeline.source_priority import HarvestPriorityQueue, Priority
from kairon_pipeline.source_registry import SourceRegistry

# ============================================================================
# StructuredKnowledge
# ============================================================================


class TestStructuredKnowledge:
    def test_basic_construction(self):
        sk = StructuredKnowledge(uri="test://doc", title="Hello", body="Some content")
        assert sk.uri == "test://doc"
        assert sk.title == "Hello"
        assert sk.body == "Some content"
        assert sk.metadata == {}

    def test_with_metadata(self):
        sk = StructuredKnowledge(uri="u", title="t", body="b", metadata={"key": "val"})
        assert sk.metadata == {"key": "val"}

    def test_to_dict(self):
        sk = StructuredKnowledge(uri="u", title="t", body="b")
        d = sk.to_dict()
        assert d["uri"] == "u"
        assert d["title"] == "t"
        assert d["body"] == "b"


# ============================================================================
# RawContent
# ============================================================================


class TestRawContent:
    def test_basic_construction(self):
        rc = RawContent(uri="http://example.com", data="<html></html>", content_type="text/html")
        assert rc.uri == "http://example.com"
        assert rc.data == "<html></html>"
        assert rc.content_type == "text/html"

    def test_default_content_type(self):
        rc = RawContent(uri="file:///doc", data="content")
        assert rc.content_type == "text/plain"

    def test_to_dict(self):
        rc = RawContent(uri="u", data="d", metadata={"m": "v"})
        d = rc.to_dict()
        assert d["uri"] == "u"
        assert d["metadata"] == {"m": "v"}


# ============================================================================
# ValidationResult
# ============================================================================


class TestValidationResult:
    def test_passed_result(self):
        vr = ValidationResult(passed=True, quality_score=0.9)
        assert vr.passed is True
        assert vr.quality_score == 0.9
        assert vr.reasons == []

    def test_failed_result_with_reasons(self):
        vr = ValidationResult(passed=False, quality_score=0.1, reasons=["too short"])
        assert vr.passed is False
        assert vr.reasons == ["too short"]


# ============================================================================
# QualityGate
# ============================================================================


class TestQualityGate:
    @pytest.mark.asyncio
    async def test_valid_item_passes(self):
        gate = QualityGate(min_title_length=3, min_body_length=50, min_word_count=10)
        item = StructuredKnowledge(
            uri="doc",
            title="Good Title",
            body="this is a body with enough words to pass the word count check",
        )
        results = await gate.validate([item])
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].quality_score == 1.0

    @pytest.mark.asyncio
    async def test_short_title_fails(self):
        gate = QualityGate(min_title_length=10)
        item = StructuredKnowledge(
            uri="doc",
            title="Hi",
            body="this is a body with enough words to pass the word count check here",
        )
        results = await gate.validate([item])
        assert results[0].quality_score < 1.0
        assert any("Title too short" in r for r in results[0].reasons)

    @pytest.mark.asyncio
    async def test_short_body_fails(self):
        gate = QualityGate(min_body_length=100)
        item = StructuredKnowledge(
            uri="doc",
            title="Good Title",
            body="short",
        )
        results = await gate.validate([item])
        assert results[0].quality_score < 1.0
        assert any("Body too short" in r for r in results[0].reasons)

    @pytest.mark.asyncio
    async def test_low_word_count_fails(self):
        gate = QualityGate(min_word_count=10)
        item = StructuredKnowledge(
            uri="doc",
            title="Good Title",
            body="only a few words",
        )
        results = await gate.validate([item])
        assert results[0].quality_score < 1.0
        assert any("Too few words" in r for r in results[0].reasons)

    @pytest.mark.asyncio
    async def test_all_rules_fail_marks_not_passed(self):
        gate = QualityGate(min_title_length=20, min_body_length=200, min_word_count=50)
        item = StructuredKnowledge(uri="d", title="x", body="y")
        results = await gate.validate([item])
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_score_clamped_to_zero(self):
        gate = QualityGate(min_title_length=999, min_body_length=999, min_word_count=999)
        item = StructuredKnowledge(uri="d", title="x", body="y")
        results = await gate.validate([item])
        # score starts at 1.0, 3 rules fail: 1.0 - 0.9 = 0.1, clamped max(0, 0.1) = 0.1
        assert results[0].quality_score == 0.09999999999999998  # floating point

    @pytest.mark.asyncio
    async def test_multiple_items(self):
        gate = QualityGate()
        items = [
            StructuredKnowledge(uri="a", title="Good Title", body="long enough body with ten or more words to pass"),
            StructuredKnowledge(uri="b", title="x", body="y"),
        ]
        results = await gate.validate(items)
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False

    @pytest.mark.asyncio
    async def test_empty_list(self):
        gate = QualityGate()
        results = await gate.validate([])
        assert results == []


# ============================================================================
# SourceRegistry
# ============================================================================


class TestSourceRegistry:
    def test_register_and_get(self):
        sr = SourceRegistry()
        sr.register("src1", {"uri": "http://example.com"})
        assert sr.get("src1") == {"uri": "http://example.com"}

    def test_unregister_existing(self):
        sr = SourceRegistry()
        sr.register("src1", {})
        assert sr.unregister("src1") is True
        assert sr.get("src1") is None

    def test_unregister_nonexistent(self):
        sr = SourceRegistry()
        assert sr.unregister("nonexistent") is False

    def test_list_sources(self):
        sr = SourceRegistry()
        sr.register("a", {})
        sr.register("b", {})
        assert set(sr.list_sources()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_resolve_returns_rawcontent(self):
        sr = SourceRegistry()
        sr.register("src1", {"uri": "http://example.com", "content_type": "text/html"})
        result = await sr.resolve("src1")
        assert isinstance(result, RawContent)
        assert result.uri == "http://example.com"
        assert result.content_type == "text/html"


# ============================================================================
# DownstreamTrigger
# ============================================================================


class TestDownstreamTrigger:
    def test_factory_function(self):
        trigger = get_downstream_trigger(processing_delay_seconds=2.0)
        assert isinstance(trigger, DownstreamTrigger)
        assert trigger.processing_delay == 2.0

    @pytest.mark.asyncio
    async def test_trigger_creates_entry(self):
        trigger = DownstreamTrigger(processing_delay_seconds=0)
        path = Path("/tmp/test_file.md")
        await trigger.trigger(path)
        assert str(path) in trigger._last_processed

    def test_get_downstream_trigger_default_delay(self):
        trigger = get_downstream_trigger()
        assert trigger.processing_delay == 1.0


# ============================================================================
# HtmlContentExtractor
# ============================================================================


class TestHtmlContentExtractor:
    @pytest.mark.asyncio
    async def test_extract_from_rawcontent(self):
        extractor = HtmlContentExtractor()
        rc = RawContent(uri="http://example.com", data="<html><title>Test Page</title><body>Hello World</body></html>")
        result = await extractor.extract(rc)
        assert result.title == "Test Page"

    @pytest.mark.asyncio
    async def test_extract_from_string(self):
        extractor = HtmlContentExtractor()
        result = await extractor.extract("<html><title>Hi</title><body>Content</body></html>")
        assert result.title == "Hi"
        assert result.uri == "inline://html"

    @pytest.mark.asyncio
    async def test_extract_no_title(self):
        extractor = HtmlContentExtractor()
        result = await extractor.extract("<html><body>No title here</body></html>")
        assert result.title == "Untitled"


# ============================================================================
# PriorityQueue
# ============================================================================


class TestHarvestPriorityQueue:
    @pytest.mark.asyncio
    async def test_add_and_pop(self):
        pq = HarvestPriorityQueue()
        await pq.enqueue("task1", priority=Priority.LOW)
        await pq.enqueue("task2", priority=Priority.URGENT)
        job = await pq.dequeue()
        assert job.source_id == "task2"  # highest priority first  # type: ignore[reportOptionalMemberAccess]

    @pytest.mark.asyncio
    async def test_empty_dequeue_returns_none(self):
        pq = HarvestPriorityQueue()
        assert await pq.dequeue() is None

    @pytest.mark.asyncio
    async def test_fifo_for_equal_priority(self):
        pq = HarvestPriorityQueue()
        await pq.enqueue("a", priority=Priority.NORMAL)
        await pq.enqueue("b", priority=Priority.NORMAL)
        assert (await pq.dequeue()).source_id == "a"  # type: ignore[reportOptionalMemberAccess]
        assert (await pq.dequeue()).source_id == "b"  # type: ignore[reportOptionalMemberAccess]

    def test_size_property(self):
        pq = HarvestPriorityQueue()
        assert pq.size == 0

    @pytest.mark.asyncio
    async def test_queue_status_counts(self):
        pq = HarvestPriorityQueue()
        await pq.enqueue("a", Priority.HIGH)
        await pq.enqueue("b", Priority.HIGH)
        await pq.enqueue("c", Priority.LOW)
        status = await pq.get_queue_status()
        assert status["high"] == 2
        assert status["low"] == 1

    @pytest.mark.asyncio
    async def test_peek_does_not_remove(self):
        pq = HarvestPriorityQueue()
        await pq.enqueue("task", Priority.URGENT)
        assert (await pq.peek()).source_id == "task"  # type: ignore[reportOptionalMemberAccess]
        assert pq.size == 1

    def test_clear_empties_queue(self):
        pq = HarvestPriorityQueue()
        pq.clear()
        assert pq.size == 0
