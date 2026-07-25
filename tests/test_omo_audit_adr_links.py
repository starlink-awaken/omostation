r"""Regression test for omo_audit ADR link extraction.

Bug: omo_audit used `\\b(\\d{4})-([a-z0-9-]+)\\.md\\b` which matched
date-like 4-digit strings in INDEX.md table cells (e.g. "2026-07-24.md"
from a date column). Fix: anchor on table column boundary (| or
whitespace) so ADR file refs sit in their own table cell.

Spans the ommostation workspace, not kairon, so we load by absolute
path rather than relying on sys.path.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


WORKSPACE = Path(__file__).resolve().parents[1]
OMO_AUDIT = WORKSPACE / "projects" / "omo" / "src" / "omo" / "omo_audit.py"
INDEX_PATH = WORKSPACE / ".omo" / "_knowledge" / "decisions" / "INDEX.md"


def _load_omo_audit():
    if str(OMO_AUDIT.parent.parent) not in sys.path:
        sys.path.insert(0, str(OMO_AUDIT.parent.parent))
    spec = importlib.util.spec_from_file_location("omo.omo_audit", OMO_AUDIT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["omo.omo_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def omo_audit():
    return _load_omo_audit()


def test_adr_links_no_date_false_positive(omo_audit):
    """Live INDEX.md must not produce '2026-07-24.md' as a broken ref."""
    if not INDEX_PATH.exists():
        pytest.skip("INDEX.md not present in this checkout")
    result = omo_audit.governance_check_adr_links()
    assert result.severity in ("ok", "warn"), (
        f"adr links check failed: severity={result.severity} message={result.message}"
    )
    for d in result.details:
        assert "2026-07-24.md" not in d, (
            f"regex regression: 2026-07-24.md matched as ADR file from date column; details={d}"
        )


def test_adr_links_handcrafted():
    """Synthetic INDEX snippet covering bug scenarios."""
    mod = _load_omo_audit()
    snippet = (
        "| 0146 | 8stage declaration | ACCEPTED | 2026-07-06 | team | 0146-8stage-stability-declaration.md |\n"
        "| 0234 | some adr | ACCEPTED | 2026-07-24 | team | 0234-bet-c87a-closeout.md |\n"
    )
    import shutil
    import tempfile
    tmpdir = Path(tempfile.mkdtemp())
    try:
        decisions = tmpdir / "decisions"
        decisions.mkdir()
        (decisions / "0146-8stage-stability-declaration.md").write_text("# 0146\n")
        (decisions / "0234-bet-c87a-closeout.md").write_text("# 0234\n")
        idx = tmpdir / "INDEX.md"
        idx.write_text(snippet)
        # DECISIONS_DIR is a module-level Path; we override it for the test.
        original = mod.DECISIONS_DIR
        setattr(mod, "DECISIONS_DIR", decisions)
        try:
            result = mod.governance_check_adr_links()
        finally:
            setattr(mod, "DECISIONS_DIR", original)
        details_str = " ".join(result.details)
        assert "2026-07-24.md" not in details_str
        assert "2026-07-06.md" not in details_str
    finally:
        shutil.rmtree(tmpdir)
