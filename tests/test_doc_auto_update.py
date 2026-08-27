"""Tests for bin/gac/doc-auto-update.py — documentation auto-update detector."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "gac" / "doc-auto-update.py"
_MODULE = "_doc_auto_update_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    return _load()


# ---------------------------------------------------------------------------
# check_stale_docs
# ---------------------------------------------------------------------------


def test_check_stale_docs_returns_list(tool, tmp_path):
    """Empty directory → empty list."""
    result = tool.check_stale_docs(tmp_path, threshold_days=7)
    assert isinstance(result, list)
    assert result == []


def test_check_stale_docs_finds_stale_file(tool, tmp_path):
    """A file with mtime 10 days ago is detected as stale (threshold=7)."""
    f = tmp_path / "old.md"
    f.write_text("content")
    # Set mtime to 10 days ago
    old_time = (datetime.now(UTC) - timedelta(days=10)).timestamp()
    f.touch()
    import os

    os.utime(f, (old_time, old_time))

    result = tool.check_stale_docs(tmp_path, threshold_days=7, base_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["file"] == "old.md"
    assert result[0]["age_days"] >= 10


def test_check_stale_docs_ignores_fresh_file(tool, tmp_path):
    """A file with today's mtime is NOT stale."""
    f = tmp_path / "fresh.md"
    f.write_text("content")

    result = tool.check_stale_docs(tmp_path, threshold_days=7)
    assert result == []


def test_check_stale_docs_ignores_subdirectories(tool, tmp_path):
    """Subdirectories are skipped, only files are checked."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    result = tool.check_stale_docs(tmp_path, threshold_days=7)
    assert result == []


def test_check_stale_docs_nonexistent_dir(tool):
    """Non-existent directory returns empty list."""
    result = tool.check_stale_docs(Path("/nonexistent/path"), threshold_days=7)
    assert result == []


def test_check_stale_docs_custom_threshold(tool, tmp_path):
    """Threshold=1 catches files from yesterday."""
    f = tmp_path / "yesterday.md"
    f.write_text("content")
    old_time = (datetime.now(UTC) - timedelta(days=2)).timestamp()
    import os

    os.utime(f, (old_time, old_time))

    # threshold=3 → NOT stale
    assert tool.check_stale_docs(tmp_path, threshold_days=3, base_dir=tmp_path) == []

    # threshold=1 → stale
    result = tool.check_stale_docs(tmp_path, threshold_days=1, base_dir=tmp_path)
    assert len(result) == 1


def test_check_stale_docs_multiple_files(tool, tmp_path):
    """Mixed fresh and stale files — only stale ones returned."""
    import os

    fresh = tmp_path / "fresh.md"
    fresh.write_text("content")

    stale1 = tmp_path / "stale1.yaml"
    stale1.write_text("data")
    old_time = (datetime.now(UTC) - timedelta(days=15)).timestamp()
    os.utime(stale1, (old_time, old_time))

    stale2 = tmp_path / "stale2.json"
    stale2.write_text("{}")
    old_time2 = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(stale2, (old_time2, old_time2))

    result = tool.check_stale_docs(tmp_path, threshold_days=7, base_dir=tmp_path)
    names = {Path(r["file"]).name for r in result}
    assert names == {"stale1.yaml", "stale2.json"}


# ---------------------------------------------------------------------------
# generate_update_plan
# ---------------------------------------------------------------------------


def test_generate_update_plan_empty(tool):
    """Empty stale list → empty plan."""
    assert tool.generate_update_plan([]) == []


def test_generate_update_plan_yaml_regenerate(tool):
    """YAML files get 'regenerate' action."""
    stale = [{"file": "docs/generated/capability-registry.yaml", "age_days": 10}]
    plan = tool.generate_update_plan(stale)
    assert len(plan) == 1
    assert plan[0]["action"] == "regenerate"
    assert plan[0]["file"] == "docs/generated/capability-registry.yaml"
    assert "refresh" in plan[0]["reason"].lower()


def test_generate_update_plan_json_regenerate(tool):
    """JSON files get 'regenerate' action."""
    stale = [{"file": "docs/generated/bin-tool-registry.json", "age_days": 8}]
    plan = tool.generate_update_plan(stale)
    assert plan[0]["action"] == "regenerate"


def test_generate_update_plan_md_review_and_refresh(tool):
    """Markdown files get 'review-and-refresh' action."""
    stale = [{"file": "docs/generated/project-layer-index.md", "age_days": 14}]
    plan = tool.generate_update_plan(stale)
    assert plan[0]["action"] == "review-and-refresh"
    assert "verify" in plan[0]["reason"].lower()


def test_generate_update_plan_unknown_ext_review(tool):
    """Unknown extensions get generic 'review' action."""
    stale = [{"file": "docs/generated/something.xyz", "age_days": 9}]
    plan = tool.generate_update_plan(stale)
    assert plan[0]["action"] == "review"


def test_generate_update_plan_preserves_order(tool):
    """Plan preserves input order."""
    stale = [
        {"file": "docs/generated/a.md", "age_days": 10},
        {"file": "docs/generated/b.yaml", "age_days": 20},
        {"file": "docs/generated/c.json", "age_days": 30},
    ]
    plan = tool.generate_update_plan(stale)
    assert [p["file"] for p in plan] == [
        "docs/generated/a.md",
        "docs/generated/b.yaml",
        "docs/generated/c.json",
    ]


def test_generate_update_plan_age_in_reason(tool):
    """Age appears in the reason string."""
    stale = [{"file": "docs/generated/test.md", "age_days": 42}]
    plan = tool.generate_update_plan(stale)
    assert "42" in plan[0]["reason"]


# ---------------------------------------------------------------------------
# Integration: check_stale_docs → generate_update_plan pipeline
# ---------------------------------------------------------------------------


def test_pipeline_end_to_end(tool, tmp_path):
    """Full pipeline: detect stale → generate plan."""
    import os

    stale_f = tmp_path / "old.yaml"
    stale_f.write_text("data")
    old_time = (datetime.now(UTC) - timedelta(days=20)).timestamp()
    os.utime(stale_f, (old_time, old_time))

    fresh_f = tmp_path / "new.md"
    fresh_f.write_text("content")

    stale = tool.check_stale_docs(tmp_path, threshold_days=7, base_dir=tmp_path)
    plan = tool.generate_update_plan(stale)

    assert len(stale) == 1
    assert len(plan) == 1
    assert plan[0]["action"] == "regenerate"
