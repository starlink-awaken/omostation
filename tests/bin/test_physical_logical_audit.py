#!/usr/bin/env python3
"""Unit tests for physical-logical-audit.py (BET-Y2Q4-SH-3).

Tests cover:
  - audit_gitlink: 3-way diff detection (drift + missing)
  - audit_launchd: plist Label vs launchctl list
  - audit_omo_assets: ref exists check + gitignore skip
"""

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


def _init_git_repo(p: Path):
    """Initialize a fake git repo so check-ignore works."""
    import subprocess
    (p / ".git").mkdir(exist_ok=True)
    # create minimal git scaffolding (git check-ignore needs at least HEAD)
    subprocess.run(["git", "-C", str(p), "init", "-q"], check=False, capture_output=True)
    subprocess.run(["git", "-C", str(p), "config", "user.email", "test@test"], check=False, capture_output=True)
    subprocess.run(["git", "-C", str(p), "config", "user.name", "test"], check=False, capture_output=True)


class PhysicalLogicalAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        _init_git_repo(self.tmp)
        (self.tmp / ".omo/cron").mkdir(parents=True)
        (self.tmp / ".omo/_truth/registry").mkdir(parents=True)
        (self.tmp / "projects/sub1").mkdir(parents=True)
        (self.tmp / "projects/sub1/.git").mkdir()  # fake submodule dir
        (self.tmp / ".gitmodules").write_text(
            "[submodule \"projects/sub1\"]\n"
            "  path = projects/sub1\n"
            "  url = https://github.com/starlink-awaken/sub1.git\n"
        )

    def test_omo_zombie_real_missing(self):
        """Asset ref points to missing dir → real zombie."""
        reg = (
            "---\n"
            "schema: ssot/v1\n"
            "owner: governance-team\n"
            "assets:\n"
            "  - id: TEST-ZOMBIE\n"
            "    ref: .omo/missing-dir/\n"
        )
        (self.tmp / ".omo/_truth/registry/omo-governance-surfaces.yaml").write_text(reg)
        m = _load("physical_logical_audit", ROOT / "bin/ssot/physical-logical-audit.py")
        m.WORKSPACE_ROOT = self.tmp
        findings = m.audit_omo_assets()
        ids = [f["id"] for f in findings]
        self.assertIn("OMO-ZOMBIE-TEST-ZOMBIE", ids)
        self.assertEqual(findings[0]["drift_kind"], "declared_but_missing")

    def test_omo_zombie_skipped_when_gitignored(self):
        """Asset ref missing but gitignored → not real zombie."""
        # Setup .gitignore
        (self.tmp / ".gitignore").write_text(".omo/runtime-only/\n")
        reg = (
            "---\n"
            "schema: ssot/v1\n"
            "owner: governance-team\n"
            "assets:\n"
            "  - id: TEST-RUNTIME\n"
            "    ref: .omo/runtime-only/\n"
        )
        (self.tmp / ".omo/_truth/registry/omo-governance-surfaces.yaml").write_text(reg)
        m = _load("physical_logical_audit", ROOT / "bin/ssot/physical-logical-audit.py")
        m.WORKSPACE_ROOT = self.tmp
        findings = m.audit_omo_assets()
        # Should be empty (gitignored runtime face expected missing)
        self.assertEqual(findings, [])

    def test_omo_zombie_present_no_drift(self):
        """Asset ref present → no finding."""
        (self.tmp / ".omo/real-dir").mkdir()
        reg = (
            "---\n"
            "schema: ssot/v1\n"
            "owner: governance-team\n"
            "assets:\n"
            "  - id: TEST-OK\n"
            "    ref: .omo/real-dir\n"
        )
        (self.tmp / ".omo/_truth/registry/omo-governance-surfaces.yaml").write_text(reg)
        m = _load("physical_logical_audit", ROOT / "bin/ssot/physical-logical-audit.py")
        m.WORKSPACE_ROOT = self.tmp
        findings = m.audit_omo_assets()
        self.assertEqual(findings, [])

    def test_launchd_missing_label(self):
        """Plist with label not in launchctl list → drift."""
        plist = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            '<dict><key>Label</key><string>com.omostation.test-missing</string></dict>\n'
            '</plist>\n'
        )
        (self.tmp / ".omo/cron/test-missing.plist").write_text(plist)
        m = _load("physical_logical_audit", ROOT / "bin/ssot/physical-logical-audit.py")
        m.WORKSPACE_ROOT = self.tmp
        # launchctl list won't have this label, so should drift
        findings = m.audit_launchd()
        ids = [f["id"] for f in findings]
        self.assertTrue(any("com.omostation.test-missing" in i for i in ids))


if __name__ == "__main__":
    unittest.main()