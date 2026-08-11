"""W2-02 sovereignty — DelegationMandate grant/revoke lifecycle tests.

Covers: grant creates active v1, validates W2-01 RoleAssignment, snapshots
versions, writes Mandate.Granted.v1; revoke transitions active v1 -> revoked v2,
writes Mandate.Revoked.v1; illegal transitions (double grant, revoke absent,
revoke stale version); principal isolation; envelope fields correctness.
All writes go through LedgerBroker.append via MandateManager.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from ecos.ssot.mof.generated.control.mof_control_models import DelegationMandate

from omo.event_ledger.broker import DuplicateEventError, LedgerBroker
from omo.sovereignty import (
    EVT_MANDATE_GRANT,
    EVT_MANDATE_REVOKE,
    MANDATE_PRODUCER,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    IllegalMandateTransitionError,
    MandateError,
    MandateManager,
    SovereigntyService,
    StaleMandateVersionError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "mandates.db"


@pytest.fixture()
def broker(db_path):
    b = LedgerBroker.connect(db_path)
    yield b
    b.close()


@pytest.fixture()
def svc(broker):
    yield SovereigntyService(broker)


@pytest.fixture()
def mgr(broker):
    yield MandateManager(broker)


@pytest.fixture()
def now():
    return datetime.now(timezone.utc)


@pytest.fixture()
def valid_from(now):
    return now - timedelta(hours=1)


@pytest.fixture()
def expires_at(now):
    return now + timedelta(days=365)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assign_family_steward(svc):
    return svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["family-commitments"],
    )


def _make_mandate(assignment, valid_from_dt, expires_at_dt):
    resp = assignment.responsibilities[0]
    return DelegationMandate(
        mandate_id="mandate:test-001",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_001",
        role_context_id="role:family-steward",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version,
        purpose="Test mandate",
        capability_scope=["bos://mail/draft"],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=valid_from_dt,
        expires_at=expires_at_dt,
        budget_limit=1.0,
        budget_unit="call",
        revocable=True,
        trace_id="abcdef1234567890abcdef12",
        mandate_version=1,
        status="active",
    )


# ---------------------------------------------------------------------------
# Grant tests
# ---------------------------------------------------------------------------


def test_grant_creates_active_v1_mandate(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    result = mgr.grant(mandate)
    assert result.status == STATUS_ACTIVE
    assert result.mandate_version == 1
    assert result.mandate_id == "mandate:test-001"
    assert result.trace_id


def test_grant_writes_mandate_granted_event(svc, mgr, broker, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    rows = list(broker.read(producer=MANDATE_PRODUCER))
    assert len(rows) >= 1
    grant_rows = [r for r in rows if r.get("event_type") == EVT_MANDATE_GRANT]
    assert len(grant_rows) == 1
    assert grant_rows[0]["principal_id"] == "principal:alice"
    assert grant_rows[0]["episode_id"] == "episode_001"


def test_grant_populates_envelope_fields(svc, mgr, broker, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    rows = list(broker.read(producer=MANDATE_PRODUCER))
    grant_row = next(r for r in rows if r["event_type"] == EVT_MANDATE_GRANT)
    assert grant_row["principal_id"] == "principal:alice"
    assert grant_row["episode_id"] == "episode_001"
    assert grant_row["role_context_id"] == "role:family-steward"
    assert grant_row["responsibility_id"]
    assert grant_row["mandate_id"] == "mandate:test-001"


def test_grant_requires_active_role_assignment(mgr, valid_from, expires_at):
    assignment = _assign_family_steward(SovereigntyService(mgr._broker))
    # Revoke the role
    svc = SovereigntyService(mgr._broker)
    svc.revoke("principal:alice", "role:family-steward")

    mandate = _make_mandate(assignment, valid_from, expires_at)
    with pytest.raises(MandateError):
        mgr.grant(mandate)


def test_grant_requires_role_context_match(mgr, valid_from, expires_at):
    # Assign role:professional to alice
    svc = SovereigntyService(mgr._broker)
    svc.assign(
        "principal:alice", "role:professional", responsibilities=["professional-duty"]
    )

    # Try to grant with role:family-steward context
    assignment = svc.current_assignment("principal:alice", "role:professional")
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(
        update={
            "role_context_id": "role:family-steward",
            "responsibility_id": "responsibility:professional-duty",
        }
    )
    # role_context_id mismatch with current_assignment call
    # This should fail because role:family-steward is not active
    with pytest.raises(MandateError):
        mgr.grant(mandate)


def test_double_grant_rejected(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)
    with pytest.raises(IllegalMandateTransitionError):
        mgr.grant(mandate)


def test_grant_snapshots_role_versions(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    result = mgr.grant(mandate)
    assert result.role_assignment_version == assignment.version
    resp = assignment.responsibilities[0]
    assert result.responsibility_version == resp.version


# ---------------------------------------------------------------------------
# Revoke tests
# ---------------------------------------------------------------------------


def test_revoke_transitions_active_to_revoked(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    revoked = mgr.revoke("mandate:test-001", "principal:alice", expected_version=1)
    assert revoked.status == STATUS_REVOKED
    assert revoked.mandate_version == 2


def test_revoke_writes_mandate_revoked_event(svc, mgr, broker, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)
    mgr.revoke("mandate:test-001", "principal:alice", expected_version=1)

    rows = list(broker.read(producer=MANDATE_PRODUCER))
    revoked_rows = [r for r in rows if r["event_type"] == EVT_MANDATE_REVOKE]
    assert len(revoked_rows) == 1
    row = revoked_rows[0]
    assert row["principal_id"] == "principal:alice"
    assert row["episode_id"] == "episode_001"
    assert row["role_context_id"] == "role:family-steward"
    assert row["responsibility_id"] == assignment.responsibilities[0].resp_id
    assert row["mandate_id"] == "mandate:test-001"
    payload = json.loads(row["payload_json"])
    assert payload["kind"] == "revoke"
    assert payload["prev_version"] == 1


def test_revoke_absent_mandate_fails(mgr):
    with pytest.raises(IllegalMandateTransitionError):
        mgr.revoke("mandate:nonexistent", "principal:alice", expected_version=1)


def test_revoke_already_revoked_fails(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)
    mgr.revoke("mandate:test-001", "principal:alice", expected_version=1)
    with pytest.raises(IllegalMandateTransitionError):
        mgr.revoke("mandate:test-001", "principal:alice", expected_version=1)


def test_revoke_stale_expected_version_fails(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)
    with pytest.raises(StaleMandateVersionError):
        mgr.revoke("mandate:test-001", "principal:alice", expected_version=0)


def test_revoke_requires_correct_principal(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)
    with pytest.raises(IllegalMandateTransitionError):
        mgr.revoke("mandate:test-001", "principal:bob", expected_version=1)


def test_revoke_rejects_empty_trace_id(svc, mgr, broker, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    rows_before = list(broker.read(producer=MANDATE_PRODUCER))
    with pytest.raises(MandateError, match="invalid revoke payload"):
        mgr.revoke(
            "mandate:test-001", "principal:alice", expected_version=1, trace_id=""
        )
    rows_after = list(broker.read(producer=MANDATE_PRODUCER))
    assert len(rows_after) == len(rows_before)
    assert broker.verify_chain()["ok"] is True


def test_revoke_rejects_malformed_trace_id(svc, mgr, broker, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    rows_before = list(broker.read(producer=MANDATE_PRODUCER))
    with pytest.raises(MandateError, match="invalid revoke payload"):
        mgr.revoke(
            "mandate:test-001", "principal:alice", expected_version=1, trace_id="!!!"
        )
    rows_after = list(broker.read(producer=MANDATE_PRODUCER))
    assert len(rows_after) == len(rows_before)


def test_revoke_uses_supplied_trace_id(svc, mgr, broker, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    supplied = "supplied-trace-000001"
    revoked = mgr.revoke(
        "mandate:test-001", "principal:alice", expected_version=1, trace_id=supplied
    )
    assert revoked.trace_id == supplied
    rows = list(broker.read(producer=MANDATE_PRODUCER))
    revoked_row = next(r for r in rows if r["event_type"] == EVT_MANDATE_REVOKE)
    payload = json.loads(revoked_row["payload_json"])
    assert payload["trace_id"] == supplied


# ---------------------------------------------------------------------------
# Duplicate idempotency
# ---------------------------------------------------------------------------


def test_concurrent_duplicate_grant_uses_idempotency_backstop(
    svc,
    mgr,
    broker,
    valid_from,
    expires_at,
    monkeypatch,
):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    other_broker = LedgerBroker.connect(broker.db_path)
    other_mgr = MandateManager(other_broker)
    gate = Barrier(2)

    for manager in (mgr, other_mgr):
        original_replay = manager._replay_all

        def synced_replay(original_replay=original_replay):
            state = original_replay()
            gate.wait(timeout=5)
            return state

        monkeypatch.setattr(manager, "_replay_all", synced_replay)

    def attempt(manager, trace_id):
        candidate = mandate.model_copy(update={"trace_id": trace_id})
        try:
            manager.grant(candidate)
        except DuplicateEventError:
            return "duplicate"
        return "granted"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [
                pool.submit(attempt, mgr, "race-trace-000001"),
                pool.submit(attempt, other_mgr, "race-trace-000002"),
            ]
            assert sorted(future.result() for future in outcomes) == [
                "duplicate",
                "granted",
            ]
        rows = list(broker.read(producer=MANDATE_PRODUCER))
        assert [row["event_type"] for row in rows] == [EVT_MANDATE_GRANT]
        assert broker.verify_chain()["ok"] is True
    finally:
        other_broker.close()


# ---------------------------------------------------------------------------
# Principal isolation
# ---------------------------------------------------------------------------


def test_bob_cannot_see_alice_mandates(svc, mgr, valid_from, expires_at):
    # Assign alice and grant
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mgr.grant(mandate)

    # Bob's query should be empty
    bob_state = mgr.query("principal:bob")
    assert len(bob_state.mandates) == 0

    # Alice's query should see it
    alice_state = mgr.query("principal:alice")
    assert "mandate:test-001" in alice_state.mandates


# ---------------------------------------------------------------------------
# Revocable enforcement
# ---------------------------------------------------------------------------


def test_revoke_non_revocable_mandate_fails(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"revocable": False})
    mgr.grant(mandate)
    with pytest.raises(IllegalMandateTransitionError):
        mgr.revoke("mandate:test-001", "principal:alice", expected_version=1)


# ---------------------------------------------------------------------------
# Local invariants
# ---------------------------------------------------------------------------


def test_grant_rejects_wildcard_capability_scope(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"capability_scope": ["bos://mail/*"]})
    with pytest.raises(MandateError, match="wildcard"):
        mgr.grant(mandate)


def test_grant_rejects_empty_capability_scope(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"capability_scope": []})
    with pytest.raises(MandateError, match="capability_scope"):
        mgr.grant(mandate)


def test_grant_rejects_negative_budget(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"budget_limit": -1.0})
    with pytest.raises(MandateError, match="budget_limit"):
        mgr.grant(mandate)


def test_grant_rejects_nan_budget_limit(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"budget_limit": float("nan")})
    with pytest.raises(MandateError, match="budget_limit"):
        mgr.grant(mandate)


def test_grant_rejects_infinite_budget_limit(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"budget_limit": float("inf")})
    with pytest.raises(MandateError, match="budget_limit"):
        mgr.grant(mandate)


def test_grant_rejects_empty_purpose(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"purpose": ""})
    with pytest.raises(MandateError, match="purpose"):
        mgr.grant(mandate)


def test_grant_rejects_invalid_validity_order(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(
        update={"valid_from": expires_at, "expires_at": valid_from}
    )
    with pytest.raises(MandateError, match="valid_from"):
        mgr.grant(mandate)


def test_grant_rejects_invalid_versions(svc, mgr, valid_from, expires_at):
    assignment = _assign_family_steward(svc)
    mandate = _make_mandate(assignment, valid_from, expires_at)
    mandate = mandate.model_copy(update={"role_assignment_version": 0})
    with pytest.raises(MandateError, match="role_assignment_version"):
        mgr.grant(mandate)
