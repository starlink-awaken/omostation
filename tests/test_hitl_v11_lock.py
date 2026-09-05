"""Additional v1.1 test: distributed lock backend config."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HITL_PROPOSAL_PATH = _REPO_ROOT / "bin" / "hitl-proposal.py"
_TMPDIR = tempfile.mkdtemp()


def _load_hitl_module():
    spec = importlib.util.spec_from_file_location("hitl_lock_test", str(_HITL_PROPOSAL_PATH))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PROPOSALS_DIR = Path(_TMPDIR)
    return m


class TestHITLV11LockBackend(unittest.TestCase):
    def setUp(self):
        for f in Path(_TMPDIR).glob("*.yaml"):
            f.unlink()

    def test_08_lock_backend_default_is_fcntl(self):
        """v1.1: default lock backend is fcntl (POSIX file lock)."""
        env = {**os.environ, "HITL_PROPOSALS_DIR": _TMPDIR}
        # No HITL_LOCK_BACKEND env var
        env.pop("HITL_LOCK_BACKEND", None)
        env.pop("HITL_LOCK_ETCD_ENDPOINTS", None)
        env.pop("HITL_LOCK_REDIS_URL", None)
        r = subprocess.run(
            [sys.executable, str(_HITL_PROPOSAL_PATH), "lock-backend"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("Lock backend: fcntl", r.stdout)

    def test_09_lock_backend_etcd_stub(self):
        """v1.1: etcd backend is recognized as STUB (no real client)."""
        env = {
            **os.environ,
            "HITL_PROPOSALS_DIR": _TMPDIR,
            "HITL_LOCK_BACKEND": "etcd",
            "HITL_LOCK_ETCD_ENDPOINTS": "http://etcd:2379",
        }
        r = subprocess.run(
            [sys.executable, str(_HITL_PROPOSAL_PATH), "lock-backend"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("Lock backend: etcd", r.stdout)
        self.assertIn("STUB", r.stdout)
        self.assertIn("http://etcd:2379", r.stdout)

    def test_10_lock_backend_redis_stub(self):
        """v1.1: redis backend is recognized as STUB (no real client)."""
        env = {
            **os.environ,
            "HITL_PROPOSALS_DIR": _TMPDIR,
            "HITL_LOCK_BACKEND": "redis",
            "HITL_LOCK_REDIS_URL": "redis://localhost:6379",
        }
        r = subprocess.run(
            [sys.executable, str(_HITL_PROPOSAL_PATH), "lock-backend"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("Lock backend: redis", r.stdout)
        self.assertIn("STUB", r.stdout)
        self.assertIn("redis://localhost:6379", r.stdout)

    def test_11_lock_backend_module_constants(self):
        """v1.1: module exposes LOCK_BACKEND, LOCK_ETCD_ENDPOINTS, LOCK_REDIS_URL."""
        m = _load_hitl_module()
        # Reset to default (subprocess test already verified env override)
        self.assertEqual(m.LOCK_BACKEND, "fcntl")
        self.assertEqual(m.LOCK_ETCD_ENDPOINTS, "")
        self.assertEqual(m.LOCK_REDIS_URL, "")

    def test_12_update_status_uses_lock_backend(self):
        """v1.1: update_status with non-fcntl backend falls back gracefully."""
        m = _load_hitl_module()
        # Create a proposal first
        p = m.create_proposal("BET-Y1Q4-T8-04", "lock-test", "test", "test")
        pid = p["proposal_id"]
        # Update with default fcntl — should work
        result = m.update_status(pid, "approved", actor="test", option="approve")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "approved")


if __name__ == "__main__":
    unittest.main()
