#!/usr/bin/env python3
"""Unit tests for drift-face-detector.py + auto-pruner.py (BET-Y2Q4-SH-1).

Tests cover:
  - detector: 5 classes triggered correctly with fixtures
  - pruner: dry-run vs apply behavior for ephemeral (move) + runs (status flip)
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


class DriftDetectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # create workspace-like layout
        (self.tmp / "docs/reports").mkdir(parents=True)
        (self.tmp / ".omo/_control/debt-dashboard").mkdir(parents=True)
        (self.tmp / "runtime/dashboard").mkdir(parents=True)
        (self.tmp / ".omo/state/heartbeats").mkdir(parents=True)
        (self.tmp / ".omo/_delivery/agent-workflows/runs").mkdir(parents=True)
        (self.tmp / ".omo/_delivery/agent-workflows/locks").mkdir(parents=True)

    def test_dashboard_stale(self):
        (self.tmp / ".omo/_control/debt-dashboard/current.yaml").write_text(
            "generated_at: '2026-01-01T00:00:00Z'\nfoo: bar\n"
        )
        det = _load("drift_face_detector", ROOT / "bin/ssot/drift-face-detector.py")
        det.WORKSPACE_ROOT = self.tmp
        findings = det.detect_dashboard()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["id"], "DASHBOARD-STALE")
        self.assertGreater(findings[0]["age_hours"], 0)

    def test_dashboard_missing(self):
        det = _load("drift_face_detector", ROOT / "bin/ssot/drift-face-detector.py")
        det.WORKSPACE_ROOT = self.tmp
        findings = det.detect_dashboard()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["id"], "DASHBOARD-MISSING")

    def test_ephemeral_detect(self):
        (self.tmp / "docs/reports/old-report.md").write_text(
            "---\ntype: ephemeral\nstatus: completed\n---\n# old\n"
        )
        (self.tmp / "docs/reports/active-report.md").write_text(
            "---\ntype: report\nstatus: active\n---\n# active\n"
        )
        (self.tmp / "docs/reports/done-no-type.md").write_text(
            "---\nstatus: completed\n---\n# done\n"
        )
        det = _load("drift_face_detector", ROOT / "bin/ssot/drift-face-detector.py")
        det.WORKSPACE_ROOT = self.tmp
        findings = det.detect_ephemeral()
        ids = [f["id"] for f in findings]
        self.assertIn("EPHEMERAL-old-report", ids)
        self.assertNotIn("EPHEMERAL-active-report", ids)
        self.assertNotIn("EPHEMERAL-done-no-type", ids)

    def test_runs_stale(self):
        run_file = self.tmp / ".omo/_delivery/agent-workflows/runs/old-run.yaml"
        run_file.write_text(
            "id: old-run\nstatus: active\ncreated_at: '2026-01-01T00:00:00Z'\nupdated_at: '2026-01-01T00:00:00Z'\n"
        )
        # fresh active run (not stale)
        (self.tmp / ".omo/_delivery/agent-workflows/runs/fresh-run.yaml").write_text(
            f"id: fresh-run\nstatus: active\ncreated_at: '{__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}'\n"
        )
        det = _load("drift_face_detector", ROOT / "bin/ssot/drift-face-detector.py")
        det.WORKSPACE_ROOT = self.tmp
        findings = det.detect_runs()
        ids = [f["id"] for f in findings]
        self.assertIn("RUN-STALE-old-run", ids)
        self.assertNotIn("RUN-STALE-fresh-run", ids)

    def test_ritual_lapsed(self):
        from datetime import datetime, timezone
        # recent weekly
        hb = self.tmp / ".omo/state/heartbeats/weekly-review.json"
        hb.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": True,
        }))
        det = _load("drift_face_detector", ROOT / "bin/ssot/drift-face-detector.py")
        det.WORKSPACE_ROOT = self.tmp
        findings = det.detect_ritual()
        self.assertEqual(findings, [])


class AutoPrunerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "docs/reports").mkdir(parents=True)
        (self.tmp / ".omo/_delivery/agent-workflows/runs").mkdir(parents=True)
        (self.tmp / ".omo/_delivery/agent-workflows/locks").mkdir(parents=True)

    def test_ephemeral_dry_run(self):
        src = self.tmp / "docs/reports/old.md"
        src.write_text("---\ntype: ephemeral\nstatus: completed\n---\n# old\n")
        pr = _load("auto_pruner", ROOT / "bin/ssot/auto-pruner.py")
        pr.WORKSPACE_ROOT = self.tmp
        actions = pr.prune_ephemeral(dry_run=True)
        self.assertEqual(len(actions), 1)
        self.assertFalse(actions[0]["applied"])
        self.assertTrue(src.exists(), "dry-run should not move")

    def test_ephemeral_apply(self):
        src = self.tmp / "docs/reports/old.md"
        src.write_text("---\ntype: ephemeral\nstatus: completed\n---\n# old\n")
        pr = _load("auto_pruner", ROOT / "bin/ssot/auto-pruner.py")
        pr.WORKSPACE_ROOT = self.tmp
        actions = pr.prune_ephemeral(dry_run=False)
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0]["applied"])
        self.assertFalse(src.exists(), "apply should move")
        self.assertTrue((self.tmp / "docs/reports/archive/old.md").exists())

    def test_runs_close(self):
        run = self.tmp / ".omo/_delivery/agent-workflows/runs/old.yaml"
        run.write_text(
            "id: old\nstatus: active\ncreated_at: '2026-01-01T00:00:00Z'\nupdated_at: '2026-01-01T00:00:00Z'\n"
        )
        pr = _load("auto_pruner", ROOT / "bin/ssot/auto-pruner.py")
        pr.WORKSPACE_ROOT = self.tmp
        actions = pr.prune_runs(dry_run=False)
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0]["applied"])
        new_text = run.read_text()
        self.assertIn("status: closed", new_text)

    def test_active_report_not_archived(self):
        src = self.tmp / "docs/reports/active.md"
        src.write_text("---\ntype: ephemeral\nstatus: active\n---\n# active\n")
        pr = _load("auto_pruner", ROOT / "bin/ssot/auto-pruner.py")
        pr.WORKSPACE_ROOT = self.tmp
        actions = pr.prune_ephemeral(dry_run=False)
        self.assertEqual(len(actions), 0)
        self.assertTrue(src.exists())


if __name__ == "__main__":
    unittest.main()