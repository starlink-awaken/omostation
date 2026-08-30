import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from project_health_check import frontmatter_coverage, health_snapshot


def test_frontmatter_coverage_counts(tmp_path):
    (tmp_path / "a.md").write_text("---\nstatus: active\n---\n# A")
    (tmp_path / "b.md").write_text("# B (no frontmatter)")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.md").write_text("---\nstatus: draft\n---\n# C")
    result = frontmatter_coverage(str(tmp_path))
    assert result["total"] == 3
    assert result["with_frontmatter"] == 2
    assert result["coverage_pct"] == 66


def test_health_snapshot_includes_key_metrics(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    snap = health_snapshot(str(tmp_path))
    assert "frontmatter" in snap
    assert "adr_count" in snap
    assert "md_files" in snap
