#!/usr/bin/env python3
"""Unit tests for registry alias map + check-rule-wiring-coverage upgrade (BET-Y2Q4-SH-4)."""

from __future__ import annotations

import importlib.util
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


class AliasMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # create fake git repo (some helpers need it)
        (self.tmp / ".git").mkdir()
        import subprocess
        subprocess.run(["git", "-C", str(self.tmp), "init", "-q"], check=False, capture_output=True)

    def test_load_alias_map(self):
        """Test alias map YAML loading."""
        m = _load("check_rule_wiring", ROOT / "bin/gac/check-rule-wiring-coverage.py")
        m._ROOT = self.tmp
        # copy alias map into tmp
        import shutil as _sh
        _sh.copy(ROOT / "bin/gac/registry-alias-map.yaml", self.tmp / "alias.yaml")
        # monkey-patch the path
        m.ALIAS_MAP = self.tmp / "alias.yaml"
        am = m._load_alias_map()
        self.assertGreater(len(am), 0)
        self.assertIn("CR-M0-STAGE-GATE", am)
        self.assertIn("mof_stage_gate", am["CR-M0-STAGE-GATE"])

    def test_resolve_via_alias(self):
        m = _load("check_rule_wiring", ROOT / "bin/gac/check-rule-wiring-coverage.py")
        am = {"CR-X-FOO": {"CR-X-FOO", "x_foo", "X-Foo"}}
        self.assertEqual(m._resolve_via_alias("CR-X-FOO", am), "CR-X-FOO")
        self.assertEqual(m._resolve_via_alias("x_foo", am), "CR-X-FOO")
        self.assertEqual(m._resolve_via_alias("X-Foo", am), "CR-X-FOO")
        self.assertIsNone(m._resolve_via_alias("CR-X-BAR", am))

    def test_alias_map_size_minimum(self):
        """Spec requires ≥20 alias entries."""
        m = _load("check_rule_wiring", ROOT / "bin/gac/check-rule-wiring-coverage.py")
        am = m._load_alias_map()
        # We have 33 documented + 2 cross_walk pairs (counted separately).
        # Spec requires ≥20 alias entries — let's check the aliases list specifically.
        self.assertGreaterEqual(len(am), 20,
            msg=f"alias map has only {len(am)} entries, spec requires ≥20")


class InventoryTests(unittest.TestCase):
    def test_inventory_runs(self):
        """Test that inventory() runs without errors on the real workspace."""
        m = _load("check_rule_wiring", ROOT / "bin/gac/check-rule-wiring-coverage.py")
        inv = m.inventory()
        self.assertIn("sources", inv)
        self.assertIn("governance-checks", inv["sources"])
        self.assertIn("candidates_unwired", inv)
        self.assertIn("implemented_via_alias", inv)
        # alias map must be loaded
        self.assertTrue(inv["sources"]["governance-checks"]["alias_map_loaded"])


if __name__ == "__main__":
    unittest.main()