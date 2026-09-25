#!/usr/bin/env python3
"""Unit tests for frontmatter-coverage.py (BET-Y2Q4-SH-2).

Tests cover:
  - detector: 7 paths × 6 fields matrix output
  - patcher: idempotent (already-full fm no-op), safe defaults
  - skip paths: archive / node_modules / _delivery
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FrontmatterCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # create path groups
        for p in ("docs", ".agents", ".omo/_knowledge/retros", ".omo/_knowledge/reports",
                  ".omo/_knowledge/decisions", ".omo/standards"):
            (self.tmp / p).mkdir(parents=True, exist_ok=True)
        (self.tmp / "projects").mkdir()

    def test_parse_fm_valid(self):
        text = "---\nfoo: bar\nbaz: 1\n---\n# body\n"
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        fm, s, e = m._parse_fm(text)
        self.assertIsNotNone(fm)
        self.assertEqual(fm.get("foo"), "bar")
        self.assertEqual(fm.get("baz"), "1")

    def test_parse_fm_missing(self):
        text = "# no fm\n"
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        fm, s, e = m._parse_fm(text)
        self.assertIsNone(fm)

    def test_walk_skip_archive(self):
        # /archive/ should be skipped
        (self.tmp / "docs/archive").mkdir(parents=True)
        (self.tmp / "docs/archive/old.md").write_text("---\nfoo: bar\n---\n")
        (self.tmp / "docs/active.md").write_text("---\nfoo: bar\n---\n")
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        m.WORKSPACE_ROOT = self.tmp
        files = list(m._walk_dirs(["docs"]))
        paths = [str(f) for f in files]
        self.assertTrue(any("active.md" in p for p in paths))
        self.assertFalse(any("/archive/" in p for p in paths))

    def test_walk_skip_delivery(self):
        (self.tmp / "docs/.omo/_delivery").mkdir(parents=True)
        (self.tmp / "docs/.omo/_delivery/x.md").write_text("---\nfoo: bar\n---\n")
        (self.tmp / "docs/x.md").write_text("---\nfoo: bar\n---\n")
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        m.WORKSPACE_ROOT = self.tmp
        files = list(m._walk_dirs(["docs"]))
        paths = [str(f) for f in files]
        self.assertFalse(any("_delivery" in p for p in paths))

    def test_apply_patch_no_fm(self):
        text = "# body\n"
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        m.WORKSPACE_ROOT = self.tmp
        new_text, added = m._apply_patch_one(self.tmp / "x.md", None, 0, 0, text)
        self.assertIn("---", new_text)
        for f in ["schema", "status", "lifecycle", "owner", "last-reviewed", "type"]:
            self.assertIn(f, new_text)

    def test_apply_patch_partial_fm(self):
        text = "---\nfoo: bar\n---\n# body\n"
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        m.WORKSPACE_ROOT = self.tmp
        fm, s, e = m._parse_fm(text)
        new_text, added = m._apply_patch_one(self.tmp / "x.md", fm, s, e, text)
        self.assertIn("foo: bar", new_text)
        for f in ["schema", "status", "lifecycle", "owner", "last-reviewed", "type"]:
            self.assertIn(f, new_text)
        self.assertIn("# body", new_text)

    def test_apply_patch_already_full(self):
        text = (
            "---\nschema: x\nstatus: a\nlifecycle: h\nowner: o\n"
            "last-reviewed: 2026-01-01\ntype: t\nfoo: bar\n---\n# body\n"
        )
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        m.WORKSPACE_ROOT = self.tmp
        fm, s, e = m._parse_fm(text)
        new_text, added = m._apply_patch_one(self.tmp / "x.md", fm, s, e, text)
        # all 6 fields already there; added should be empty
        self.assertEqual(added, [])
        # foo still preserved
        self.assertIn("foo: bar", new_text)
        # last-reviewed bumped to today (2026-09-25)
        self.assertIn("last-reviewed: 2026-09-25", new_text)

    def test_coverage_one_basic(self):
        # write 3 files with various FM states
        (self.tmp / "docs/a.md").write_text("---\nfoo: bar\n---\n# a\n")
        (self.tmp / "docs/b.md").write_text("# b\n")  # no fm
        (self.tmp / "docs/c.md").write_text(
            "---\nschema: x\nstatus: a\nlifecycle: h\nowner: o\n"
            "last-reviewed: 2026-01-01\ntype: t\n---\n# c\n"
        )
        m = _load("frontmatter_coverage", ROOT / "bin/ssot/frontmatter-coverage.py")
        m.WORKSPACE_ROOT = self.tmp
        result = m._coverage_one("docs", m._walk_dirs(["docs"]))
        # 3 files total; 2 with fm; c has all fields → 2/2 for each field
        self.assertEqual(result["total_files"], 3)
        self.assertEqual(result["files_with_no_fm"], 1)
        self.assertEqual(result["matrix"]["schema"]["total"], 2)
        self.assertEqual(result["matrix"]["schema"]["present"], 1)


if __name__ == "__main__":
    unittest.main()