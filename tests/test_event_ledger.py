"""W1-03 SQLite causal Event Ledger substrate — counter-proof tests.

Covers every negative/positive requirement from blueprint §10.2 / §25.2:

- duplicate keys: ``(producer, idempotency_key)`` dedup enforcement
- concurrent appends: contiguous sequence + continuous hash chain
- append-only: direct UPDATE/DELETE rejected by triggers
- payload: valid JSON accepted, invalid JSON rejected at DB + boundary
- integrity: clean chain passes; trigger-bypassed tampering is detected
- outbox: committed atomically with the append (no divergence)
- migrations: re-run is idempotent; a failed/corrupt migration is rejected
- anchors: correct root hash verifies, tampered anchor fails
- SQLite version gate: WAL enabled only for blueprint-safe versions
"""

from __future__ import annotations

import itertools
import json
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.event_ledger import (  # noqa: E402
    DEFAULT_OUTBOX_DESTINATION,
    DEFAULT_SCHEMA_VERSION,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
    OUTBOX_SENT,
    DuplicateEventError,
    IntegrityViolationError,
    InvalidPayloadError,
    LedgerBroker,
    LedgerError,
    LedgerSchemaError,
    apply_schema,
    is_wal_allowed,
    schema_fingerprint,
    wal_allowed_for_current,
)


def _broker(tmp_path: Path, **kwargs) -> LedgerBroker:
    return LedgerBroker.connect(tmp_path / "ledger.db", **kwargs)


def _append(broker: LedgerBroker, seq: int = 0, *, payload=None, **extra) -> int:
    return broker.append(
        event_type="Test.v1",
        producer="test",
        principal_id="p1",
        space_id="s1",
        correlation_id=f"c{seq}",
        payload={} if payload is None else payload,
        idempotency_key=f"ik{seq}",
        **extra,
    )


# ---------------------------------------------------------------------------
# Schema / physical model
# ---------------------------------------------------------------------------


def test_schema_contains_all_required_tables(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    names = schema_fingerprint(broker._conn)["tables"]
    broker.close()
    assert {
        "event_log",
        "projection_checkpoint",
        "event_outbox",
        "schema_migration",
        "integrity_anchor",
    } <= set(names)


def test_schema_contains_required_indexes(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    indexes = {
        row[0]
        for row in broker._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    broker.close()
    expected = {
        "idx_event_log_episode_sequence",
        "idx_event_log_principal_space_time",
        "idx_event_log_responsibility_time",
        "idx_event_log_event_type_time",
        "idx_event_log_mandate_sequence",
        "idx_event_outbox_state_next_attempt",
    }
    assert expected <= indexes


def test_event_log_has_producer_idempotency_unique(tmp_path: Path) -> None:
    """The (producer, idempotency_key) composite is enforced as UNIQUE."""
    broker = _broker(tmp_path)
    schema_sql = broker._conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'event_log'"
    ).fetchone()[0]
    broker.close()
    assert "UNIQUE(producer, idempotency_key)" in schema_sql


# ---------------------------------------------------------------------------
# Append + replay read
# ---------------------------------------------------------------------------


def test_append_and_read(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    seq = broker.append(
        event_type="SignalObserved.v1",
        producer="test",
        principal_id="p1",
        space_id="s1",
        correlation_id="c1",
        payload={"msg": "hello"},
        idempotency_key="ik1",
    )
    assert seq == 1
    events = broker.read(from_sequence=1)
    assert len(events) == 1
    assert events[0]["event_hash"] is not None
    assert json.loads(events[0]["payload_json"]) == {"msg": "hello"}
    broker.close()


def test_replay_from_sequence(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    replayed = broker.read(from_sequence=3)
    assert len(replayed) == 3
    assert replayed[0]["sequence"] == 3
    assert [e["sequence"] for e in replayed] == [3, 4, 5]
    broker.close()


def test_replay_with_filters(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    broker.append(
        event_type="A.v1",
        producer="p1",
        principal_id="x",
        space_id="s",
        correlation_id="c1",
        payload={},
        idempotency_key="a",
    )
    broker.append(
        event_type="B.v1",
        producer="p2",
        principal_id="x",
        space_id="s",
        correlation_id="c2",
        payload={},
        idempotency_key="b",
    )
    only_a = broker.read(event_type="A.v1")
    assert [e["event_type"] for e in only_a] == ["A.v1"]
    only_p2 = broker.read(producer="p2")
    assert [e["producer"] for e in only_p2] == ["p2"]
    broker.close()


# ---------------------------------------------------------------------------
# Duplicate keys
# ---------------------------------------------------------------------------


def test_duplicate_idempotency_key_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    broker.append(
        event_type="Test.v1",
        producer="test",
        principal_id="p1",
        space_id="s1",
        correlation_id="c1",
        payload={},
        idempotency_key="ik1",
    )
    with pytest.raises(DuplicateEventError):
        broker.append(
            event_type="Test.v1",
            producer="test",
            principal_id="p1",
            space_id="s1",
            correlation_id="c1",
            payload={},
            idempotency_key="ik1",
        )
    assert broker.count() == 1
    broker.close()


def test_same_key_different_producer_allowed(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    broker.append(
        event_type="T.v1",
        producer="a",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={},
        idempotency_key="ik",
    )
    broker.append(
        event_type="T.v1",
        producer="b",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={},
        idempotency_key="ik",
    )
    assert broker.count() == 2
    broker.close()


def test_duplicate_event_id_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    _append(broker, seq=1)
    with pytest.raises(LedgerError):
        broker.append(
            event_type="T.v1",
            producer="x",
            principal_id="p",
            space_id="s",
            correlation_id="c2",
            payload={},
            idempotency_key="ik-x",
            event_id=broker.read(from_sequence=1)[0]["event_id"],
        )
    broker.close()


# ---------------------------------------------------------------------------
# Concurrent appends: contiguous sequence + continuous chain
# ---------------------------------------------------------------------------


def test_concurrent_appends_sequence_contiguous(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    n = 24
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            broker.append(
                event_type="Test.v1",
                producer="test",
                principal_id="p1",
                space_id="s1",
                correlation_id=f"c{i}",
                payload={"i": i},
                idempotency_key=f"ik{i}",
            )
        except Exception as exc:  # pragma: no cover - failure surfacing
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent append failures: {errors}"
    events = broker.read(from_sequence=1)
    assert [e["sequence"] for e in events] == list(range(1, n + 1))
    assert broker.count() == n
    result = broker.verify_chain()
    assert result["ok"], result
    assert result["total"] == n
    broker.close()


# ---------------------------------------------------------------------------
# Append-only triggers
# ---------------------------------------------------------------------------


def test_trigger_rejects_direct_update(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    _append(broker, seq=1)
    conn = sqlite3.connect(str(broker.db_path))
    with pytest.raises(sqlite3.Error, match="append-only"):
        conn.execute("UPDATE event_log SET event_type='HACKED'")
    conn.close()
    broker.close()


def test_trigger_rejects_direct_delete(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    _append(broker, seq=1)
    conn = sqlite3.connect(str(broker.db_path))
    with pytest.raises(sqlite3.Error, match="append-only"):
        conn.execute("DELETE FROM event_log")
    conn.close()
    assert broker.count() == 1
    broker.close()


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------


def test_payload_valid_json_accepted(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    broker.append(
        event_type="T.v1",
        producer="t",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={"a": [1, 2], "b": "中"},
        idempotency_key="ik",
    )
    assert broker.count() == 1
    broker.close()


def test_payload_invalid_json_rejected_by_check(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = sqlite3.connect(str(broker.db_path))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
            "principal_id, space_id, correlation_id, producer, idempotency_key, "
            "occurred_at, recorded_at, privacy_class, payload_json, event_hash) "
            "VALUES (1, 'evt_bad', 'T.v1', '1', 'p', 's', 'c', 't', 'ik', "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'internal', "
            "'{not json', 'deadbeef')"
        )
    conn.close()
    broker.close()


def test_payload_non_mapping_rejected_at_boundary(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(InvalidPayloadError):
        broker.append(
            event_type="T.v1",
            producer="t",
            principal_id="p",
            space_id="s",
            correlation_id="c",
            payload=[1, 2],
            idempotency_key="ik",
        )
    assert broker.count() == 0
    broker.close()


def test_payload_non_serializable_rejected_at_boundary(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(InvalidPayloadError):
        broker.append(
            event_type="T.v1",
            producer="t",
            principal_id="p",
            space_id="s",
            correlation_id="c",
            payload={"bad": object()},
            idempotency_key="ik",
        )
    assert broker.count() == 0
    broker.close()


# ---------------------------------------------------------------------------
# Integrity: clean chain + tamper detection
# ---------------------------------------------------------------------------


def test_clean_chain_verifies(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(10):
        _append(broker, seq=i, payload={"i": i})
    result = broker.verify_chain()
    assert result["ok"]
    assert result["total"] == 10
    broker.close()


def test_chain_previous_hash_links_each_row(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    events = broker.read(from_sequence=1)
    assert events[0]["previous_hash"] is None
    for prev, cur in itertools.pairwise(events):
        assert cur["previous_hash"] == prev["event_hash"]
    broker.close()


def test_tamper_via_trigger_bypass_detected(tmp_path: Path) -> None:
    """Drop the append-only triggers, rewrite a row, then detect the break."""
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    conn = sqlite3.connect(str(broker.db_path))
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute(
        "UPDATE event_log SET payload_json = '{\"hacked\": true}' WHERE sequence = 3"
    )
    conn.commit()
    conn.close()
    result = broker.verify_chain()
    assert not result["ok"]
    assert result["first_bad_sequence"] == 3
    broker.close()


def test_tamper_previous_hash_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    conn = sqlite3.connect(str(broker.db_path))
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute("UPDATE event_log SET previous_hash = 'tampered' WHERE sequence = 4")
    conn.commit()
    conn.close()
    result = broker.verify_chain()
    assert not result["ok"]
    assert result["first_bad_sequence"] == 4
    broker.close()


def test_sequence_gap_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(4):
        _append(broker, seq=i)
    conn = sqlite3.connect(str(broker.db_path))
    # A smuggled row is only detectable because our verify_chain requires
    # contiguous sequence numbers.
    row = broker.read(from_sequence=4)[0]
    conn.execute(
        "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
        "principal_id, space_id, correlation_id, producer, idempotency_key, "
        "occurred_at, recorded_at, privacy_class, payload_json, previous_hash, "
        "event_hash) VALUES (?, 'evt_smuggled', 'T.v1', '1', 'p', 's', 'c9', "
        "'t', 'ik9', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'internal', "
        "'{}', ?, ?)",
        (6, row["event_hash"], row["event_hash"]),
    )
    conn.commit()
    conn.close()
    result = broker.verify_chain()
    assert not result["ok"]
    assert "gap" in result["error"] or result["first_bad_sequence"] == 6
    broker.close()


# ---------------------------------------------------------------------------
# Outbox atomicity
# ---------------------------------------------------------------------------


def test_outbox_written_in_same_transaction(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    seq = broker.append(
        event_type="T.v1",
        producer="t",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={},
        idempotency_key="ik",
        destinations=("fanout-a", "fanout-b"),
    )
    assert seq == 1
    entries = broker.outbox_entries()
    assert {e["destination"] for e in entries} == {"fanout-a", "fanout-b"}
    assert all(e["state"] == OUTBOX_PENDING for e in entries)
    broker.close()


def test_outbox_append_is_atomic_no_partial_write(tmp_path: Path) -> None:
    """If the outbox insert fails, the event row must roll back too."""
    broker = _broker(tmp_path)
    conn = broker._conn
    # Sabotage outbox delivery with a blocking trigger so the outbox INSERT
    # raises inside the append transaction.
    conn.execute(
        "CREATE TRIGGER trg_outbox_block "
        "BEFORE INSERT ON event_outbox "
        "BEGIN SELECT RAISE(ABORT, 'outbox intentionally blocked'); END"
    )
    conn.commit()
    with pytest.raises(LedgerError):
        broker.append(
            event_type="T.v1",
            producer="t",
            principal_id="p",
            space_id="s",
            correlation_id="c",
            payload={},
            idempotency_key="ik",
        )
    # The ledger commit must not have survived the failed outbox insert.
    assert broker.count() == 0
    broker.close()


def test_outbox_mark_sent_and_failed(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    broker.append(
        event_type="T.v1",
        producer="t",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={},
        idempotency_key="ik",
    )
    pending = broker.outbox_pending()
    assert len(pending) == 1
    event_id = pending[0]["event_id"]
    broker.outbox_mark(
        event_id, DEFAULT_OUTBOX_DESTINATION, state=OUTBOX_SENT, attempts=1
    )
    assert broker.outbox_pending() == []
    entries = broker.outbox_entries()
    assert entries[0]["state"] == OUTBOX_SENT
    assert entries[0]["attempts"] == 1
    broker.outbox_mark(
        event_id, DEFAULT_OUTBOX_DESTINATION, state=OUTBOX_FAILED, attempts=2
    )
    assert broker.outbox_entries()[0]["state"] == OUTBOX_FAILED
    broker.close()


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------


def test_migration_reapply_is_idempotent(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    status = broker.migration_status()
    assert len(status) == 1
    assert status[0]["version"] == "1"
    # Re-applying the same schema is a no-op (idempotent).
    apply_schema(broker._conn)
    assert len(broker.migration_status()) == 1
    broker.close()


def test_migration_checksum_mismatch_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("UPDATE schema_migration SET checksum = 'corrupt' WHERE version = '1'")
    conn.commit()
    with pytest.raises(LedgerSchemaError):
        apply_schema(conn)
    broker.close()


def test_migration_recorded_once_after_schema_applied(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    assert len(broker.migration_status()) == 1
    broker.close()
    # Reopening the file must not re-apply or duplicate the migration record.
    broker2 = _broker(tmp_path)
    assert len(broker2.migration_status()) == 1
    broker2.close()


# ---------------------------------------------------------------------------
# Integrity anchors
# ---------------------------------------------------------------------------


def test_anchor_created_and_verified(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    anchor = broker.create_anchor()
    assert anchor["from_sequence"] == 1
    assert anchor["to_sequence"] == 5
    result = broker.verify_anchor(anchor["anchor_id"])
    assert result["ok"], result
    broker.close()


def test_anchor_range_verification(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(10):
        _append(broker, seq=i)
    anchor = broker.create_anchor(from_sequence=3, to_sequence=7)
    result = broker.verify_anchor(anchor["anchor_id"])
    assert result["ok"]
    assert result["from_sequence"] == 3
    assert result["to_sequence"] == 7
    broker.close()


def test_anchor_detects_tamper(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    anchor = broker.create_anchor()
    conn = sqlite3.connect(str(broker.db_path))
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute("UPDATE event_log SET payload_json = '{\"x\": 1}' WHERE sequence = 2")
    conn.commit()
    conn.close()
    result = broker.verify_anchor(anchor["anchor_id"])
    assert not result["ok"]
    assert result["actual"] != result["expected"]
    broker.close()


def test_anchor_empty_range_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(LedgerError):
        broker.create_anchor(from_sequence=5, to_sequence=3)
    broker.close()


# ---------------------------------------------------------------------------
# SQLite version gate
# ---------------------------------------------------------------------------


def test_wal_gate_accepts_blueprint_safe_versions() -> None:
    assert is_wal_allowed((3, 51, 3))
    assert is_wal_allowed((3, 51, 4))
    assert is_wal_allowed((3, 53, 4))
    assert is_wal_allowed((3, 44, 6))
    assert is_wal_allowed((3, 50, 7))
    assert not is_wal_allowed((3, 44, 5))
    assert not is_wal_allowed((3, 50, 6))
    assert not is_wal_allowed((3, 50, 4))
    assert not is_wal_allowed((3, 45, 0))
    assert not is_wal_allowed((3, 49, 0))
    assert not is_wal_allowed(None)


def test_force_wal_removed_from_public_api(tmp_path: Path) -> None:
    """force_wal was a version-gate bypass; it must not be part of the API."""
    db = tmp_path / "ledger.db"
    with pytest.raises(TypeError):
        LedgerBroker.connect(db, force_wal=True)
    with pytest.raises(TypeError):
        LedgerBroker.connect(db, force_wal=False)


def test_wal_disabled_on_unsafe_runtime(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    # The dev venv ships SQLite 3.50.4, which is outside the blueprint safe
    # set; the broker must still function but must not claim WAL.
    if not wal_allowed_for_current():
        assert broker.wal_enabled is False
    _append(broker, seq=1)
    assert broker.verify_chain()["ok"]
    broker.close()


# ---------------------------------------------------------------------------
# Projection checkpoints
# ---------------------------------------------------------------------------


def test_checkpoint_set_and_get(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(3):
        _append(broker, seq=i)
    assert broker.checkpoint_get("proj-a") is None
    broker.checkpoint_set("proj-a", 2)
    checkpoint = broker.checkpoint_get("proj-a")
    assert checkpoint["last_sequence"] == 2
    broker.checkpoint_set("proj-a", 3)
    assert broker.checkpoint_get("proj-a")["last_sequence"] == 3
    broker.close()


# ---------------------------------------------------------------------------
# Cross-process / reopen consistency
# ---------------------------------------------------------------------------


def test_reopen_keeps_data_and_chain(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    b1 = LedgerBroker.connect(path)
    for i in range(4):
        _append(b1, seq=i)
    b1.close()
    b2 = LedgerBroker.connect(path)
    assert b2.count() == 4
    assert b2.verify_chain()["ok"]
    assert b2.read(from_sequence=1)[0]["event_hash"] is not None
    b2.close()


def test_sequential_read_consistent_with_write(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    seen: list[int] = []
    for i in range(6):
        seq = _append(broker, seq=i)
        seen.append(seq)
    assert seen == list(range(1, 7))
    assert [e["sequence"] for e in broker.read(from_sequence=1)] == seen
    broker.close()


# ---------------------------------------------------------------------------
# HARDENING ROUND (falsifier correction) — partial verify / episode / WAL /
# trigger recreate / lock sharing / checksum / drift fail-closed / NaN /
# anchor pre-check / checkpoint observability
# ---------------------------------------------------------------------------


# -- A1: partial verify_chain -----------------------------------------------


def test_partial_verify_chain_from_mid_clean(tmp_path: Path) -> None:
    """verify_chain(from_sequence=N) must pass on a clean chain."""
    broker = _broker(tmp_path)
    for i in range(10):
        _append(broker, seq=i)
    result = broker.verify_chain(from_sequence=3)
    assert result["ok"], result
    assert result["total"] == 10
    broker.close()


def test_partial_verify_chain_detects_tamper_in_range(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(6):
        _append(broker, seq=i)
    conn = sqlite3.connect(str(broker.db_path))
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute("UPDATE event_log SET payload_json = '{\"h\":1}' WHERE sequence = 4")
    conn.commit()
    conn.close()
    result = broker.verify_chain(from_sequence=3)
    assert not result["ok"]
    assert result["first_bad_sequence"] == 4
    broker.close()


# -- A2: episode_id enforcement ---------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        "Decision.v1",
        "Mandate.v1",
        "Action.v1",
        "Evidence.v1",
        "Outcome.v1",
        "Decision",
        "Action",
    ],
)
def test_episode_required_events_reject_missing_episode(
    tmp_path: Path, event_type: str
) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(LedgerError, match="episode_id"):
        broker.append(
            event_type=event_type,
            producer="t",
            principal_id="p",
            space_id="s",
            correlation_id="c",
            payload={},
            idempotency_key=f"ik-{event_type}",
        )
    assert broker.count() == 0
    broker.close()


@pytest.mark.parametrize(
    "event_type",
    ["Decision.v1", "Mandate.v1", "Action.v1", "Evidence.v1", "Outcome.v1"],
)
def test_episode_required_events_accept_episode(
    tmp_path: Path, event_type: str
) -> None:
    broker = _broker(tmp_path)
    seq = broker.append(
        event_type=event_type,
        producer="t",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={},
        idempotency_key=f"ik-{event_type}",
        episode_id="ep_1",
    )
    assert seq >= 1
    broker.close()


def test_non_episode_event_without_episode_allowed(tmp_path: Path) -> None:
    """SignalObserved and other event classes may lack an episode_id."""
    broker = _broker(tmp_path)
    broker.append(
        event_type="SignalObserved.v1",
        producer="t",
        principal_id="p",
        space_id="s",
        correlation_id="c",
        payload={},
        idempotency_key="ik-sig",
    )
    assert broker.count() == 1
    broker.close()


def test_episode_required_db_trigger(tmp_path: Path) -> None:
    """The DB trigger must reject a missing episode even on raw INSERT."""
    broker = _broker(tmp_path)
    conn = sqlite3.connect(str(broker.db_path))
    with pytest.raises(sqlite3.Error, match="episode_id"):
        conn.execute(
            "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
            "principal_id, space_id, correlation_id, producer, idempotency_key, "
            "occurred_at, recorded_at, privacy_class, payload_json, event_hash) "
            "VALUES (1, 'e1', 'Decision.v1', '1', 'p', 's', 'c', 't', 'ik1', "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'internal', '{}', 'h1')"
        )
    conn.close()
    assert broker.count() == 0
    broker.close()


def test_non_episode_db_trigger_allows_raw_insert(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = sqlite3.connect(str(broker.db_path))
    conn.execute(
        "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
        "principal_id, space_id, correlation_id, producer, idempotency_key, "
        "occurred_at, recorded_at, privacy_class, payload_json, event_hash) "
        "VALUES (1, 'e2', 'SignalObserved.v1', '1', 'p', 's', 'c', 't', 'ik2', "
        "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'internal', '{}', 'h2')"
    )
    conn.commit()
    conn.close()
    assert broker.count() == 1
    broker.close()


# -- A4: persistent WAL downgrade / actual PRAGMA reporting ------------------


def test_wal_enabled_reports_actual_pragma(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    actual = broker._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert (str(actual).lower() == "wal") == broker.wal_enabled
    assert broker.journal_mode() == str(actual).lower()
    broker.close()


def test_wal_false_negative_on_reopen_prevented(tmp_path: Path, monkeypatch) -> None:
    """Unsafe runtime reopening a WAL-persisted DB must not report wal=False
    while the DB is actually still in WAL mode — it must downgrade.

    Runtime-independent: the WAL-persisted database is prepared with a raw
    sqlite3 connection (no dependency on the hosting SQLite being a
    blueprint-safe version), then reopened through the broker with the version
    gate forced to an unsafe version.
    """
    db = tmp_path / "wal.db"
    # Prepare: force the file into WAL mode with a plain connection.
    prep = sqlite3.connect(str(db))
    prep.execute("PRAGMA journal_mode=WAL")
    prep.close()
    # The DB file is now durably in WAL mode regardless of the hosting runtime.
    del prep

    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    try:
        b2 = LedgerBroker.connect(db)  # unsafe runtime
    except LedgerError as exc:
        # Explicit fail-closed is acceptable per the correction: refusing to
        # operate a WAL database under an unsafe version.
        assert "WAL" in str(exc) or "journal" in str(exc)
        return
    mode = b2._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() != "wal"
    assert b2.wal_enabled is False
    assert b2.journal_mode() == str(mode).lower()
    _append(b2, seq=1)
    assert b2.verify_chain()["ok"]
    b2.close()


def test_unsafe_runtime_never_enables_wal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    broker = _broker(tmp_path)
    assert broker.wal_enabled is False
    mode = broker._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() != "wal"
    _append(broker, seq=1)
    assert broker.verify_chain()["ok"]
    broker.close()


# -- A5: dropped/modified trigger fails closed on reopen -----------------------


def test_dropped_trigger_fails_closed_on_reopen(tmp_path: Path) -> None:
    """A dropped trigger is drift, not self-healable: reopen must fail closed."""
    db = tmp_path / "ledger.db"
    b1 = LedgerBroker.connect(db)
    b1.close()
    conn = sqlite3.connect(str(db))
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.commit()
    conn.close()
    with pytest.raises(LedgerSchemaError, match="trigger"):
        LedgerBroker.connect(db)
    # The database is NOT auto-repaired; the trigger is still missing.
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='trg_event_log_no_update'"
    ).fetchone()
    assert row is None
    conn.close()


def test_modified_trigger_fails_closed_on_reopen(tmp_path: Path) -> None:
    """A trigger whose SQL definition changed is drift and must fail closed."""
    db = tmp_path / "ledger.db"
    b1 = LedgerBroker.connect(db)
    b1.close()
    conn = sqlite3.connect(str(db))
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute(
        "CREATE TRIGGER trg_event_log_no_delete "
        "BEFORE DELETE ON event_log "
        "BEGIN SELECT RAISE(ABORT, 'tampered'); END"
    )
    conn.commit()
    conn.close()
    with pytest.raises(LedgerSchemaError, match="trigger"):
        LedgerBroker.connect(db)


def test_trigger_definition_drift_detected_by_verify_schema(tmp_path: Path) -> None:
    """verify_schema must compare the stored trigger SQL, not just the name."""
    from omo.event_ledger.schema import verify_schema

    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("DROP TRIGGER trg_event_log_episode_required")
    conn.execute(
        "CREATE TRIGGER trg_event_log_episode_required "
        "BEFORE INSERT ON event_log "
        "WHEN NEW.event_type = 'Decision.v1' "
        "BEGIN SELECT RAISE(ABORT, 'weakened'); END"
    )
    conn.commit()
    with pytest.raises(LedgerSchemaError, match="trigger"):
        verify_schema(conn)
    broker.close()


# -- B1: busy_timeout floor ---------------------------------------------------


def test_busy_timeout_floor_enforced(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    with pytest.raises(LedgerError, match="busy_timeout"):
        LedgerBroker.connect(db, busy_timeout_ms=1)
    with pytest.raises(LedgerError, match="busy_timeout"):
        LedgerBroker.connect(db, busy_timeout_ms=0)
    with pytest.raises(LedgerError, match="busy_timeout"):
        LedgerBroker.connect(db, busy_timeout_ms=-5)
    broker = LedgerBroker.connect(db, busy_timeout_ms=5000)
    broker.close()
    broker = LedgerBroker.connect(db, busy_timeout_ms=9000)
    broker.close()


def test_busy_timeout_actually_set(tmp_path: Path) -> None:
    broker = _broker(tmp_path, busy_timeout_ms=8000)
    timeout = broker._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout == 8000
    broker.close()


# -- B2: checksum covers actual DDL + triggers + indexes ---------------------


def test_checksum_derived_from_actual_sql_text() -> None:
    import hashlib

    from omo.event_ledger.schema import LEDGER_DDL, LEDGER_TRIGGERS, SCHEMA_CHECKSUM

    expected = hashlib.sha256(
        (LEDGER_DDL + "\n" + LEDGER_TRIGGERS).encode("utf-8")
    ).hexdigest()
    assert SCHEMA_CHECKSUM == expected


def test_checksum_changes_when_sql_text_changes() -> None:
    """The checksum must not be a hand-written column list; it must track the
    actual SQL text, so altering triggers/indexes/CHECK changes it."""
    import hashlib

    from omo.event_ledger.schema import LEDGER_DDL, LEDGER_TRIGGERS

    base = hashlib.sha256(
        (LEDGER_DDL + "\n" + LEDGER_TRIGGERS).encode("utf-8")
    ).hexdigest()
    tampered_trigger = LEDGER_TRIGGERS + "\n-- injected comment"
    alt = hashlib.sha256(
        (LEDGER_DDL + "\n" + tampered_trigger).encode("utf-8")
    ).hexdigest()
    assert alt != base


def test_checksum_recorded_in_migration(tmp_path: Path) -> None:
    from omo.event_ledger.schema import SCHEMA_CHECKSUM

    broker = _broker(tmp_path)
    status = broker.migration_status()
    assert status[0]["checksum"] == SCHEMA_CHECKSUM
    broker.close()


# -- B3: WAL checkpoint observability -----------------------------------------


def test_wal_checkpoint_receipt(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    receipt = broker.wal_checkpoint()
    assert "busy" in receipt
    assert "log_frames" in receipt
    assert "checkpointed_frames" in receipt
    assert receipt["mode"] == "PASSIVE"
    assert receipt["journal_mode"] == broker.journal_mode()
    assert isinstance(receipt["busy"], int)
    assert isinstance(receipt["log_frames"], int)
    assert isinstance(receipt["checkpointed_frames"], int)
    # Non-WAL DBs report a zero triple, still a valid receipt.
    broker2 = _broker(
        tmp_path
    )  # same path; actual journal mode is whatever gate allows
    r2 = broker2.wal_checkpoint(mode="FULL")
    assert r2["mode"] == "FULL"
    broker.close()
    broker2.close()


def test_wal_checkpoint_invalid_mode(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(LedgerError):
        broker.wal_checkpoint(mode="BOGUS")
    broker.close()


# -- B4: process-wide lock sharing --------------------------------------------


def test_same_path_shares_process_lock(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    b1 = LedgerBroker.connect(db)
    b2 = LedgerBroker.connect(db)
    assert b1._lock is b2._lock
    b1.close()
    b2.close()


def test_different_paths_get_distinct_locks(tmp_path: Path) -> None:
    b1 = LedgerBroker.connect(tmp_path / "a.db")
    b2 = LedgerBroker.connect(tmp_path / "b.db")
    assert b1._lock is not b2._lock
    b1.close()
    b2.close()


def test_dual_broker_concurrent_appends_contiguous(tmp_path: Path) -> None:
    """Two broker handles on the same DB must share one lock and produce a
    contiguous, chain-continuous ledger under concurrency."""
    db = tmp_path / "ledger.db"
    b1 = LedgerBroker.connect(db)
    b2 = LedgerBroker.connect(db)
    n = 20
    errors: list[Exception] = []

    def worker(broker: LedgerBroker, start: int) -> None:
        try:
            for i in range(start, start + n // 2):
                broker.append(
                    event_type="Test.v1",
                    producer="test",
                    principal_id="p1",
                    space_id="s1",
                    correlation_id=f"c{i}",
                    payload={"i": i},
                    idempotency_key=f"ik{i}",
                )
        except Exception as exc:  # pragma: no cover - failure surfacing
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(b1, 0))
    t2 = threading.Thread(target=worker, args=(b2, n // 2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"concurrent append failures: {errors}"
    events = b1.read(from_sequence=1)
    assert [e["sequence"] for e in events] == list(range(1, n + 1))
    assert b1.verify_chain()["ok"]
    b1.close()
    b2.close()


# -- apply_schema explicit single transaction / no residue --------------------


def test_apply_schema_single_transaction_no_residue(tmp_path: Path) -> None:
    """A malformed pre-existing table must abort the whole migration and leave
    no partially-created schema_migration/objects behind."""
    db = tmp_path / "bad.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE event_outbox (wrong_shape TEXT)")
    conn.commit()
    with pytest.raises((LedgerSchemaError, sqlite3.OperationalError)):
        apply_schema(conn)
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    # The pre-existing malformed table remains, but no new objects (including
    # schema_migration) were created by the failed migration.
    assert names == {"event_outbox"}
    conn.close()


def test_migration_record_not_written_on_failure(tmp_path: Path) -> None:
    db = tmp_path / "bad2.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE integrity_anchor (bad TEXT)")
    conn.commit()
    with pytest.raises((LedgerSchemaError, sqlite3.OperationalError)):
        apply_schema(conn)
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migration'"
    ).fetchone()
    assert row is None, "schema_migration must not survive a failed migration"
    conn.close()


# -- drift fail-closed on registered migration --------------------------------


def test_registered_migration_column_drift_fails_closed(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    # Rebuild event_log without the event_type column (simulates tampering).
    conn.execute("ALTER TABLE event_log RENAME TO event_log_old")
    conn.execute(
        "CREATE TABLE event_log ("
        "sequence INTEGER PRIMARY KEY AUTOINCREMENT,"
        "event_id TEXT NOT NULL UNIQUE,"
        "schema_version TEXT NOT NULL,"
        "principal_id TEXT NOT NULL,"
        "space_id TEXT NOT NULL,"
        "correlation_id TEXT NOT NULL,"
        "producer TEXT NOT NULL,"
        "idempotency_key TEXT NOT NULL,"
        "occurred_at TEXT NOT NULL,"
        "recorded_at TEXT NOT NULL,"
        "privacy_class TEXT NOT NULL,"
        "payload_json TEXT NOT NULL,"
        "event_hash TEXT NOT NULL,"
        "UNIQUE(producer, idempotency_key))"
    )
    conn.commit()
    with pytest.raises(LedgerSchemaError, match="event_log"):
        apply_schema(conn)
    broker.close()


def test_registered_migration_index_drift_fails_closed(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("DROP INDEX idx_event_log_episode_sequence")
    conn.commit()
    with pytest.raises(LedgerSchemaError, match="index"):
        apply_schema(conn)
    broker.close()


def test_registered_migration_trigger_drift_fails_closed(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.commit()
    # Already-migrated databases never auto-repair a dropped trigger.
    with pytest.raises(LedgerSchemaError, match="trigger"):
        apply_schema(conn)
    broker.close()


# -- NaN / Infinity payload rejection -----------------------------------------


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_payload_rejected(tmp_path: Path, bad_value: float) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(InvalidPayloadError, match="NaN|Infinity|JSON"):
        broker.append(
            event_type="T.v1",
            producer="t",
            principal_id="p",
            space_id="s",
            correlation_id="c",
            payload={"v": bad_value},
            idempotency_key="ik",
        )
    assert broker.count() == 0
    broker.close()


def test_nested_non_finite_payload_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(InvalidPayloadError):
        broker.append(
            event_type="T.v1",
            producer="t",
            principal_id="p",
            space_id="s",
            correlation_id="c",
            payload={"a": {"b": [float("inf")]}},
            idempotency_key="ik",
        )
    assert broker.count() == 0
    broker.close()


# -- anchor refuses broken chain / gap ----------------------------------------


def test_anchor_rejects_broken_chain(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    conn = sqlite3.connect(str(broker.db_path))
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute("UPDATE event_log SET payload_json = '{\"x\":1}' WHERE sequence = 2")
    conn.commit()
    conn.close()
    with pytest.raises(IntegrityViolationError):
        broker.create_anchor()
    broker.close()


def test_anchor_rejects_sequence_gap(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(4):
        _append(broker, seq=i)
    conn = sqlite3.connect(str(broker.db_path))
    row = broker.read(from_sequence=4)[0]
    conn.execute(
        "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
        "principal_id, space_id, correlation_id, producer, idempotency_key, "
        "occurred_at, recorded_at, privacy_class, payload_json, previous_hash, "
        "event_hash) VALUES (?, 'evt_gap', 'T.v1', '1', 'p', 's', 'c9', "
        "'t', 'ik9', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'internal', "
        "'{}', ?, ?)",
        (6, row["event_hash"], row["event_hash"]),
    )
    conn.commit()
    conn.close()
    with pytest.raises(IntegrityViolationError):
        broker.create_anchor()
    broker.close()


# -- DEFAULT_SCHEMA_VERSION alignment -----------------------------------------


def test_default_schema_version_matches_event_envelope() -> None:

    assert DEFAULT_SCHEMA_VERSION == "event-envelope/v1"


def test_appended_event_carries_event_envelope_schema_version(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    _append(broker, seq=1)
    event = broker.read(from_sequence=1)[0]
    assert event["schema_version"] == "event-envelope/v1"
    broker.close()


# ---------------------------------------------------------------------------
# HARDENING ROUND 2 (independent falsifier) — tail-beyond verify/anchor,
# extra-column drift, same-name index on wrong table, weakened CHECK,
# unexpected tables, exact index DDL, verify_chain range edges, connect close
# ---------------------------------------------------------------------------


# -- verify_chain range edges ------------------------------------------------


def test_verify_chain_high_less_than_low_fails(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    result = broker.verify_chain(from_sequence=4, to_sequence=3)
    assert not result["ok"]
    assert "range" in result["error"] or "invalid" in result["error"]
    broker.close()


def test_verify_chain_empty_default_ok(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    result = broker.verify_chain()
    assert result["ok"]
    assert result["total"] == 0
    broker.close()


def test_verify_chain_empty_explicit_range_fails(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    result = broker.verify_chain(from_sequence=1, to_sequence=5)
    assert not result["ok"]
    assert "empty" in result["error"]
    broker.close()


def test_verify_chain_from_beyond_tail_fails(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    result = broker.verify_chain(from_sequence=7)
    assert not result["ok"]
    assert "tail" in result["error"]
    broker.close()


def test_verify_chain_to_beyond_tail_fails(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    result = broker.verify_chain(to_sequence=100)
    assert not result["ok"]
    assert "gap" in result["error"]
    broker.close()


def test_verify_chain_default_range_succeeds(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    assert broker.verify_chain()["ok"]
    broker.close()


class _FakeCursor:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def fetchall(self) -> list:
        return self._rows


class _SnapshotHookConnection(sqlite3.Connection):
    """sqlite3.Connection subclass whose execute() can pause on the ledger
    snapshot SELECT so tests can interleave a concurrent append."""

    _snapshot_hook: Any = None

    def execute(self, sql: str, *args: Any) -> Any:
        cursor = super().execute(sql, *args)
        hook = getattr(self, "_snapshot_hook", None)
        if hook is not None and str(sql).startswith("SELECT * FROM event_log"):
            rows = cursor.fetchall()
            return _FakeCursor(hook(rows))
        return cursor


def _make_hook_broker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook: Any,
) -> LedgerBroker:
    """Build a broker whose connection triggers ``hook(snapshot_rows)`` on the
    verify_chain snapshot SELECT; the hook returns the rows verify must see."""
    import omo.event_ledger.broker as broker_mod

    real_connect = sqlite3.connect

    def hooked_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs["factory"] = _SnapshotHookConnection
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(broker_mod.sqlite3, "connect", hooked_connect)
    broker = LedgerBroker.connect(tmp_path / "ledger.db")
    broker._conn._snapshot_hook = hook
    return broker


def test_verify_chain_snapshot_consistent_under_concurrent_append(
    tmp_path: Path, monkeypatch
) -> None:
    """A concurrent append landing after the snapshot read must not change
    verify_chain's reported total/range: they refer to the frozen snapshot,
    while the database's live count has already grown."""
    snapshot_triggered = threading.Event()
    append_done = threading.Event()
    captured: list = []

    def hook(snapshot_rows: list) -> list:
        captured.extend(snapshot_rows)
        snapshot_triggered.set()
        append_done.wait(timeout=5)
        return snapshot_rows

    broker = _make_hook_broker(tmp_path, monkeypatch, hook=hook)
    for i in range(6):
        _append(broker, seq=i)
    assert broker.count() == 6

    def run_append() -> None:
        # Wait for verify_chain to freeze its snapshot first, then write so
        # the concurrent append provably lands AFTER the snapshot read.
        snapshot_triggered.wait(timeout=5)
        writer = sqlite3.connect(str(broker.db_path))
        writer.execute(
            "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
            "principal_id, space_id, correlation_id, producer, idempotency_key, "
            "occurred_at, recorded_at, privacy_class, payload_json, event_hash) "
            "VALUES (7, 'evt_late', 'Test.v1', 'event-envelope/v1', 'p1', 's1', "
            "'c-late', 'other', 'ik-late', '2026-01-01T00:00:00Z', "
            "'2026-01-01T00:00:00Z', 'internal', '{}', 'x')"
        )
        writer.commit()
        writer.close()
        append_done.set()

    thread = threading.Thread(target=run_append)
    thread.start()
    result = broker.verify_chain()
    thread.join(timeout=5)

    # The verify result describes the snapshot taken at verify start: 6 rows
    # and a contiguous 1..6 chain. The live database has already grown to 7.
    assert len(captured) == 6
    assert result["ok"], result
    assert result["total"] == 6
    assert broker.count() == 7
    broker.close()


def test_verify_chain_partial_snapshot_consistent_under_concurrent_append(
    tmp_path: Path, monkeypatch
) -> None:
    """Partial verification (from_sequence>1) must also stay anchored to the
    snapshot: total reflects the snapshot, and the prior-row hash comes from
    the same frozen view even if more rows arrive concurrently."""
    snapshot_triggered = threading.Event()
    append_done = threading.Event()
    captured: list = []

    def hook(snapshot_rows: list) -> list:
        captured.extend(snapshot_rows)
        snapshot_triggered.set()
        append_done.wait(timeout=5)
        return snapshot_rows

    broker = _make_hook_broker(tmp_path, monkeypatch, hook=hook)
    for i in range(6):
        _append(broker, seq=i)

    def run_append() -> None:
        snapshot_triggered.wait(timeout=5)
        writer = sqlite3.connect(str(broker.db_path))
        writer.execute(
            "INSERT INTO event_log(sequence, event_id, event_type, schema_version, "
            "principal_id, space_id, correlation_id, producer, idempotency_key, "
            "occurred_at, recorded_at, privacy_class, payload_json, event_hash) "
            "VALUES (7, 'evt_late2', 'Test.v1', 'event-envelope/v1', 'p1', 's1', "
            "'c-late', 'other', 'ik-late-2', '2026-01-01T00:00:00Z', "
            "'2026-01-01T00:00:00Z', 'internal', '{}', 'x')"
        )
        writer.commit()
        writer.close()
        append_done.set()

    thread = threading.Thread(target=run_append)
    thread.start()
    result = broker.verify_chain(from_sequence=3, to_sequence=6)
    thread.join(timeout=5)

    # Range [3,6] verified against the frozen 6-row snapshot; live count grew.
    assert len(captured) == 6
    assert result["ok"], result
    assert result["total"] == 6
    assert broker.count() == 7
    broker.close()


# -- tail-beyond anchor ------------------------------------------------------


def test_create_anchor_to_beyond_tail_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    with pytest.raises(IntegrityViolationError):
        broker.create_anchor(to_sequence=100)
    broker.close()


def test_create_anchor_from_beyond_tail_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    for i in range(5):
        _append(broker, seq=i)
    with pytest.raises(IntegrityViolationError):
        broker.create_anchor(from_sequence=7)
    broker.close()


def test_create_anchor_empty_range_edges(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(LedgerError):
        broker.create_anchor(from_sequence=1, to_sequence=0)
    broker.close()


# -- extra column drift ------------------------------------------------------


def test_extra_column_in_event_log_drift(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("ALTER TABLE event_log ADD COLUMN rogue_col TEXT")
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="DDL changed"):
        verify_schema(conn)
    broker.close()


def test_extra_column_in_outbox_drift(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("ALTER TABLE event_outbox ADD COLUMN rogue_col TEXT")
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="DDL changed"):
        verify_schema(conn)
    broker.close()


# -- unexpected tables -------------------------------------------------------


def test_unexpected_table_rejected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("CREATE TABLE rogue_table (id INTEGER)")
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="unexpected tables"):
        verify_schema(conn)
    broker.close()


# -- same-name index on wrong table ------------------------------------------


def test_index_moved_to_wrong_table_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    # Move idx_event_log_episode_sequence onto event_outbox.
    conn.execute("DROP INDEX idx_event_log_episode_sequence")
    conn.execute(
        "CREATE INDEX idx_event_log_episode_sequence "
        "ON event_outbox(event_id, destination)"
    )
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="definition changed|on table"):
        verify_schema(conn)
    broker.close()


# -- weakened / altered CHECK ------------------------------------------------


def test_weakened_json_check_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    # Rebuild event_log with a weakened CHECK (always true). Drop the old
    # triggers and table so no rogue object lingers.
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute("DROP TRIGGER trg_event_log_episode_required")
    conn.execute("DROP INDEX idx_event_log_episode_sequence")
    conn.execute("DROP INDEX idx_event_log_principal_space_time")
    conn.execute("DROP INDEX idx_event_log_responsibility_time")
    conn.execute("DROP INDEX idx_event_log_event_type_time")
    conn.execute("DROP INDEX idx_event_log_mandate_sequence")
    conn.execute("DROP TABLE event_log")
    conn.execute(
        "CREATE TABLE event_log ("
        "sequence INTEGER PRIMARY KEY AUTOINCREMENT,"
        "event_id TEXT NOT NULL UNIQUE,"
        "event_type TEXT NOT NULL,"
        "schema_version TEXT NOT NULL,"
        "episode_id TEXT,"
        "principal_id TEXT NOT NULL,"
        "space_id TEXT NOT NULL,"
        "role_context_id TEXT,"
        "responsibility_id TEXT,"
        "mandate_id TEXT,"
        "correlation_id TEXT NOT NULL,"
        "causation_id TEXT,"
        "producer TEXT NOT NULL,"
        "idempotency_key TEXT NOT NULL,"
        "occurred_at TEXT NOT NULL,"
        "recorded_at TEXT NOT NULL,"
        "privacy_class TEXT NOT NULL,"
        "payload_json TEXT NOT NULL CHECK(json_valid(payload_json) OR 1=1),"
        "evidence_uri TEXT,"
        "previous_hash TEXT,"
        "event_hash TEXT NOT NULL,"
        "UNIQUE(producer, idempotency_key))"
    )
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="DDL changed"):
        verify_schema(conn)
    broker.close()


def test_altered_unique_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("DROP TRIGGER trg_event_log_no_update")
    conn.execute("DROP TRIGGER trg_event_log_no_delete")
    conn.execute("DROP TRIGGER trg_event_log_episode_required")
    conn.execute("DROP INDEX idx_event_log_episode_sequence")
    conn.execute("DROP INDEX idx_event_log_principal_space_time")
    conn.execute("DROP INDEX idx_event_log_responsibility_time")
    conn.execute("DROP INDEX idx_event_log_event_type_time")
    conn.execute("DROP INDEX idx_event_log_mandate_sequence")
    conn.execute("DROP TABLE event_log")
    conn.execute(
        "CREATE TABLE event_log ("
        "sequence INTEGER PRIMARY KEY AUTOINCREMENT,"
        "event_id TEXT NOT NULL UNIQUE,"
        "event_type TEXT NOT NULL,"
        "schema_version TEXT NOT NULL,"
        "episode_id TEXT,"
        "principal_id TEXT NOT NULL,"
        "space_id TEXT NOT NULL,"
        "role_context_id TEXT,"
        "responsibility_id TEXT,"
        "mandate_id TEXT,"
        "correlation_id TEXT NOT NULL,"
        "causation_id TEXT,"
        "producer TEXT NOT NULL,"
        "idempotency_key TEXT NOT NULL,"
        "occurred_at TEXT NOT NULL,"
        "recorded_at TEXT NOT NULL,"
        "privacy_class TEXT NOT NULL,"
        "payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),"
        "evidence_uri TEXT,"
        "previous_hash TEXT,"
        "event_hash TEXT NOT NULL,"
        "UNIQUE(producer, idempotency_key, episode_id))"
    )
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="DDL changed"):
        verify_schema(conn)
    broker.close()


# -- exact index DDL drift ---------------------------------------------------


def test_index_changed_to_unique_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("DROP INDEX idx_event_log_episode_sequence")
    conn.execute(
        "CREATE UNIQUE INDEX idx_event_log_episode_sequence "
        "ON event_log(episode_id, sequence)"
    )
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="definition changed"):
        verify_schema(conn)
    broker.close()


def test_index_column_order_drift_detected(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    conn = broker._conn
    conn.execute("DROP INDEX idx_event_log_episode_sequence")
    conn.execute(
        "CREATE INDEX idx_event_log_episode_sequence ON event_log(sequence, episode_id)"
    )
    conn.commit()
    from omo.event_ledger.schema import verify_schema

    with pytest.raises(LedgerSchemaError, match="definition changed|columns"):
        verify_schema(conn)
    broker.close()


# -- connect failure closes connection ---------------------------------------


def _spy_connect_and_force_failure(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    *,
    failure: str,
) -> sqlite3.Connection:
    """Spy on sqlite3.connect and force a failure during LedgerBroker.connect.

    Returns the actual sqlite3.Connection object that the broker opened, so
    the test can prove it was closed after the failed connect.
    """
    import omo.event_ledger.broker as broker_mod

    real_connect = sqlite3.connect
    captured: list[sqlite3.Connection] = []

    def spy_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)
        captured.append(conn)
        return conn

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise LedgerError(f"forced failure in {failure}")

    monkeypatch.setattr(broker_mod.sqlite3, "connect", spy_connect)
    if failure == "apply_schema":
        monkeypatch.setattr(broker_mod, "apply_schema", boom)
    else:
        monkeypatch.setattr(LedgerBroker, "_configure_journal_mode", boom)
    with pytest.raises(LedgerError, match="forced failure"):
        LedgerBroker.connect(db)
    assert len(captured) == 1, "broker must have opened exactly one connection"
    return captured[0]


def _assert_connection_closed(conn: sqlite3.Connection) -> None:
    """A closed sqlite3.Connection raises ProgrammingError on any use."""
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
    # And it must not be usable indirectly either.
    try:
        conn.close()
    except sqlite3.Error:  # pragma: no cover - closed close is a no-op
        pass


def test_connect_failure_apply_schema_closes_connection(
    tmp_path: Path, monkeypatch
) -> None:
    """A failed connect during apply_schema must close the raw connection."""
    db = tmp_path / "ledger.db"
    conn = _spy_connect_and_force_failure(monkeypatch, db, failure="apply_schema")
    _assert_connection_closed(conn)


def test_connect_failure_journal_mode_closes_connection(
    tmp_path: Path, monkeypatch
) -> None:
    """A failed connect during journal-mode setup must close the connection."""
    db = tmp_path / "ledger.db"
    conn = _spy_connect_and_force_failure(
        monkeypatch, db, failure="_configure_journal_mode"
    )
    _assert_connection_closed(conn)


def test_connect_failure_unsafe_wal_closes(tmp_path: Path, monkeypatch) -> None:
    """Unsafe runtime + persistent WAL: the fail-closed downgrade path must
    close the broker's connection (spy on the real connection)."""
    db = tmp_path / "wal.db"
    prep = sqlite3.connect(str(db))
    prep.execute("PRAGMA journal_mode=WAL")
    prep.close()

    import omo.event_ledger.broker as broker_mod

    real_connect = sqlite3.connect
    captured: list[sqlite3.Connection] = []

    def spy_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)
        captured.append(conn)
        return conn

    def failing_journal(conn: sqlite3.Connection, *, allow_wal: bool) -> str:
        # Simulate the exact fail-closed condition: WAL persists after the
        # downgrade attempt, so the real code raises and connect must close.
        assert allow_wal is False
        raise LedgerError(
            "unsafe SQLite version cannot downgrade persistent WAL "
            "database; refusing to operate in WAL mode (fail closed)"
        )

    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    monkeypatch.setattr(broker_mod.sqlite3, "connect", spy_connect)
    monkeypatch.setattr(LedgerBroker, "_configure_journal_mode", failing_journal)
    with pytest.raises(LedgerError, match="fail closed"):
        LedgerBroker.connect(db)
    assert len(captured) == 1
    _assert_connection_closed(captured[0])
