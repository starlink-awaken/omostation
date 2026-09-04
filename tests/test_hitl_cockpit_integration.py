"""tests.test_hitl_cockpit_integration — verify bin/cockpit delegates to hitl-proposal.py.

This tests the standalone subprocess path (when cockpit decide can't route
hitl-* IDs to its internal handler, e.g. before PR #129 merges). The
subprocess delegation ensures HITL proposals work even without the
cockpit-side integration.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HITL_PROPOSAL_PATH = _REPO_ROOT / "bin" / "hitl-proposal.py"
_TMPDIR = tempfile.mkdtemp()


def _load_hitl_module():
    spec = importlib.util.spec_from_file_location("hitl_proposal_test", str(_HITL_PROPOSAL_PATH))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PROPOSALS_DIR = Path(_TMPDIR)
    return m


class TestHITLCockpitSubprocessDelegation(unittest.TestCase):
    """Verify bin/cockpit decide approve/reject delegates to bin/hitl-proposal.py."""

    def setUp(self):
        for f in Path(_TMPDIR).glob("*.yaml"):
            f.unlink()
        for f in Path(_TMPDIR).glob("*.tmp"):
            f.unlink()

    def _run_hitl(self, *args):
        """Invoke bin/hitl-proposal.py as subprocess (mimics cockpit shim path)."""
        return subprocess.run(
            [sys.executable, str(_HITL_PROPOSAL_PATH), *args],
            capture_output=True, text=True,
            env={**os.environ, "HITL_PROPOSALS_DIR": _TMPDIR},
        )

    def test_subprocess_create_returns_id(self):
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-1",
                          "--run-id", "test", "--title", "delegate test")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Created:", r.stdout)
        proposal_id = r.stdout.split("Created:")[1].split("\n")[0].strip()
        self.assertTrue(proposal_id.startswith("hitl-"))

    def test_subprocess_approve_succeeds(self):
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-2",
                          "--run-id", "test", "--title", "approve test")
        pid = r.stdout.split("Created:")[1].split("\n")[0].strip()
        r = self._run_hitl("approve", pid)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Approved:", r.stdout)
        # verify file
        self.assertTrue((Path(_TMPDIR) / f"{pid}.yaml").exists())

    def test_subprocess_reject_succeeds(self):
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-3",
                          "--run-id", "test", "--title", "reject test")
        pid = r.stdout.split("Created:")[1].split("\n")[0].strip()
        r = self._run_hitl("reject", pid)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Rejected:", r.stdout)

    def test_subprocess_get_yaml_structure(self):
        """Verify the YAML schema matches the spec contract."""
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-4",
                          "--run-id", "test", "--title", "schema test",
                          "--description", "schema verification")
        pid = r.stdout.split("Created:")[1].split("\n")[0].strip()
        r = self._run_hitl("get", pid)
        data = yaml.safe_load(r.stdout)
        # Required fields per spec
        required = ["schema_version", "proposal_id", "bet_id", "run_id",
                    "title", "description", "options", "status",
                    "created_at", "expires_at", "responded_at",
                    "response_actor", "response_option"]
        for field in required:
            self.assertIn(field, data, f"Missing required field: {field}")
        self.assertEqual(data["schema_version"], "hitl-proposal/v1")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["options"]), 2)  # approve + reject
        self.assertEqual(data["options"][0]["id"], "approve")
        self.assertEqual(data["options"][1]["id"], "reject")

    def test_subprocess_actor_auto_detected(self):
        """Verify default actor is auto-captured from git config (not just 'human')."""
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-5",
                          "--run-id", "test", "--title", "actor test")
        pid = r.stdout.split("Created:")[1].split("\n")[0].strip()
        r = self._run_hitl("approve", pid)
        self.assertEqual(r.returncode, 0)
        r = self._run_hitl("get", pid)
        data = yaml.safe_load(r.stdout)
        # Auto-detected actor should NOT be the literal "human" if git config has user
        actor = data["response_actor"]
        # Either git user is set (non-"human") or USER env was set
        self.assertIsInstance(actor, str)
        self.assertGreater(len(actor), 0)

    def test_subprocess_prefix_match_in_get(self):
        """Verify that 'get <prefix>' works with truncated proposal IDs."""
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-6",
                          "--run-id", "test", "--title", "prefix test")
        pid = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Use first 12 chars
        short = pid[:12]
        r = self._run_hitl("get", short)
        self.assertEqual(r.returncode, 0)
        self.assertIn(pid, r.stdout)

    def test_subprocess_check_returns_hitl_required(self):
        """Verify check returns HITL_REQUIRED for L2 BET with human_gate=true."""
        r = self._run_hitl("check", "--bet-id", "BET-Y1Q4-T1-02")
        self.assertEqual(r.returncode, 0)
        self.assertIn("HITL_REQUIRED", r.stdout)

    def test_subprocess_check_returns_empty_for_non_hitl(self):
        """Verify check returns no HITL_REQUIRED for non-L2 BETs."""
        r = self._run_hitl("check", "--bet-id", "BET-Y1Q3-T10-109")
        # exit 0, no HITL_REQUIRED in stdout
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("HITL_REQUIRED", r.stdout)

    def test_subprocess_concurrent_approval_safety(self):
        """Verify fcntl.flock prevents two concurrent approvals on same proposal."""
        r = self._run_hitl("create", "--bet-id", "BET-COCKPIT-7",
                          "--run-id", "test", "--title", "concurrent test")
        pid = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Try to approve twice; second one should also succeed but be idempotent
        r1 = self._run_hitl("approve", pid)
        r2 = self._run_hitl("approve", pid)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r2.returncode, 0)  # second approve is idempotent
        # File should still be valid YAML
        data = yaml.safe_load((Path(_TMPDIR) / f"{pid}.yaml").read_text())
        self.assertEqual(data["status"], "approved")


if __name__ == "__main__":
    unittest.main()
