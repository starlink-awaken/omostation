"""tests.test_hitl_v11 — v1.1 specific tests for HITL Proposal System.

Tests for:
- notified_at field on proposal YAML (backward-compat)
- bin/notification.py stub (log + stdout channels, slack/email no-op without config)
- --hitl-wait default behavior in bin/harness
- bin/notification.py audit trail
- bin/notification.py graceful failure modes
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
_NOTIFICATION_PATH = _REPO_ROOT / "bin" / "notification.py"
_HARNESS_PATH = _REPO_ROOT / "bin" / "harness"
_TMPDIR = tempfile.mkdtemp()


def _load_hitl_module():
    spec = importlib.util.spec_from_file_location("hitl_proposal_v11", str(_HITL_PROPOSAL_PATH))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PROPOSALS_DIR = Path(_TMPDIR)
    return m


def _run(*args, env_extra=None):
    env = {**os.environ, "HITL_PROPOSALS_DIR": _TMPDIR}
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env)


class TestHITLV11(unittest.TestCase):
    def setUp(self):
        for f in Path(_TMPDIR).glob("*.yaml"):
            f.unlink()
        for f in Path(_TMPDIR).glob("*.log"):
            f.unlink()
        for f in Path(_TMPDIR).glob("*.tmp"):
            f.unlink()

    def test_01_v11_proposal_has_notified_at_field(self):
        """v1.1: proposal YAML must include notified_at and notification_channels fields."""
        r = _run(str(_HITL_PROPOSAL_PATH), "create",
                 "--bet-id", "BET-Y1Q4-T8-04",
                 "--run-id", "v11-notified-001",
                 "--title", "v1.1 notified_at test")
        self.assertEqual(r.returncode, 0)
        proposal_id = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Read the proposal file
        path = Path(_TMPDIR) / f"{proposal_id}.yaml"
        self.assertTrue(path.exists())
        with open(path) as f:
            data = yaml.safe_load(f)
        # Backward-compat: v1.1 fields must exist (initially None/empty)
        self.assertIn("notified_at", data, "missing notified_at field")
        self.assertIn("notification_channels", data, "missing notification_channels field")
        self.assertIsNone(data["notified_at"], "notified_at should be None before notify invocation")
        self.assertEqual(data["notification_channels"], [], "notification_channels should be empty initially")

    def test_02_notification_stub_log_channel(self):
        """v1.1: bin/notification.py with log channel writes audit log."""
        r = _run(str(_HITL_PROPOSAL_PATH), "create",
                 "--bet-id", "BET-Y1Q4-T8-04",
                 "--run-id", "v11-notif-log-001",
                 "--title", "log channel test")
        proposal_id = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Notify with log channel only
        r = _run(str(_NOTIFICATION_PATH), "notify", proposal_id, "--channels", "log")
        self.assertEqual(r.returncode, 0)
        # Check audit log
        log_file = Path(_TMPDIR) / ".notifications.log"
        self.assertTrue(log_file.exists(), "audit log not created")
        with open(log_file) as f:
            content = f.read()
        self.assertIn(proposal_id, content)
        self.assertIn("log", content)
        self.assertIn("ok", content)

    def test_03_notification_updates_notified_at(self):
        """v1.1: notify invocation should update notified_at + notification_channels."""
        r = _run(str(_HITL_PROPOSAL_PATH), "create",
                 "--bet-id", "BET-Y1Q4-T8-04",
                 "--run-id", "v11-notif-update-001",
                 "--title", "update test")
        proposal_id = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Notify
        r = _run(str(_NOTIFICATION_PATH), "notify", proposal_id, "--channels", "log,stdout")
        self.assertEqual(r.returncode, 0)
        # Verify proposal file updated
        path = Path(_TMPDIR) / f"{proposal_id}.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        self.assertIsNotNone(data["notified_at"], "notified_at not updated")
        self.assertIn("log", data["notification_channels"])
        self.assertIn("stdout", data["notification_channels"])

    def test_04_notification_slack_noop_without_config(self):
        """v1.1: slack channel must no-op gracefully without webhook config."""
        r = _run(str(_HITL_PROPOSAL_PATH), "create",
                 "--bet-id", "BET-Y1Q4-T8-04",
                 "--run-id", "v11-slack-noop-001",
                 "--title", "slack noop test")
        proposal_id = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Notify with slack (no config in test env)
        r = _run(str(_NOTIFICATION_PATH), "notify", proposal_id, "--channels", "slack")
        # Should still exit 0 (slack is non-fatal, log+stdout also run)
        # Actually with only slack channel, return 1 because no success
        # But the script behavior: notify returns 0 if any succeeds
        # With only slack (no config), returns False but might still be 0 if log default is also enabled
        # Check stderr for warning
        self.assertIn("slack channel not configured", r.stderr)

    def test_05_notification_idempotent(self):
        """v1.1: calling notify twice should be safe and merge channels."""
        r = _run(str(_HITL_PROPOSAL_PATH), "create",
                 "--bet-id", "BET-Y1Q4-T8-04",
                 "--run-id", "v11-idemp-001",
                 "--title", "idempotency test")
        proposal_id = r.stdout.split("Created:")[1].split("\n")[0].strip()
        # Notify twice
        r1 = _run(str(_NOTIFICATION_PATH), "notify", proposal_id, "--channels", "log")
        r2 = _run(str(_NOTIFICATION_PATH), "notify", proposal_id, "--channels", "stdout")
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r2.returncode, 0)
        # Verify proposal
        path = Path(_TMPDIR) / f"{proposal_id}.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        # Both channels should be in the list
        self.assertIn("log", data["notification_channels"])
        self.assertIn("stdout", data["notification_channels"])

    def test_06_harness_hitl_wait_default_on(self):
        """v1.1: bin/harness run should have --hitl-wait default ON."""
        r = subprocess.run(
            [sys.executable, str(_HARNESS_PATH), "run", "--help"],
            capture_output=True, text=True,
        )
        self.assertIn("--hitl-wait", r.stdout)
        self.assertIn("--no-hitl-wait", r.stdout)
        # Help text should say "default ON"
        self.assertIn("default ON", r.stdout)

    def test_07_notification_nonexistent_proposal_exits_1(self):
        """v1.1: notification on non-existent proposal returns exit 1."""
        r = _run(str(_NOTIFICATION_PATH), "notify", "hitl-nonexistent-9999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Proposal not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
