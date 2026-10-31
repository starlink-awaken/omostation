from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.memory_tombstone_guard import MemoryTombstoneStore


class MemoryTombstoneGuardTests(unittest.TestCase):
    def test_required_attributes_query_and_persistent_wal_replay(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_file = os.path.join(tmpdir, "tombstone_wal.jsonl")
            store = MemoryTombstoneStore(wal_path=wal_file)
            record = store.ingest_memory("MEM-FAM-01", "家庭周末出行偏好与过敏记录", "S_family")
            self.assertEqual(len(store.canonical_records), 1)
            self.assertIn("record_ref", record)
            self.assertIn("withdrawal_state", record)
            self.assertEqual(len(store.query_active_memories("过敏")), 1)

            store.withdraw_memory("MEM-FAM-01", reason="user_requested_purge")
            self.assertEqual(len(store.query_active_memories("过敏")), 0)

            restarted = MemoryTombstoneStore(wal_path=wal_file)
            snapshot = [
                {
                    "record_ref": "MEM-FAM-01",
                    "memory_id": "MEM-FAM-01",
                    "content": "家庭周末出行偏好与过敏记录",
                    "sensitivity": "S_family",
                    "state": "scoped_active",
                }
            ]
            blocked = restarted.restore_from_snapshot_with_tombstone_replay(snapshot)
            self.assertEqual(blocked, 1)
            self.assertEqual(len(restarted.query_active_memories("过敏")), 0)
