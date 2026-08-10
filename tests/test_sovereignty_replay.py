"""W2-01 sovereignty — replay, hash chain, CLI, and DB isolation tests.

Verifies the append-only guarantee end to end: sovereignty events written via
LedgerBroker.append are replayed per-principal on every query (including after
a fresh broker connect on the same db), the ledger hash chain stays valid,
the flat local CLI (``omo ledger sovereignty-assign`` / ``sovereignty-query``
with --principal-id/--role-id/--db/--json) behaves correctly, malformed
sovereignty rows become a stable domain failure, and the exact registered
smoke (BET-Y1Q2-T1-04 verify cmd) passes verbatim.  Local only: ``--agora``
must be rejected for these commands.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from omo.event_ledger.broker import LedgerBroker
from omo.sovereignty import PRODUCER, SovereigntyReplayError, SovereigntyService

OMO_SRC = Path(__file__).resolve().parents[1] / "src"


# ---------------------------------------------------------------------------
# Subprocess CLI helper (mirrors test_event_ledger_surface conventions)
# ---------------------------------------------------------------------------


def run_cli(tmp_path, *args, db_name="sov.db"):
    db = tmp_path / db_name
    env = dict(os.environ)
    env["PYTHONPATH"] = str(OMO_SRC)
    env["WORKSPACE_ROOT"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "omo.omo_ledger", *args, "--db", str(db)],
        capture_output=True,
        text=True,
        cwd=str(OMO_SRC.parent),
        env=env,
        timeout=60,
    )
    return proc, db


def _assign(db, principal_id, role_id, **extra):
    argv = ["sovereignty-assign", "--principal-id", principal_id, "--role-id", role_id]
    for key, value in extra.items():
        argv += [f"--{key.replace('_', '-')}", value]
    return argv


# ---------------------------------------------------------------------------
# Replay across broker reconnects
# ---------------------------------------------------------------------------


def _seed_alice(db_path) -> None:
    svc = SovereigntyService.open(db_path)
    try:
        svc.assign(
            "principal:alice",
            "role:family-steward",
            role_name="Family Steward",
            scope="family",
            responsibilities=["School pickup", "Meal prep"],
        )
        svc.assign(
            "principal:alice",
            "role:career-engineer",
            role_name="Engineer",
            scope="career",
            responsibilities=["Code review"],
        )
    finally:
        svc._broker.close()


def test_replay_after_reopen_reconstructs_state(tmp_path):
    db = tmp_path / "replay.db"
    _seed_alice(db)

    fresh = SovereigntyService.open(db)
    try:
        principal = fresh.query("principal:alice")
        assert principal.count == 2
        assert principal.role_ids == ["role:career-engineer", "role:family-steward"]
        assert principal.assignments["role:family-steward"].version == 1
        assert principal.assignments["role:career-engineer"].role_scope == "career"
        # Deterministic replay reconstructs every aggregate version.
        state = fresh.versions("principal:alice")
        assert state.principal.version == 2
        assert state.roles["role:family-steward"].version == 1
        assert state.roles["role:career-engineer"].version == 1
        assert state.responsibilities["responsibility:school-pickup"].version == 1
    finally:
        fresh._broker.close()


def test_replay_preserves_replace_and_revoke_history(tmp_path):
    db = tmp_path / "lifecycle.db"
    svc = SovereigntyService.open(db)
    try:
        svc.assign(
            "principal:alice",
            "role:family-steward",
            role_name="V1",
            responsibilities=["School pickup"],
        )
        svc.replace(
            "principal:alice",
            "role:family-steward",
            role_name="V2",
            responsibilities=["School pickup", "Driving"],
        )
        svc.revoke("principal:alice", "role:family-steward")
    finally:
        svc._broker.close()

    reopened = SovereigntyService.open(db)
    try:
        principal = reopened.query("principal:alice")
        assignment = principal.assignments["role:family-steward"]
        assert assignment.status == "revoked"
        assert assignment.version == 3
        assert assignment.role_name == "V2"
        # No data loss: a revoked assignment keeps its definition/history.
        assert [r.name for r in assignment.responsibilities] == [
            "School pickup",
            "Driving",
        ]
        assert principal.count == 0
        assert principal.role_ids == []
    finally:
        reopened._broker.close()


def test_replay_filters_other_principals_out(tmp_path):
    db = tmp_path / "multi.db"
    svc = SovereigntyService.open(db)
    try:
        _seed_alice(db)
        svc.assign(
            "principal:bob",
            "role:tenant",
            role_name="Tenant",
            responsibilities=["Pay rent"],
        )
    finally:
        svc._broker.close()

    reopened = SovereigntyService.open(db)
    try:
        assert reopened.query("principal:bob").count == 1
        assert reopened.query("principal:alice").count == 2
        assert reopened.query("principal:ghost").count == 0
    finally:
        reopened._broker.close()


# ---------------------------------------------------------------------------
# Malformed sovereignty rows → stable domain failure
# ---------------------------------------------------------------------------


def test_malformed_sovereignty_row_is_stable_domain_failure(tmp_path):
    db = tmp_path / "malformed.db"
    svc = SovereigntyService.open(db)
    try:
        _seed_alice(db)
    finally:
        svc._broker.close()

    # Inject a sovereignty-row with a malformed payload kind via the broker
    # (a perfectly valid ledger event, but not a valid sovereignty event).
    with LedgerBroker.connect(db) as broker:
        broker.append(
            event_type="Sovereignty.RoleAssigned.v1",
            producer=PRODUCER,
            principal_id="principal:alice",
            space_id="sovereignty",
            correlation_id="malformed-1",
            idempotency_key="principal:alice|role:oops|bogus|1",
            payload={"kind": "explode", "role_id": "role:oops"},
        )

    reopened = SovereigntyService.open(db)
    try:
        # Reads and writes for the affected principal fail with the stable reason.
        with pytest.raises(SovereigntyReplayError) as exc_info:
            reopened.query("principal:alice")
        assert exc_info.value.reason == "malformed_replay"
        with pytest.raises(SovereigntyReplayError):
            reopened.assign("principal:alice", "role:career-engineer")
        # Other principals are unaffected (envelope-level isolation).
        assert reopened.query("principal:bob").count == 0
    finally:
        reopened._broker.close()


def test_malformed_payload_json_is_stable_domain_failure(tmp_path):
    db = tmp_path / "badjson.db"
    _seed_alice(db)
    with LedgerBroker.connect(db) as broker:
        broker.append(
            event_type="Sovereignty.RoleAssigned.v1",
            producer=PRODUCER,
            principal_id="principal:alice",
            space_id="sovereignty",
            correlation_id="bad-json-1",
            idempotency_key="principal:alice|role:oops|badjson|1",
            payload={
                "kind": "assign",
                "role_id": "role:oops",
            },  # missing required fields
        )
    reopened = SovereigntyService.open(db)
    try:
        with pytest.raises(SovereigntyReplayError):
            reopened.query("principal:alice")
    finally:
        reopened._broker.close()


# ---------------------------------------------------------------------------
# Hash chain integrity after sovereignty writes
# ---------------------------------------------------------------------------


def test_hash_chain_valid_after_sovereignty_writes(tmp_path):
    db = tmp_path / "chain.db"
    svc = SovereigntyService.open(db)
    try:
        svc.assign("principal:alice", "role:family-steward", role_name="Family")
        svc.assign("principal:alice", "role:career-engineer", role_name="Engineer")
        svc.replace("principal:alice", "role:family-steward", role_name="Family V2")
        svc.revoke("principal:alice", "role:career-engineer")
    finally:
        svc._broker.close()

    with LedgerBroker.connect(db) as broker:
        result = broker.verify_chain()
        assert result["ok"] is True
        assert result["total"] == 4
        assert broker.count() == 4


def test_hash_chain_detects_tampering(tmp_path):
    """A forged row with a wrong hash breaks the chain — verify_chain catches it."""
    db = tmp_path / "tamper.db"
    _seed_alice(db)

    with LedgerBroker.connect(db) as broker:
        result = broker.verify_chain()
        assert result["ok"] is True
        assert result["total"] == 2
        last = broker.read()[-1]
        tail_hash = last["event_hash"]

    # Smuggle a forged row via raw INSERT (append-only trigger blocks UPDATE).
    # previous_hash links to the real tail; event_hash is garbage, so the
    # recompute in verify_chain must flag sequence 3.
    forged_id = "event_forged-tamper-0001"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            INSERT INTO event_log (
              sequence, event_id, event_type, schema_version, principal_id,
              space_id, correlation_id, producer, idempotency_key,
              occurred_at, recorded_at, privacy_class, payload_json,
              previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                3,
                forged_id,
                "Sovereignty.RoleAssigned.v1",
                "event-envelope/v1",
                "principal:alice",
                "sovereignty",
                "forged-correlation",
                "omo-sovereignty",
                "forged|tamper|1",
                "2026-01-01T00:00:00Z",
                datetime.now(timezone.utc).isoformat(),
                "internal",
                json.dumps(
                    {
                        "kind": "assign",
                        "role_id": "role:tampered",
                        "assignment_id": "assignment:forged",
                        "version": 1,
                        "prev_version": 0,
                        "principal_version": 1,
                        "role_version": 1,
                        "responsibilities": [],
                        "status": "active",
                    }
                ),
                tail_hash,
                "0" * 64,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with LedgerBroker.connect(db) as broker:
        result = broker.verify_chain()
        assert result["ok"] is False
        assert result["first_bad_sequence"] == 3


# ---------------------------------------------------------------------------
# CLI — sovereignty-assign
# ---------------------------------------------------------------------------


def test_cli_assign_creates_assignment(tmp_path):
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "Family Steward",
        "--scope",
        "family",
        "--responsibilities",
        "School pickup, Meal prep",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["ok"] is True
    assert receipt["principal_id"] == "principal:alice"
    assert receipt["role_id"] == "role:family-steward"
    assert receipt["version"] == 1
    assert receipt["status"] == "active"
    assert [r["name"] for r in receipt["responsibilities"]] == [
        "School pickup",
        "Meal prep",
    ]


def test_cli_assign_twice_without_replace_is_illegal(tmp_path):
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
    )
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--json",
    )
    assert proc.returncode == 1
    body = json.loads(proc.stdout)
    assert body["ok"] is False
    assert body["reason"] == "illegal_transition"


def test_cli_assign_replace_flag_bumps_version(tmp_path):
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V1",
    )
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V2",
        "--replace",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body["ok"] is True
    assert body["version"] == 2
    assert body["role_name"] == "V2"


def test_cli_replace_without_responsibilities_preserves_them(tmp_path):
    """The CLI replace omission must not wipe existing responsibilities."""
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V1",
        "--responsibilities",
        "School pickup, Meal prep",
    )
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V2",
        "--replace",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body["version"] == 2
    assert body["role_name"] == "V2"
    assert [r["name"] for r in body["responsibilities"]] == [
        "School pickup",
        "Meal prep",
    ]


def test_cli_assign_invalid_principal_id_rejected(tmp_path):
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "alice",
        "--role-id",
        "role:family-steward",
        "--json",
    )
    assert proc.returncode == 1
    body = json.loads(proc.stdout)
    assert body["ok"] is False
    assert body["reason"] == "invalid_id"


# ---------------------------------------------------------------------------
# CLI — --expected-version (W2-01 hardening)
# ---------------------------------------------------------------------------


def test_cli_assign_stale_expected_version_rejected(tmp_path):
    """--expected-version that does not match the replayed version is stale."""
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V1",
    )
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V2",
        "--replace",
        "--expected-version",
        "5",
        "--json",
    )
    assert proc.returncode == 1
    body = json.loads(proc.stdout)
    assert body["ok"] is False
    assert body["reason"] == "stale_version"


def test_cli_assign_matching_expected_version_ok(tmp_path):
    """A correct --expected-version lets the replace through."""
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V1",
    )
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "V2",
        "--replace",
        "--expected-version",
        "1",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body["ok"] is True
    assert body["version"] == 2


def test_cli_assign_expected_version_zero_fresh_ok(tmp_path):
    """A fresh assign expects base version 0 (backward compatible omission)."""
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--expected-version",
        "0",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["version"] == 1


def test_cli_assign_rejects_agora_flag(tmp_path):
    """Sovereignty is local-only: --agora must not be accepted."""
    proc, _ = run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--agora",
    )
    assert proc.returncode != 0
    assert "unrecognized arguments" in proc.stderr or "error" in proc.stderr.lower()


# ---------------------------------------------------------------------------
# CLI — sovereignty-query
# ---------------------------------------------------------------------------


def test_cli_query_output_shape(tmp_path):
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        "--role-name",
        "Family Steward",
    )
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:career-engineer",
        "--role-name",
        "Engineer",
    )
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:bob",
        "--role-id",
        "role:tenant",
        "--role-name",
        "Tenant",
    )
    proc, _ = run_cli(
        tmp_path, "sovereignty-query", "--principal-id", "principal:alice", "--json"
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert set(body) == {"ok", "principal_id", "count", "assignments", "role_ids"}
    assert body["ok"] is True
    assert body["principal_id"] == "principal:alice"
    assert body["count"] == 2
    assert body["role_ids"] == ["role:career-engineer", "role:family-steward"]
    assert len(body["assignments"]) == 2


def test_cli_query_unknown_principal_is_empty(tmp_path):
    proc, _ = run_cli(
        tmp_path, "sovereignty-query", "--principal-id", "principal:ghost", "--json"
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body == {
        "ok": True,
        "principal_id": "principal:ghost",
        "count": 0,
        "assignments": [],
        "role_ids": [],
    }


def test_cli_query_invalid_principal_id(tmp_path):
    proc, _ = run_cli(
        tmp_path, "sovereignty-query", "--principal-id", "ghost", "--json"
    )
    assert proc.returncode == 1
    body = json.loads(proc.stdout)
    assert body["ok"] is False
    assert body["reason"] == "invalid_id"


def test_cli_query_after_revoke(tmp_path):
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
    )
    # Revoke via the service API (same db) then verify CLI reflects it.
    db = tmp_path / "sov.db"
    svc = SovereigntyService.open(db)
    try:
        svc.revoke("principal:alice", "role:family-steward")
    finally:
        svc._broker.close()
    proc, _ = run_cli(
        tmp_path, "sovereignty-query", "--principal-id", "principal:alice", "--json"
    )
    body = json.loads(proc.stdout)
    assert body["count"] == 0
    assert body["role_ids"] == []
    assert body["assignments"][0]["status"] == "revoked"


# ---------------------------------------------------------------------------
# CLI — exact registered smoke (BET-Y1Q2-T1-04 verify cmd)
# ---------------------------------------------------------------------------


def test_registered_smoke_exact(tmp_path):
    """The registered smoke scenario, verbatim ids, 3 assigns → ledger total 3."""
    for args in (
        (
            "sovereignty-assign",
            "--principal-id",
            "principal:alice",
            "--role-id",
            "role:family-steward",
            "--json",
        ),
        (
            "sovereignty-assign",
            "--principal-id",
            "principal:alice",
            "--role-id",
            "role:professional",
            "--json",
        ),
        (
            "sovereignty-assign",
            "--principal-id",
            "principal:bob",
            "--role-id",
            "role:learner",
            "--json",
        ),
    ):
        proc, _ = run_cli(tmp_path, *args)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["ok"] is True

    proc, _ = run_cli(
        tmp_path, "sovereignty-query", "--principal-id", "principal:alice", "--json"
    )
    assert proc.returncode == 0, proc.stderr
    q = json.loads(proc.stdout)
    assert q["ok"] is True and q["count"] == 2
    assert all(a["principal_id"] == "principal:alice" for a in q["assignments"])
    assert "role:family-steward" in q["role_ids"]
    assert "role:professional" in q["role_ids"]
    assert "role:learner" not in q["role_ids"]

    proc, _ = run_cli(tmp_path, "verify", "--from", "1", "--json")
    assert proc.returncode == 0, proc.stderr
    v = json.loads(proc.stdout)
    assert v["ok"] is True and v["total"] == 3


# ---------------------------------------------------------------------------
# CLI — DB isolation and coexistence with the ledger commands
# ---------------------------------------------------------------------------


def test_cli_db_isolation(tmp_path):
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
        db_name="one.db",
    )
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:bob",
        "--role-id",
        "role:tenant",
        db_name="two.db",
    )
    proc_a, _ = run_cli(
        tmp_path,
        "sovereignty-query",
        "--principal-id",
        "principal:alice",
        "--json",
        db_name="one.db",
    )
    proc_b, _ = run_cli(
        tmp_path,
        "sovereignty-query",
        "--principal-id",
        "principal:bob",
        "--json",
        db_name="two.db",
    )
    assert json.loads(proc_a.stdout)["count"] == 1
    assert json.loads(proc_b.stdout)["count"] == 1
    # Alice does not exist in bob's db and vice versa.
    proc_a2, _ = run_cli(
        tmp_path,
        "sovereignty-query",
        "--principal-id",
        "principal:bob",
        "--json",
        db_name="one.db",
    )
    assert json.loads(proc_a2.stdout)["count"] == 0


def test_ledger_commands_see_sovereignty_events(tmp_path):
    """Sovereignty events are ordinary ledger events (verifiable, readable)."""
    run_cli(
        tmp_path,
        "sovereignty-assign",
        "--principal-id",
        "principal:alice",
        "--role-id",
        "role:family-steward",
    )
    proc_verify, _ = run_cli(tmp_path, "verify", "--json")
    assert proc_verify.returncode == 0, proc_verify.stderr
    verify = json.loads(proc_verify.stdout)
    assert verify.get("ok") is True
    assert verify.get("total", verify.get("count", 0)) == 1

    proc_read, _ = run_cli(tmp_path, "read", "--json")
    assert proc_read.returncode == 0, proc_read.stderr
    rows = json.loads(proc_read.stdout)
    events = rows if isinstance(rows, list) else rows.get("events", [])
    assert any(
        e.get("event_type") == "Sovereignty.RoleAssigned.v1"
        and e.get("principal_id") == "principal:alice"
        for e in events
    )


# ---------------------------------------------------------------------------
# In-process ledger invariants
# ---------------------------------------------------------------------------


def test_sovereignty_events_carry_expected_envelope(tmp_path):
    db = tmp_path / "env.db"
    _seed_alice(db)
    with LedgerBroker.connect(db) as broker:
        rows = broker.read(producer="omo-sovereignty")
        assert len(rows) == 2
        for row in rows:
            assert row["producer"] == "omo-sovereignty"
            assert row["space_id"] == "sovereignty"
            assert row["principal_id"] == "principal:alice"
            assert row["event_type"].startswith("Sovereignty.Role")
            payload = json.loads(row["payload_json"])
            assert payload["kind"] in ("assign", "replace", "revoke")
            assert payload["role_id"].startswith("role:")
            assert payload["principal_id"] == "principal:alice"
            assert isinstance(payload["principal_version"], int)
            assert isinstance(payload["role_version"], int)
            assert isinstance(payload["version"], int)


def test_one_event_per_mutation(tmp_path):
    """Three assigns produce exactly three ledger events (BET-Y1Q2-T1-04)."""
    db = tmp_path / "count.db"
    svc = SovereigntyService.open(db)
    try:
        svc.assign("principal:alice", "role:family-steward")
        svc.assign("principal:alice", "role:professional")
        svc.assign("principal:bob", "role:learner")
    finally:
        svc._broker.close()
    with LedgerBroker.connect(db) as broker:
        assert broker.count() == 3
