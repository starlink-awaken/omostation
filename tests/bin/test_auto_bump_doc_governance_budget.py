#!/usr/bin/env python3
"""Unit tests for auto-bump-doc-governance-budget.py.

Tests parser, find_exception, bump_budget functions without running subprocess.
Run: python3 tests/bin/test_auto_bump_doc_governance_budget.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "auto-bump-doc-governance-budget.py"


def _load():
    spec = importlib.util.spec_from_file_location("autobump", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["autobump"] = m
    spec.loader.exec_module(m)
    return m


def test_parse_single_failure():
    m = _load()
    sample = """
.omo/_truth/registry/document-governance.yaml: warning_budget_exceeded [error]
  warning exception legacy-omo-knowledge-enums has been exceeded
  (evidence: invalid_metadata:omo-knowledge count=68 max=63)
"""
    failures = m.parse_failure_evidence(sample)
    assert len(failures) == 1
    f = failures[0]
    assert f["exception_id"] == "legacy-omo-knowledge-enums"
    assert f["rule"] == "invalid_metadata"
    assert f["surface"] == "omo-knowledge"
    assert f["count"] == 68


def test_parse_multiple_failures():
    m = _load()
    sample = """
warning exception legacy-omo-knowledge-enums has been exceeded
(evidence: invalid_metadata:omo-knowledge count=68 max=63)
warning exception legacy-docs-frontmatter has been exceeded
(evidence: missing_frontmatter:docs-discoverable count=180 max=175)
warning exception concurrent-plans-orphan-docs has been exceeded
(evidence: orphan_document:docs-discoverable count=10 max=8)
"""
    failures = m.parse_failure_evidence(sample)
    assert len(failures) == 3
    exc_ids = {f["exception_id"] for f in failures}
    assert exc_ids == {
        "legacy-omo-knowledge-enums",
        "legacy-docs-frontmatter",
        "concurrent-plans-orphan-docs",
    }


def test_find_exception_by_rule_surface():
    m = _load()
    yaml = """
warning_exceptions:
  entries:
    - id: legacy-omo-knowledge-enums
      rule: invalid_metadata
      surface: omo-knowledge
      max_findings: 70
      expires: 2026-10-31
      reason: x
    - id: legacy-docs-enums
      rule: invalid_metadata
      surface: docs-discoverable
      max_findings: 24
      expires: 2026-10-31
      reason: y
"""
    cur, exc_id, line_no = m.find_exception(yaml, "invalid_metadata", "omo-knowledge")
    assert cur == 70
    assert exc_id == "legacy-omo-knowledge-enums"
    assert line_no > 0


def test_find_exception_returns_none_when_missing():
    m = _load()
    yaml = """
warning_exceptions:
  entries:
    - id: legacy-x
      rule: invalid_metadata
      surface: omo-knowledge
      max_findings: 5
"""
    cur, exc_id, line_no = m.find_exception(yaml, "missing_frontmatter", "omo-knowledge")
    assert cur is None
    assert exc_id is None


def test_bump_budget_creates_marker(tmp_path):
    m = _load()
    yaml = tmp_path / "dg.yaml"
    yaml.write_text("""warning_exceptions:
  entries:
    - id: test-budget
      rule: invalid_metadata
      surface: omo-knowledge
      max_findings: 70
      expires: 2026-10-31
      reason: existing
""")
    new = m.bump_budget(
        yaml,
        line_no=4,
        rule="invalid_metadata",
        surface="omo-knowledge",
        current=70,
        amount=20,
        exception_id="test-budget",
    )
    assert new == 90
    content = yaml.read_text()
    assert "max_findings: 90" in content
    assert "# auto-bumped to 90 on" in content


def test_bump_budget_preserves_other_budgets(tmp_path):
    m = _load()
    yaml = tmp_path / "dg.yaml"
    yaml.write_text("""warning_exceptions:
  entries:
    - id: budget-a
      rule: invalid_metadata
      surface: omo-knowledge
      max_findings: 70
      expires: 2026-10-31
      reason: a
    - id: budget-b
      rule: missing_frontmatter
      surface: docs-discoverable
      max_findings: 175
      expires: 2026-10-31
      reason: b
""")
    m.bump_budget(
        yaml,
        line_no=4,
        rule="invalid_metadata",
        surface="omo-knowledge",
        current=70,
        amount=20,
        exception_id="budget-a",
    )
    content = yaml.read_text()
    assert "max_findings: 90" in content
    assert "max_findings: 175" in content
    assert "budget-b" in content
    assert "budget-a" in content


def test_circuit_breaker_at_50():
    m = _load()
    assert m.ABSOLUTE_MAX_BUMP == 50


if __name__ == "__main__":
    import inspect
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            sig = inspect.signature(fn)
            if "tmp_path" in sig.parameters:
                from tempfile import mkdtemp
                import pathlib
                fn(pathlib.Path(mkdtemp()))
            else:
                fn()
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append((name, e))
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")