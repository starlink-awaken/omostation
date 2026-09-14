"""Tests for ContextCompressor — hot/warm/cold compression."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import time

from eidos.context_compressor import (
    _SUMMARY_TAG,
    ContextCompressor,
    MemoryEntry,
    _estimate_tokens,
)


class TestEstimateTokens:
    def test_empty(self):
        assert _estimate_tokens("") == 0

    def test_single_word(self):
        assert _estimate_tokens("hello") == 1

    def test_multi_word(self):
        assert _estimate_tokens("hello world test") == 3

    def test_whitespace(self):
        assert _estimate_tokens("   ") == 0


class TestMemoryEntry:
    def test_token_count_auto(self):
        entry = MemoryEntry(content="one two three")
        assert entry.token_count == 3

    def test_token_count_explicit(self):
        entry = MemoryEntry(content="hello", token_count=999)
        assert entry.token_count == 999

    def test_empty_content_token_count(self):
        entry = MemoryEntry(content="")
        assert entry.token_count == 0


class TestClassifyTemperature:
    def setup_method(self):
        self.cc = ContextCompressor(hot_age=300, warm_age=1800, hot_access_floor=3)

    def test_hot_by_age(self):
        entry = MemoryEntry(content="hot", timestamp=time.time() - 10)
        assert self.cc.classify_temperature(entry, time.time()) == "hot"

    def test_hot_by_access(self):
        entry = MemoryEntry(content="frequent", timestamp=time.time() - 9999, access_count=10)
        assert self.cc.classify_temperature(entry, time.time()) == "hot"

    def test_warm(self):
        now = time.time()
        entry = MemoryEntry(content="recent", timestamp=now - 600)  # 10 min
        assert self.cc.classify_temperature(entry, now) == "warm"

    def test_cold(self):
        now = time.time()
        entry = MemoryEntry(content="old", timestamp=now - 99999, access_count=0)
        assert self.cc.classify_temperature(entry, now) == "cold"


class TestCompress:
    def test_empty_input(self):
        cc = ContextCompressor()
        assert cc.compress([], 4096) == []

    def test_keeps_hot(self):
        cc = ContextCompressor()
        hot = MemoryEntry(content="x", timestamp=time.time(), access_count=99)
        result = cc.compress([hot], 4096)
        assert len(result) == 1
        assert result[0].content == "x"

    def test_evicts_cold(self):
        cc = ContextCompressor()
        now = time.time()
        cold = MemoryEntry(content="old", timestamp=now - 99999, access_count=0)
        result = cc.compress([cold], 4096)
        assert len(result) == 0

    def test_summarizes_warm(self):
        cc = ContextCompressor()
        now = time.time()
        warm1 = MemoryEntry(content="first", timestamp=now - 600, access_count=1)
        warm2 = MemoryEntry(content="second", timestamp=now - 700, access_count=1)
        result = cc.compress([warm1, warm2], 4096)
        assert len(result) == 1
        assert _SUMMARY_TAG in result[0].tags
        assert "first" in result[0].content
        assert "second" in result[0].content

    def test_budget_trim(self):
        cc = ContextCompressor()
        now = time.time()
        entries = [
            MemoryEntry(content="a", timestamp=now - 10, access_count=99, token_count=2000),
            MemoryEntry(content="b", timestamp=now - 20, access_count=99, token_count=2000),
        ]
        result = cc.compress(entries, token_budget=2500)
        assert len(result) == 1  # only one fits


class TestSummarizeBatch:
    def test_empty(self):
        cc = ContextCompressor()
        result = cc.summarize_batch([])
        assert result.content == ""
        assert _SUMMARY_TAG in result.tags

    def test_single(self):
        cc = ContextCompressor()
        entry = MemoryEntry(content="only", tags=["a"])
        result = cc.summarize_batch([entry])
        assert result is entry  # same object

    def test_multiple(self):
        cc = ContextCompressor()
        now = time.time()
        e1 = MemoryEntry(content="hello", timestamp=now, tags=["greeting"], access_count=3)
        e2 = MemoryEntry(content="world", timestamp=now - 100, tags=["place"], access_count=5)
        result = cc.summarize_batch([e1, e2])
        assert "hello" in result.content
        assert "world" in result.content
        assert "greeting" in result.tags
        assert "place" in result.tags
        assert _SUMMARY_TAG in result.tags
        assert result.access_count == 8
        assert result.timestamp == now


class TestEvictCold:
    def test_none_evicted_when_recent(self):
        cc = ContextCompressor(hot_access_floor=3)
        now = time.time()
        entry = MemoryEntry(content="fresh", timestamp=now - 10, access_count=0)
        kept, evicted = cc.evict_cold([entry], threshold=3600, now=now)
        assert len(kept) == 1
        assert len(evicted) == 0

    def test_old_low_access_evicted(self):
        cc = ContextCompressor(hot_access_floor=3)
        now = time.time()
        entry = MemoryEntry(content="stale", timestamp=now - 99999, access_count=0)
        kept, evicted = cc.evict_cold([entry], threshold=100, now=now)
        assert len(evicted) == 1
        assert len(kept) == 0

    def test_old_high_access_kept(self):
        cc = ContextCompressor(hot_access_floor=3)
        now = time.time()
        entry = MemoryEntry(content="valuable", timestamp=now - 99999, access_count=5)
        kept, evicted = cc.evict_cold([entry], threshold=100, now=now)
        assert len(kept) == 1
