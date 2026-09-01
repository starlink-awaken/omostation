"""Tests for bin/adr/adr-coverage.py parse_index regex.

Regression: original regex `[0-9]{4}-[a-z0-9-]+.md` matched `2026-07-24.md`
inside INDEX.md table date columns, causing false-positive "INDEX 引用不存在的文件".

Fix: anchor pattern to table column boundaries (| or whitespace) so 4-digit
date-like strings inside table cells are not extracted as ADR filenames.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "adr" / "adr-coverage.py"


def _load_module():
    if str(SCRIPT.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("adr_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def adr_coverage():
    return _load_module()


def test_parse_index_real_index_no_date_false_positive(adr_coverage):
    """Regression: live INDEX.md (2026-07-24 dates) must not produce '2026-07-24.md' ref."""
    index_path = Path(__file__).resolve().parents[1] / ".omo" / "_knowledge" / "decisions" / "INDEX.md"
    if not index_path.exists():
        pytest.skip("INDEX.md not present in this checkout")
    data = adr_coverage.parse_index(index_path)
    assert "2026-07-24.md" not in data["adrs"], "regex regression: 2026-07-24.md matched as ADR file from date column"


def test_parse_index_real_index_has_0146_ref(adr_coverage):
    """Sanity: 0146-8stage-stability-declaration.md is referenced in INDEX."""
    index_path = Path(__file__).resolve().parents[1] / ".omo" / "_knowledge" / "decisions" / "INDEX.md"
    if not index_path.exists():
        pytest.skip("INDEX.md not present in this checkout")
    data = adr_coverage.parse_index(index_path)
    assert "0146-8stage-stability-declaration.md" in data["adrs"]


def test_parse_index_handcrafted_minimal():
    """Synthetic INDEX snippet covering the bug scenarios."""
    mod = _load_module()
    snippet = (
        "| 0146 | 8stage declaration | ACCEPTED | 2026-07-06 | team | 0146-8stage-stability-declaration.md |\n"
        "| 0234 | some adr | ACCEPTED | 2026-07-24 | team | 0234-bet-c87a-closeout.md |\n"
    )
    data = mod.parse_index_from_str(snippet) if hasattr(mod, "parse_index_from_str") else _parse_text(mod, snippet)
    assert "0146-8stage-stability-declaration.md" in data["adrs"]
    assert "0234-bet-c87a-closeout.md" in data["adrs"]
    assert "2026-07-24.md" not in data["adrs"]
    assert "2026-07-06.md" not in data["adrs"]


def test_check_coverage_treats_signal_numbers_as_retired(adr_coverage, tmp_path: Path):
    """ADR-0443: a draft moved to signals retires its old number without creating a decisions gap."""
    decisions = tmp_path / "decisions"
    signals = tmp_path / "signals"
    decisions.mkdir()
    signals.mkdir()
    frontmatter = "---\nstatus: accepted\nlifecycle: spec\nowner: test\nlast-reviewed: 2026-08-31\n---\n"
    (decisions / "0001-first.md").write_text(f"{frontmatter.replace('---\\n', '---\\nid: ADR-0001\\n', 1)}# first\n")
    (decisions / "0003-third.md").write_text(f"{frontmatter.replace('---\\n', '---\\nid: ADR-0003\\n', 1)}# third\n")
    (signals / "0002-retired-draft.md").write_text("---\nid: ADR-0002\n---\n# signal only\n")
    (signals / "2026-08-30-note.md").write_text(
        "---\nid: signal://evolution/date-note\n---\n# date-prefixed signal\n"
    )
    index = decisions / "INDEX.md"
    index.write_text("0001-first.md\n0003-third.md\n")

    result = adr_coverage.check_coverage(decisions, index)

    assert result["retired_signal_numbers"] == [2]
    assert result["missing_numbers"] == []


def _parse_text(mod, text: str):
    """Wrap parse_index to accept string instead of path."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return mod.parse_index(path)
    finally:
        path.unlink()
