"""Tests for eidos.federated_memory — CRDT vector clocks + cross-node memory sync.

Covers VectorClock comparison/merge, CRDTSet add/remove/merge, FederatedMemory
put/get/delete/query, sync peer management, prepare_sync_data/apply_sync_data
with conflict resolution, merge_with, and stats aggregation.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eidos.federated_memory import (
    CRDTSet,
    FederatedMemory,
    FederatedMemoryEntry,
    VectorClock,
)

# ── VectorClock ────────────────────────────────────────────────


class TestVectorClock:
    def test_default_empty(self):
        vc = VectorClock()
        assert vc.clocks == {}

    def test_increment_new_node(self):
        vc = VectorClock()
        vc.increment("node-a")
        assert vc.clocks == {"node-a": 1}

    def test_increment_existing_node(self):
        vc = VectorClock({"node-a": 1})
        vc.increment("node-a")
        assert vc.clocks == {"node-a": 2}

    def test_merge_takes_max_per_node(self):
        vc1 = VectorClock({"a": 2, "b": 1})
        vc2 = VectorClock({"a": 1, "b": 3, "c": 2})
        merged = vc1.merge(vc2)
        assert merged.clocks == {"a": 2, "b": 3, "c": 2}

    def test_compare_equal(self):
        vc1 = VectorClock({"a": 1, "b": 2})
        vc2 = VectorClock({"a": 1, "b": 2})
        assert vc1.compare(vc2) == "equal"

    def test_compare_before(self):
        """self strictly before other."""
        vc1 = VectorClock({"a": 1})
        vc2 = VectorClock({"a": 2})
        assert vc1.compare(vc2) == "before"

    def test_compare_after(self):
        """self strictly after other."""
        vc1 = VectorClock({"a": 2})
        vc2 = VectorClock({"a": 1})
        assert vc1.compare(vc2) == "after"

    def test_compare_concurrent(self):
        """self and other have divergent events."""
        vc1 = VectorClock({"a": 1, "b": 0})
        vc2 = VectorClock({"a": 0, "b": 1})
        assert vc1.compare(vc2) == "concurrent"

    def test_compare_with_disjoint_nodes(self):
        """Different nodes with different clocks → concurrent (not equal).

        Disjoint nodes have no relationship; both 'dominates' and 'dominated'
        flags become True, yielding "concurrent".
        """
        vc1 = VectorClock({"a": 1})
        vc2 = VectorClock({"b": 1})
        # Both nodes have unique values → concurrent
        assert vc1.compare(vc2) == "concurrent"

    def test_compare_with_disjoint_nodes_at_zero(self):
        """Different nodes with all-zero values → equal."""
        vc1 = VectorClock({"a": 0})
        vc2 = VectorClock({"b": 0})
        assert vc1.compare(vc2) == "equal"

    def test_to_dict_returns_copy(self):
        vc = VectorClock({"a": 1, "b": 2})
        d = vc.to_dict()
        assert d == {"a": 1, "b": 2}
        # Should be a copy, not a reference
        d["c"] = 99
        assert "c" not in vc.clocks

    def test_from_dict_classmethod(self):
        vc = VectorClock.from_dict({"a": 1, "b": 2})
        assert vc.clocks == {"a": 1, "b": 2}

    def test_from_dict_empty(self):
        vc = VectorClock.from_dict({})
        assert vc.clocks == {}


# ── FederatedMemoryEntry ──────────────────────────────────────


class TestFederatedMemoryEntry:
    def test_post_init_computes_hash(self):
        entry = FederatedMemoryEntry(
            key="k",
            value={"a": 1},
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        assert entry.content_hash != ""
        assert len(entry.content_hash) == 16  # sha256[:16]

    def test_explicit_hash_preserved(self):
        entry = FederatedMemoryEntry(
            key="k",
            value={"a": 1},
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
            content_hash="custom_hash_value",
        )
        assert entry.content_hash == "custom_hash_value"

    def test_verify_integrity_valid(self):
        entry = FederatedMemoryEntry(
            key="k",
            value={"a": 1},
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        assert entry.verify_integrity() is True

    def test_verify_integrity_tampered(self):
        entry = FederatedMemoryEntry(
            key="k",
            value={"a": 1},
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        # Tamper with value (hash becomes invalid)
        entry.value = {"a": 2}
        assert entry.verify_integrity() is False

    def test_default_trust_level(self):
        entry = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock(),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        assert entry.trust_level == 0.5

    def test_default_sync_priority(self):
        entry = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock(),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        assert entry.sync_priority == 1

    def test_default_not_deleted(self):
        entry = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock(),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        assert entry.deleted is False

    def test_hash_deterministic(self):
        """Same key+value → same hash (regardless of clock/timestamp)."""
        e1 = FederatedMemoryEntry(
            key="k",
            value={"a": 1, "b": 2},
            version=VectorClock({"n": 5}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        e2 = FederatedMemoryEntry(
            key="k",
            value={"b": 2, "a": 1},
            version=VectorClock({"n": 99}),
            timestamp=datetime(2020, 1, 1),
            node_id="other",
        )
        assert e1.content_hash == e2.content_hash


# ── CRDTSet ────────────────────────────────────────────────────


class TestCRDTSet:
    def test_add_and_get(self):
        s = CRDTSet()
        entry = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        s.add(entry)
        assert s.get("k") is entry

    def test_get_missing(self):
        s = CRDTSet()
        assert s.get("missing") is None

    def test_add_merges_existing_versions(self):
        s = CRDTSet()
        old = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            node_id="n",
        )
        new = FederatedMemoryEntry(
            key="k",
            value=2,
            version=VectorClock({"n": 2}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        s.add(old)
        s.add(new)
        # New value should win (newer timestamp)
        assert s.get("k").value == 2  # type: ignore[reportOptionalMemberAccess]

    def test_add_older_timestamp_does_not_overwrite(self):
        """If new entry has older timestamp, old value wins."""
        s = CRDTSet()
        old = FederatedMemoryEntry(
            key="k",
            value="current",
            version=VectorClock({"n": 2}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        older = FederatedMemoryEntry(
            key="k",
            value="stale",
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            node_id="n",
        )
        s.add(old)
        s.add(older)
        assert s.get("k").value == "current"  # type: ignore[reportOptionalMemberAccess]

    def test_remove_soft_delete(self):
        s = CRDTSet()
        entry = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        s.add(entry)
        s.remove("k", "n")
        assert s.get("k") is None

    def test_remove_nonexistent_is_safe(self):
        s = CRDTSet()
        s.remove("missing", "n")  # should not raise
        assert s.get("missing") is None

    def test_add_undoes_remove(self):
        """Re-adding a key removes it from the deletion set."""
        s = CRDTSet()
        old = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        new = FederatedMemoryEntry(
            key="k",
            value=2,
            version=VectorClock({"n": 2}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        s.add(old)
        s.remove("k", "n")
        s.add(new)
        assert s.get("k").value == 2  # type: ignore[reportOptionalMemberAccess]

    def test_values_returns_active_only(self):
        s = CRDTSet()
        active = FederatedMemoryEntry(
            key="a",
            value=1,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        deleted = FederatedMemoryEntry(
            key="b",
            value=2,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        soft_deleted = FederatedMemoryEntry(
            key="c",
            value=3,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        s.add(active)
        s.add(deleted)
        s.add(soft_deleted)
        s.remove("b", "n")
        soft_deleted.deleted = True  # soft delete via field
        values = s.values()
        assert len(values) == 1
        assert values[0].key == "a"

    def test_merge_both_empty(self):
        s1 = CRDTSet()
        s2 = CRDTSet()
        merged = s1.merge(s2)
        assert len(merged.values()) == 0

    def test_merge_disjoint_keys(self):
        s1 = CRDTSet()
        s2 = CRDTSet()
        s1.add(
            FederatedMemoryEntry(
                key="a", value=1, version=VectorClock({"n1": 1}), timestamp=datetime.now(UTC), node_id="n1"
            )
        )
        s2.add(
            FederatedMemoryEntry(
                key="b", value=2, version=VectorClock({"n2": 1}), timestamp=datetime.now(UTC), node_id="n2"
            )
        )
        merged = s1.merge(s2)
        keys = {e.key for e in merged.values()}
        assert keys == {"a", "b"}

    def test_merge_overlapping_newer_wins(self):
        """When same key in both, the one with later timestamp wins."""
        older = FederatedMemoryEntry(
            key="shared",
            value="old",
            version=VectorClock({"n": 1}),
            timestamp=datetime(2020, 1, 1),
            node_id="n",
        )
        newer = FederatedMemoryEntry(
            key="shared",
            value="new",
            version=VectorClock({"n": 1}),
            timestamp=datetime(2025, 1, 1),
            node_id="n",
        )
        s1 = CRDTSet()
        s2 = CRDTSet()
        s1.add(older)
        s2.add(newer)
        merged = s1.merge(s2)
        assert len(merged.values()) == 1
        assert merged.values()[0].value == "new"

    def test_merge_merges_removals(self):
        s1 = CRDTSet()
        s2 = CRDTSet()
        entry = FederatedMemoryEntry(
            key="k",
            value=1,
            version=VectorClock({"n": 1}),
            timestamp=datetime.now(UTC),
            node_id="n",
        )
        s1.add(entry)
        s2.add(entry)
        s1.remove("k", "n")
        merged = s1.merge(s2)
        assert merged.get("k") is None


# ── FederatedMemory ───────────────────────────────────────────


class TestFederatedMemory:
    def test_init(self):
        fm = FederatedMemory("node-a")
        assert fm.node_id == "node-a"
        assert fm._local_memory is not None
        assert fm._sync_peers == {}
        assert fm._sync_history == []

    def test_put_stores_and_returns_entry(self):
        fm = FederatedMemory("node-a")
        entry = fm.put("key1", "value1", trust_level=0.8)
        assert entry.key == "key1"
        assert entry.value == "value1"
        assert entry.trust_level == 0.8
        assert entry.node_id == "node-a"
        assert entry.version.clocks == {"node-a": 1}

    def test_put_default_trust_level(self):
        fm = FederatedMemory("node-a")
        entry = fm.put("k", "v")
        assert entry.trust_level == 1.0

    def test_get_returns_value(self):
        fm = FederatedMemory("node-a")
        fm.put("k", "v")
        assert fm.get("k") == "v"

    def test_get_missing_returns_none(self):
        fm = FederatedMemory("node-a")
        assert fm.get("missing") is None

    def test_delete_existing(self):
        fm = FederatedMemory("node-a")
        fm.put("k", "v")
        assert fm.delete("k") is True
        assert fm.get("k") is None

    def test_delete_nonexistent(self):
        fm = FederatedMemory("node-a")
        assert fm.delete("missing") is False

    def test_query_empty(self):
        fm = FederatedMemory("node-a")
        assert fm.query() == []

    def test_query_filters_by_min_trust(self):
        fm = FederatedMemory("node-a")
        fm.put("high", "v1", trust_level=0.9)
        fm.put("low", "v2", trust_level=0.1)
        result = fm.query(min_trust=0.5)
        assert len(result) == 1
        assert result[0].key == "high"

    def test_query_filters_by_since(self):
        fm = FederatedMemory("node-a")
        old = datetime.now(UTC) - timedelta(hours=2)
        _new = datetime.now(UTC)
        fm.put("old_key", "v1")
        # Manually override timestamp
        fm._local_memory._additions["old_key"].timestamp = old
        fm.put("new_key", "v2")
        result = fm.query(since=datetime.now(UTC) - timedelta(hours=1))
        assert len(result) == 1
        assert result[0].key == "new_key"

    def test_query_sorted_newest_first(self):
        fm = FederatedMemory("node-a")
        fm.put("a", "v")
        # Force older timestamp on first entry
        fm._local_memory._additions["a"].timestamp = datetime.now(UTC) - timedelta(hours=1)
        fm.put("b", "v")
        result = fm.query()
        assert result[0].key == "b"
        assert result[1].key == "a"

    def test_add_sync_peer_above_threshold(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", trust_level=0.5)
        assert "node-b" in fm._sync_peers
        assert fm._sync_peers["node-b"] == 0.5

    def test_add_sync_peer_below_threshold_rejected(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", trust_level=0.2)  # < 0.3
        assert "node-b" not in fm._sync_peers

    def test_add_sync_peer_at_threshold(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", trust_level=0.3)  # exactly threshold
        assert "node-b" in fm._sync_peers

    def test_remove_sync_peer(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        fm.remove_sync_peer("node-b")
        assert "node-b" not in fm._sync_peers

    def test_remove_sync_peer_nonexistent_is_safe(self):
        fm = FederatedMemory("node-a")
        fm.remove_sync_peer("nonexistent")  # no raise

    def test_prepare_sync_data_untrusted_returns_none(self):
        fm = FederatedMemory("node-a")
        result = fm.prepare_sync_data("node-b")  # not a peer
        assert result is None

    def test_prepare_sync_data_filters_by_trust(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        fm.put("trusted", "v1", trust_level=0.7)
        fm.put("untrusted", "v2", trust_level=0.1)
        result = fm.prepare_sync_data("node-b")
        assert result is not None
        keys = {e["key"] for e in result["entries"]}
        assert "trusted" in keys
        assert "untrusted" not in keys

    def test_prepare_sync_data_format(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        fm.put("k", "v")
        result = fm.prepare_sync_data("node-b")
        assert result["source"] == "node-a"  # type: ignore[reportOptionalSubscript]
        assert result["target"] == "node-b"  # type: ignore[reportOptionalSubscript]
        assert "entries" in result  # type: ignore[reportOperatorIssue]
        assert "sync_timestamp" in result  # type: ignore[reportOperatorIssue]

    def test_apply_sync_data_untrusted_source(self):
        fm = FederatedMemory("node-a")
        result = fm.apply_sync_data({"source": "unknown", "entries": []})
        assert "error" in result
        assert result["added"] == 0

    def test_apply_sync_data_adds_new(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        sync_data = {
            "source": "node-b",
            "entries": [
                {
                    "key": "k",
                    "value": "v",
                    "version": {"node-b": 1},
                    "timestamp": datetime.now(UTC).isoformat(),
                    "node_id": "node-b",
                    "trust_level": 0.5,
                    "deleted": False,
                    "content_hash": "",
                }
            ],
        }
        result = fm.apply_sync_data(sync_data)
        assert result["added"] == 1
        assert fm.get("k") == "v"

    def test_apply_sync_data_updates_existing(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        fm.put("k", "old")
        sync_data = {
            "source": "node-b",
            "entries": [
                {
                    "key": "k",
                    "value": "new",
                    "version": {"node-b": 1},
                    "timestamp": datetime.now(UTC).isoformat(),
                    "node_id": "node-b",
                    "trust_level": 0.5,
                    "deleted": False,
                    "content_hash": "",
                }
            ],
        }
        result = fm.apply_sync_data(sync_data)
        assert result["updated"] >= 1

    def test_apply_sync_data_records_history(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        sync_data = {"source": "node-b", "entries": []}
        fm.apply_sync_data(sync_data)
        assert len(fm._sync_history) == 1
        assert fm._sync_history[0]["source"] == "node-b"

    def test_merge_with_creates_combined(self):
        fm1 = FederatedMemory("node-a")
        fm2 = FederatedMemory("node-b")
        fm1.put("a1", "v")
        fm2.put("a2", "v")
        merged = fm1.merge_with(fm2)
        assert merged.node_id == "node-a+node-b"
        keys = {e.key for e in merged._local_memory.values()}
        assert "a1" in keys
        assert "a2" in keys

    def test_merge_with_combines_peers(self):
        fm1 = FederatedMemory("node-a")
        fm2 = FederatedMemory("node-b")
        fm1.add_sync_peer("peer-1", 0.7)
        fm2.add_sync_peer("peer-2", 0.6)
        merged = fm1.merge_with(fm2)
        assert merged._sync_peers.get("peer-1") == 0.7
        assert merged._sync_peers.get("peer-2") == 0.6

    def test_get_stats_empty(self):
        fm = FederatedMemory("node-a")
        stats = fm.get_stats()
        assert stats["total_entries"] == 0
        assert stats["sync_peers"] == 0
        assert stats["avg_trust"] == 0
        assert stats["sync_history_count"] == 0

    def test_get_stats_with_data(self):
        fm = FederatedMemory("node-a")
        fm.put("a", "v1", trust_level=0.8)
        fm.put("b", "v2", trust_level=0.6)
        fm.add_sync_peer("node-b", 0.5)
        stats = fm.get_stats()
        assert stats["total_entries"] == 2
        assert stats["sync_peers"] == 1
        assert abs(stats["avg_trust"] - 0.7) < 0.01

    def test_get_stats_recent_syncs(self):
        fm = FederatedMemory("node-a")
        fm.add_sync_peer("node-b", 0.5)
        for i in range(3):
            fm._sync_history.append({"source": "node-b", "added": i})
        stats = fm.get_stats()
        assert stats["sync_history_count"] == 3
        assert len(stats["recent_syncs"]) == 3

    def test_get_stats_recent_syncs_capped_at_5(self):
        fm = FederatedMemory("node-a")
        for i in range(10):
            fm._sync_history.append({"source": "node-b", "added": i})
        stats = fm.get_stats()
        assert len(stats["recent_syncs"]) == 5  # last 5
