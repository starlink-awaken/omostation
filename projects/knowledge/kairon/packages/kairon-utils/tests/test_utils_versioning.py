"""Tests for kairon_lib.utils.versioning — ContentVersion, ContentVersionTracker."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import tempfile
from pathlib import Path

import pytest
from kairon_utils.versioning import ContentVersion, ContentVersionTracker


class TestContentVersion:
    def test_to_dict(self):
        v = ContentVersion(
            content_hash="abc123",
            previous_hash=None,
            version_number=1,
            source_id="src1",
            harvested_at="2025-01-01T00:00:00",
            content_size=10,
            metadata={"key": "val"},
        )
        d = v.to_dict()
        assert d["content_hash"] == "abc123"
        assert d["version_number"] == 1
        assert d["metadata"] == {"key": "val"}

    def test_from_dict(self):
        d = {
            "content_hash": "def456",
            "previous_hash": "abc123",
            "version_number": 2,
            "source_id": "src1",
            "harvested_at": "2025-01-02T00:00:00",
            "content_size": 20,
            "metadata": {},
        }
        v = ContentVersion.from_dict(d)
        assert v.content_hash == "def456"
        assert v.previous_hash == "abc123"
        assert v.version_number == 2


class TestContentVersionTracker:
    @pytest.fixture
    def tmp_storage(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_compute_content_hash(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        h1 = tracker.compute_content_hash("content")
        h2 = tracker.compute_content_hash("content")
        assert h1 == h2
        assert len(h1) == 64

    @pytest.mark.asyncio
    async def test_record_version_creates_first_version(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        version = await tracker.record_version("src1", "hello world", {"type": "test"})
        assert version.version_number == 1
        assert version.source_id == "src1"
        assert version.content_size == 11
        assert version.previous_hash is None
        assert version.metadata == {"type": "test"}

    @pytest.mark.asyncio
    async def test_record_version_increments(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        v1 = await tracker.record_version("src1", "version 1")
        v2 = await tracker.record_version("src1", "version 2")
        assert v1.version_number == 1
        assert v2.version_number == 2
        assert v2.previous_hash == v1.content_hash

    @pytest.mark.asyncio
    async def test_get_latest_version(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        await tracker.record_version("src1", "v1")
        await tracker.record_version("src1", "v2")
        await tracker.record_version("src1", "v3")
        latest = await tracker.get_latest_version("src1")
        assert latest is not None
        assert latest.version_number == 3

    @pytest.mark.asyncio
    async def test_get_latest_version_nonexistent(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        result = await tracker.get_latest_version("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_version_history(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        await tracker.record_version("src1", "v1")
        await tracker.record_version("src1", "v2")
        history = await tracker.get_version_history("src1", limit=10)
        assert len(history) == 2
        # Newest first
        assert history[0].version_number == 2
        assert history[1].version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_history_limit(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        for i in range(5):
            await tracker.record_version("src1", f"v{i}")
        history = await tracker.get_version_history("src1", limit=2)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_compare_versions(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        v1 = await tracker.record_version("src1", "small")
        v2 = await tracker.record_version("src1", "larger content")
        result = await tracker.compare_versions("src1", v1.content_hash, v2.content_hash)
        assert result["status"] == "compared"
        assert result["version1"] == 1
        assert result["version2"] == 2
        assert result["size_delta"] > 0

    @pytest.mark.asyncio
    async def test_compare_versions_not_found(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        result = await tracker.compare_versions("src1", "nonexistent1", "nonexistent2")
        assert result["status"] == "not_found"

    def test_get_statistics_empty(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        stats = tracker.get_statistics()
        assert stats["total_sources"] == 0
        assert stats["total_versions"] == 0

    @pytest.mark.asyncio
    async def test_get_statistics(self, tmp_storage):
        tracker = ContentVersionTracker(storage_dir=tmp_storage)
        await tracker.record_version("src1", "data1")
        await tracker.record_version("src1", "data2")
        await tracker.record_version("src2", "data3")
        stats = tracker.get_statistics()
        assert stats["total_sources"] == 2
        assert stats["total_versions"] == 3
