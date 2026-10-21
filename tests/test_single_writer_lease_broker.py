from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.single_writer_lease_broker import (
    BrokerSecurityError,
    ControlCapsuleSigner,
    SingleWriterLeaseBroker,
)


class SingleWriterLeaseBrokerTests(unittest.TestCase):
    def test_persistent_epoch_restart_and_surface_fencing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = os.path.join(tmpdir, "lease_state.sqlite3")
            signer = ControlCapsuleSigner("test-lease-broker-hmac-key-2026")
            broker = SingleWriterLeaseBroker(signer, db_path=db_file)

            lease1 = broker.acquire_lease(
                "T31-RESTART",
                "worker-a",
                "ImplementerA",
                op_level="L1",
                allowed_write_scopes=["src/omo/workflow_mesh.py"],
                now_ts=1000.0,
            )
            self.assertEqual(lease1["lease_epoch"], 1)
            with self.assertRaises(BrokerSecurityError) as conflict:
                broker.acquire_lease(
                    "T31-OTHER",
                    "worker-b",
                    "ImplementerB",
                    op_level="L1",
                    allowed_write_scopes=["src/omo/workflow_mesh.py"],
                    now_ts=1005.0,
                )
            self.assertIn("WRITE_SURFACE_CONFLICT", str(conflict.exception))
            restarted = SingleWriterLeaseBroker(signer, db_path=db_file)
            lease2 = restarted.acquire_lease(
                "T31-RESTART",
                "worker-b",
                "ImplementerB",
                op_level="L1",
                allowed_write_scopes=["src/omo/workflow_mesh.py"],
                now_ts=1020.0,
            )
            self.assertEqual(lease2["lease_epoch"], 2)
            with self.assertRaises(BrokerSecurityError) as fenced:
                restarted.commit_transition(lease1, "key-stale", "RUNNING->DONE", "sha256:111", now_ts=1030.0)
            self.assertIn("STALE_LEASE_EPOCH_FENCED", str(fenced.exception))
            committed = restarted.commit_transition(lease2, "key-current", "RUNNING->DONE", "sha256:222", now_ts=1030.0)
            self.assertEqual(committed["status"], "COMMITTED")
            restarted.close()

    def test_capsule_auth_idempotency_and_conflict(self):
        signer = ControlCapsuleSigner("test-lease-broker-hmac-key-2026")
        broker = SingleWriterLeaseBroker(signer)
        capsule = broker.acquire_lease(
            "T31-AUTH",
            "worker-a",
            "ImplementerA",
            op_level="L1",
            allowed_write_scopes=["lib/auth.py"],
            now_ts=2000.0,
        )

        unsigned = dict(capsule)
        unsigned.pop("hmac_sha256")
        with self.assertRaises(BrokerSecurityError):
            broker.commit_transition(unsigned, "key-auth", "RUNNING->DONE", "sha256:333", now_ts=2010.0)

        forged = dict(capsule)
        forged["op_level"] = "L3"
        with self.assertRaises(BrokerSecurityError):
            broker.commit_transition(forged, "key-forged", "RUNNING->DONE", "sha256:333", now_ts=2010.0)

        expired = broker.acquire_lease(
            "T31-EXPIRED",
            "worker-a",
            "ImplementerA",
            op_level="L1",
            ttl_seconds=5,
            allowed_write_scopes=["lib/expired.py"],
            now_ts=2100.0,
        )
        with self.assertRaises(BrokerSecurityError):
            broker.commit_transition(expired, "key-expired", "RUNNING->DONE", "sha256:444", now_ts=2200.0)

        high_risk_capsule = {
            "issuer": "control-home-01",
            "audience": "omo-worker",
            "task_id": "T31-HIGH-RISK",
            "worker_id": "worker-a",
            "clone_id": "clone-default",
            "role_id": "ImplementerA",
            "op_level": "L2",
            "lease_epoch": 1,
            "expires_at": 3000.0,
            "approval_ref": "",
            "allowed_write_scopes": ["lib/high_risk.py"],
        }
        with self.assertRaises(BrokerSecurityError):
            broker.commit_transition(
                signer.sign_capsule(high_risk_capsule),
                "key-high-risk",
                "RUNNING->DONE",
                "sha256:555",
                now_ts=2100.0,
            )

        idempotent = broker.commit_transition(
            capsule, "key-idem", "RUNNING->DONE", "sha256:666", now_ts=2010.0
        )
        self.assertEqual(idempotent["status"], "COMMITTED")
        replay = broker.commit_transition(
            capsule, "key-idem", "RUNNING->DONE", "sha256:666", now_ts=2011.0
        )
        self.assertEqual(replay["status"], "IDEMPOTENT_NOOP")
        with self.assertRaises(BrokerSecurityError) as conflict:
            broker.commit_transition(capsule, "key-idem", "RUNNING->FAILED", "sha256:666", now_ts=2012.0)
        self.assertIn("IDEMPOTENCY_KEY_PARAMETER_CONFLICT", str(conflict.exception))

        broker.close()
