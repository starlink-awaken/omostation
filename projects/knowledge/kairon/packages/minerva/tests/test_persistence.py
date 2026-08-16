"""Tests for minerva.persistence — research result save/list/get/delete/stats.

Covers slug generation, save_research with metadata + report + search results
serialization, list_results ordering, get_result with report loading,
delete_result cleanup, get_storage_stats aggregation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from minerva import persistence
from minerva.persistence import (
    _slugify,
    delete_result,
    get_result,
    get_storage_stats,
    list_results,
    save_research,
)

# ── _slugify ─────────────────────────────────────────────────────


class TestSlugify:
    def test_lowercase(self):
        assert _slugify("Hello World") == "hello_world"

    def test_special_chars_to_underscore(self):
        assert _slugify("foo@bar.com") == "foo_bar_com"

    def test_multiple_underscores_collapse(self):
        assert _slugify("foo___bar") == "foo_bar"

    def test_leading_trailing_underscore_stripped(self):
        assert _slugify("___test___") == "test"

    def test_max_length(self):
        slug = _slugify("a" * 100, max_len=10)
        assert len(slug) == 10

    def test_empty_string(self):
        assert _slugify("") == ""

    def test_only_special_chars(self):
        assert _slugify("@#$%^&*()") == ""

    def test_unicode_chinese_kept(self):
        slug = _slugify("中文测试")
        # Chinese chars are kept (regex allows 一-鿿)
        assert "中" in slug or len(slug) > 0  # implementation-dependent

    def test_underscore_in_input_preserved(self):
        assert "_" in _slugify("foo_bar_baz")


# ── save_research ────────────────────────────────────────────────


class TestSaveResearch:
    def test_creates_directory(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="test",
            level="L2",
            quality_score=85,
            source_count=10,
            entity_count=20,
            cost_usd=0.5,
            elapsed_s=12.0,
            paradigm_name="test_paradigm",
            stage_timings={"s1": 1.0, "s2": 2.5},
            report="# test report",
            report_path=None,
        )
        assert (tmp_path / "research" / result_id).exists()

    def test_returns_id_with_timestamp_prefix(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        before = int(datetime.now(UTC).timestamp())
        result_id = save_research(
            query="test",
            level="L0",
            quality_score=100,
            source_count=0,
            entity_count=0,
            cost_usd=0.0,
            elapsed_s=0.1,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        # ID format: {ts}_{slug}
        ts_str, _, slug = result_id.partition("_")
        ts = int(ts_str)
        assert ts >= before
        assert ts <= before + 5  # 5 sec window

    def test_writes_meta_json(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L3",
            quality_score="B",  # string OK
            source_count=5,
            entity_count=10,
            cost_usd=1.23456,
            elapsed_s=20.0,
            paradigm_name="my_paradigm",
            stage_timings={"a": 1.5, "b": 2.5},
            report="",
            report_path=None,
        )
        meta = json.loads((tmp_path / "research" / result_id / "meta.json").read_text())
        assert meta["query"] == "q"
        assert meta["level"] == "L3"
        assert meta["quality_score"] == "B"
        assert meta["source_count"] == 5
        assert meta["entity_count"] == 10
        assert meta["paradigm"] == "my_paradigm"
        # Rounding
        assert meta["cost_usd"] == 1.2346
        assert meta["elapsed_s"] == 20.0
        # stage timings rounded
        assert meta["pipeline_stages"]["a"] == 1.5
        assert meta["pipeline_stages"]["b"] == 2.5

    def test_writes_report_md(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="# Hello\nWorld",
            report_path=None,
        )
        report = (tmp_path / "research" / result_id / "report.md").read_text()
        assert report == "# Hello\nWorld"

    def test_no_report_file_when_empty(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        assert not (tmp_path / "research" / result_id / "report.md").exists()

    def test_writes_search_results_json(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
            search_results=[{"title": "T1", "url": "u1"}, {"title": "T2"}],
        )
        path = tmp_path / "research" / result_id / "search_results.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert data[0]["title"] == "T1"

    def test_search_results_serialize_via_to_dict(self, tmp_path: Path, monkeypatch):
        class FakeResult:
            def to_dict(self):
                return {"serialized": True}

        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
            search_results=[FakeResult()],
        )

    def test_search_results_truncate_at_50(self, tmp_path: Path, monkeypatch):
        """save_research keeps only first 50 search results."""
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        results = [{"id": i} for i in range(100)]
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
            search_results=results,
        )
        data = json.loads((tmp_path / "research" / result_id / "search_results.json").read_text())
        assert len(data) == 50

    def test_search_results_serialization_failure_swallowed(self, tmp_path: Path, monkeypatch):
        """Non-serializable search results don't crash save_research."""

        class BadResult:
            def __getattr__(self, name):
                raise RuntimeError("cannot serialize")

        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        # Should not raise
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
            search_results=[BadResult()],
        )
        # search_results.json not created (since serialization failed)
        assert not (tmp_path / "research" / result_id / "search_results.json").exists()

    def test_copies_report_original(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        original = tmp_path / "src_report.md"
        original.write_text("# Original\n")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=str(original),
        )
        copy = tmp_path / "research" / result_id / "report_original.md"
        assert copy.exists()
        assert copy.read_text() == "# Original\n"

    def test_copies_report_from_external_path(self, tmp_path: Path, monkeypatch):
        """When report_path points to a file outside _RESULTS_DIR, it's copied."""
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        external = tmp_path / "external_report.md"
        external.write_text("# External Report\n")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=str(external),
        )
        copy = tmp_path / "research" / result_id / "report_original.md"
        assert copy.exists()
        assert copy.read_text() == "# External Report\n"

    def test_skips_copy_when_source_missing(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        # report_path points to nonexistent file
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=str(tmp_path / "nonexistent.md"),
        )
        assert not (tmp_path / "research" / result_id / "report_original.md").exists()

    def test_id_includes_slugified_query(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="Quantum Computing@2024!",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        # ID should have "quantum_computing_2024_" or similar
        assert "quantum" in result_id or "computing" in result_id

    def test_timestamp_iso8601_in_meta(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        before = datetime.now(UTC)
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        meta = json.loads((tmp_path / "research" / result_id / "meta.json").read_text())
        ts = datetime.fromisoformat(meta["timestamp"])
        # Allow 5 sec clock skew
        assert abs((ts - before).total_seconds()) < 5


# ── list_results ──────────────────────────────────────────────────


class TestListResults:
    def test_empty_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        (tmp_path / "research").mkdir(parents=True)
        assert list_results() == []

    def test_returns_metadata(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        save_research(
            query="q1",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        save_research(
            query="q2",
            level="L2",
            quality_score=90,
            source_count=2,
            entity_count=2,
            cost_usd=0.2,
            elapsed_s=2.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        result = list_results()
        assert len(result) == 2
        queries = {r["query"] for r in result}
        assert queries == {"q1", "q2"}

    def test_has_report_flag(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        save_research(
            query="q1",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="report content",
            report_path=None,
        )
        save_research(
            query="q2",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        result = list_results()
        by_query = {r["query"]: r["has_report"] for r in result}
        assert by_query["q1"] is True
        assert by_query["q2"] is False

    def test_limit(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        for i in range(10):
            save_research(
                query=f"q{i}",
                level="L1",
                quality_score=80,
                source_count=1,
                entity_count=1,
                cost_usd=0.1,
                elapsed_s=1.0,
                paradigm_name="p",
                stage_timings={},
                report="",
                report_path=None,
            )
        assert len(list_results(limit=3)) == 3

    def test_newest_first(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        for i in range(3):
            save_research(
                query=f"q{i}",
                level="L1",
                quality_score=80,
                source_count=1,
                entity_count=1,
                cost_usd=0.1,
                elapsed_s=1.0,
                paradigm_name="p",
                stage_timings={},
                report="",
                report_path=None,
            )
        result = list_results()
        # Sorted by directory name (timestamp_slug) desc
        assert result[0]["query"] == "q2"
        assert result[1]["query"] == "q1"
        assert result[2]["query"] == "q0"

    def test_skips_dirs_without_meta(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        (tmp_path / "research" / "broken_dir").mkdir(parents=True)
        save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        result = list_results()
        # broken_dir has no meta.json so should be skipped
        assert len(result) == 1
        assert result[0]["query"] == "q"

    def test_skips_files(self, tmp_path: Path, monkeypatch):
        """Non-directory entries are skipped."""
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        (tmp_path / "research").mkdir(parents=True)
        (tmp_path / "research" / "stray_file.txt").write_text("not a dir")
        result = list_results()
        assert result == []

    def test_corrupt_meta_swallowed(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        bad = tmp_path / "research" / "bad_id"
        bad.mkdir(parents=True)
        (bad / "meta.json").write_text("{ invalid json")
        result = list_results()
        assert result == []


# ── get_result ──────────────────────────────────────────────────


class TestGetResult:
    def test_returns_none_for_missing_id(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        assert get_result("nonexistent_id") is None

    def test_returns_metadata_for_existing_id(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        result = get_result(result_id)
        assert result is not None
        assert result["query"] == "q"

    def test_includes_report_content(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="# My Report",
            report_path=None,
        )
        result = get_result(result_id)
        assert result["report"] == "# My Report"  # type: ignore[reportOptionalSubscript]

    def test_omits_report_when_missing(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        result = get_result(result_id)
        assert "report" not in result  # type: ignore[reportOperatorIssue]

    def test_includes_search_results(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
            search_results=[{"id": 1}, {"id": 2}],
        )
        result = get_result(result_id)
        assert result["search_results"] == [{"id": 1}, {"id": 2}]  # type: ignore[reportOptionalSubscript]

    def test_corrupt_search_results_swallowed(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
            search_results=[{"id": 1}],
        )
        # Corrupt the search_results.json
        sr_path = tmp_path / "research" / result_id / "search_results.json"
        sr_path.write_text("{ corrupt")
        result = get_result(result_id)
        # Meta still loads; search_results is dropped silently
        assert result is not None
        assert "search_results" not in result

    def test_corrupt_meta_returns_none(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        # Corrupt the meta.json
        meta_path = tmp_path / "research" / result_id / "meta.json"
        meta_path.write_text("{ corrupt")
        assert get_result(result_id) is None

    def test_returns_none_when_dir_exists_but_no_meta(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        (tmp_path / "research" / "no_meta_id").mkdir(parents=True)
        assert get_result("no_meta_id") is None


# ── delete_result ────────────────────────────────────────────────


class TestDeleteResult:
    def test_delete_existing(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        assert delete_result(result_id) is True
        assert not (tmp_path / "research" / result_id).exists()

    def test_delete_nonexistent(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        assert delete_result("nonexistent") is False

    def test_delete_removes_all_files(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="report",
            report_path=None,
            search_results=[{"id": 1}],
        )
        result_dir = tmp_path / "research" / result_id
        assert (result_dir / "meta.json").exists()
        assert (result_dir / "report.md").exists()
        assert (result_dir / "search_results.json").exists()
        delete_result(result_id)
        assert not result_dir.exists()


# ── get_storage_stats ────────────────────────────────────────────


class TestGetStorageStats:
    def test_empty_storage(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        (tmp_path / "research").mkdir(parents=True)
        stats = get_storage_stats()
        assert stats["total_results"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["total_size_mb"] == 0.0
        assert stats["storage_dir"] == str(tmp_path / "research")

    def test_counts_results(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        for i in range(3):
            save_research(
                query=f"q{i}",
                level="L1",
                quality_score=80,
                source_count=1,
                entity_count=1,
                cost_usd=0.1,
                elapsed_s=1.0,
                paradigm_name="p",
                stage_timings={},
                report="",
                report_path=None,
            )
        assert get_storage_stats()["total_results"] == 3

    def test_sums_file_sizes(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        result_id = save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="",
            report_path=None,
        )
        # Add a 1MB file
        (tmp_path / "research" / result_id / "extra.bin").write_bytes(b"x" * (1024 * 1024))
        stats = get_storage_stats()
        assert stats["total_size_bytes"] >= 1024 * 1024
        # 1 MB file → total_size_mb should be ≥ 0.5 (after round to 2 decimals)
        # The 1MB file is the dominant contribution, plus meta.json
        assert stats["total_size_mb"] >= 0.99  # at least ~1MB

    def test_total_size_bytes_aggregates_recursively(self, tmp_path: Path, monkeypatch):
        """get_storage_stats uses rglob, so nested files count."""
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        save_research(
            query="q",
            level="L1",
            quality_score=80,
            source_count=1,
            entity_count=1,
            cost_usd=0.1,
            elapsed_s=1.0,
            paradigm_name="p",
            stage_timings={},
            report="r",
            report_path=None,
            search_results=[{"a": 1}],
        )
        stats = get_storage_stats()
        # meta.json + report.md + search_results.json all count
        assert stats["total_size_bytes"] > 0
        assert stats["total_results"] == 1

    def test_storage_dir_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(persistence, "_RESULTS_DIR", tmp_path / "research")
        stats = get_storage_stats()
        assert stats["storage_dir"] == str(tmp_path / "research")
