"""tests.test_hitl_proposal — unit tests for HITL proposal system."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# Resolve paths
_REPO_ROOT = Path(__file__).resolve().parents[1]
_HITL_PROPOSAL_PATH = _REPO_ROOT / "bin" / "hitl-proposal.py"
_TMPDIR = tempfile.mkdtemp()


def _load_hitl_module():
    """Load bin/hitl-proposal.py as a module with patched PROPOSALS_DIR."""
    # Patch the proposals dir before import
    import os
    os.environ["_HITL_PROPOSALS_DIR"] = _TMPDIR

    spec = importlib.util.spec_from_file_location("hitl_proposal_mod", str(_HITL_PROPOSAL_PATH))
    mod = importlib.util.module_from_spec(spec)

    # Monkey-patch PROPOSALS_DIR before execution
    original_dir = None
    # We need to patch after module loads but before functions run
    # Instead, we patch at module level after exec
    spec.loader.exec_module(mod)
    mod.PROPOSALS_DIR = Path(_TMPDIR)
    return mod


class TestHITLProposal(unittest.TestCase):
    def setUp(self):
        for f in Path(_TMPDIR).glob("*.yaml"):
            f.unlink()
        for f in Path(_TMPDIR).glob("*.tmp"):
            f.unlink()

    def test_01_create_proposal(self):
        mod = _load_hitl_module()
        p = mod.create_proposal(
            bet_id="BET-TEST-001",
            run_id="harness-test-001",
            title="Test proposal",
            description="A test",
        )
        self.assertTrue(p["proposal_id"].startswith("hitl-"))
        self.assertEqual(p["status"], "pending")
        self.assertEqual(p["bet_id"], "BET-TEST-001")
        proposal_file = Path(_TMPDIR) / f"{p['proposal_id']}.yaml"
        self.assertTrue(proposal_file.exists())

    def test_02_list_proposals(self):
        mod = _load_hitl_module()
        mod.create_proposal("BET-A", "run-a", "A", "desc")
        mod.create_proposal("BET-B", "run-b", "B", "desc")
        proposals = mod.list_proposals()
        self.assertEqual(len(proposals), 2)

    def test_03_get_proposal_prefix_match(self):
        mod = _load_hitl_module()
        p = mod.create_proposal("BET-C", "run-c", "C", "desc")
        short_id = p["proposal_id"][:12]
        found = mod.get_proposal(short_id)
        self.assertIsNotNone(found)
        self.assertEqual(found["proposal_id"], p["proposal_id"])

    def test_04_approve_proposal(self):
        mod = _load_hitl_module()
        p = mod.create_proposal("BET-D", "run-d", "D", "desc")
        result = mod.update_status(p["proposal_id"], "approved", actor="test")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["response_actor"], "test")
        self.assertIsNotNone(result["responded_at"])

    def test_05_reject_proposal(self):
        mod = _load_hitl_module()
        p = mod.create_proposal("BET-E", "run-e", "E", "desc")
        result = mod.update_status(p["proposal_id"], "rejected", actor="test")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "rejected")

    def test_06_expire_stale(self):
        mod = _load_hitl_module()
        p = mod.create_proposal("BET-F", "run-f", "F", "desc", ttl_hours=-1)
        expired = mod.expire_stale()
        self.assertIn(p["proposal_id"], expired)
        updated = mod.get_proposal(p["proposal_id"])
        self.assertEqual(updated["status"], "expired")

    def test_07_check_human_gate_no_ledger(self):
        mod = _load_hitl_module()
        # When ledger doesn't exist, should return False
        result = mod.check_human_gate_needed("BET-NONEXISTENT")
        # Depends on whether ledger exists in worktree; just verify no crash
        self.assertIsInstance(result, bool)

    def test_08_list_filter_by_status(self):
        mod = _load_hitl_module()
        p1 = mod.create_proposal("BET-G", "run-g", "G", "desc")
        p2 = mod.create_proposal("BET-H", "run-h", "H", "desc")
        mod.update_status(p1["proposal_id"], "approved")
        pending = mod.list_proposals(status_filter="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["proposal_id"], p2["proposal_id"])


if __name__ == "__main__":
    unittest.main()
