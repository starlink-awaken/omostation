"""Tests for kairon_lib.utils.deduplicator — ContentDeduplicator."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import tempfile
from pathlib import Path

import pytest
from kairon_utils.deduplicator import ContentDeduplicator


class TestContentDeduplicator:
    @pytest.fixture
    def tmp_cache(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_compute_content_hash(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        h1 = dedup.compute_content_hash("hello")
        h2 = dedup.compute_content_hash("hello")
        h3 = dedup.compute_content_hash("world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA256 hex

    @pytest.mark.asyncio
    async def test_is_duplicate_new_content(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        result = await dedup.is_duplicate("new content", "src1")
        assert result is False  # First time — not a duplicate

    @pytest.mark.asyncio
    async def test_is_duplicate_detects_duplicate(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        await dedup.is_duplicate("hello", "src1")
        result = await dedup.is_duplicate("hello", "src1")
        assert result is True  # Duplicate for same source

    @pytest.mark.asyncio
    async def test_same_content_different_sources(self, tmp_cache):
        """Same content from different sources is NOT a duplicate."""
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        await dedup.is_duplicate("hello", "src1")
        result = await dedup.is_duplicate("hello", "src2")
        assert result is False  # Different source

    @pytest.mark.asyncio
    async def test_mark_seen(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        await dedup.mark_seen("data", "src")
        result = await dedup.is_duplicate("data", "src")
        assert result is True

    def test_get_stats(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        stats = dedup.get_stats()
        assert stats["total_seen"] == 0
        assert stats["cache_dir"] == str(tmp_cache)

    @pytest.mark.asyncio
    async def test_get_stats_after_seen(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        await dedup.is_duplicate("a", "s1")
        await dedup.is_duplicate("b", "s1")
        stats = dedup.get_stats()
        assert stats["total_seen"] == 2

    def test_clear_cache(self, tmp_cache):
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        dedup._seen_hashes.add("k1")
        dedup._seen_hashes.add("k2")
        dedup.clear_cache()
        assert len(dedup._seen_hashes) == 0

    def test_cache_persistence(self, tmp_cache):
        """Seen hashes persist to disk and reload on new instance."""
        dedup1 = ContentDeduplicator(cache_dir=tmp_cache)
        dedup1._seen_hashes.add("src:hash1")
        dedup1._save_cache()

        dedup2 = ContentDeduplicator(cache_dir=tmp_cache)
        assert "src:hash1" in dedup2._seen_hashes

    def test_cache_load_with_corrupted_file(self, tmp_cache):
        """Corrupted cache file doesn't crash loading."""
        cache_file = tmp_cache / "seen_hashes.json"
        cache_file.write_text("not valid json")
        dedup = ContentDeduplicator(cache_dir=tmp_cache)
        # Falls back to empty set
        assert dedup._seen_hashes == set()
