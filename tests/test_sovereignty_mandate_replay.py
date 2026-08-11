"""W2-02 sovereignty — DelegationMandate deterministic replay tests.

Covers: replay reconstructs mandates from events; principal isolation;
malformed events raise MandateReplayError; state reconstruction after
fresh service; injected-clock not-yet-valid and expired; ledger count
unchanged after admission (read-only).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from ecos.ssot.mof.generated.control.mof_control_models import DelegationMandate

from omo import omo_ledger
from omo.event_ledger.broker import LedgerBroker
from omo.sovereignty import (
    EVT_MANDATE_GRANT,
    MANDATE_PRODUCER,
    MandateError,
    MandateManager,
    MandateReplayError,
    SovereigntyService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "replay.db"


@pytest.fixture()
def broker(db_path):
    b = LedgerBroker.connect(db_path)
    yield b
    b.close()


@pytest.fixture()
def svc(broker):
    yield SovereigntyService(broker)


@pytest.fixture()
def now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_mandate(svc, mgr, now, cap="bos://mail/draft"):
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["family-commitments"],
    )
    resp = assignment.responsibilities[0]
    mandate = DelegationMandate(
        mandate_id="mandate:replay-001",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_replay",
        role_context_id="role:family-steward",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version,
        purpose="Replay test",
        capability_scope=[cap],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=now - timedelta(hours=1),
        expires_at=now + timedelta(days=365),
        budget_limit=10.0,
        budget_unit="call",
        revocable=True,
        trace_id="replay1234567890abcdef12",
        mandate_version=1,
        status="active",
    )
    return mgr.grant(mandate)


def _grant_payload(mandate):
    payload = dict(mandate)
    payload["kind"] = "grant"
    return payload


def _append_grant_row(broker, mandate, idempotency_key):
    broker.append(
        event_type=EVT_MANDATE_GRANT,
        producer=MANDATE_PRODUCER,
        principal_id=mandate["principal_id"],
        space_id="sovereignty",
        correlation_id=f"malicious-{idempotency_key}",
        idempotency_key=idempotency_key,
        episode_id=mandate["episode_id"],
        role_context_id=mandate["role_context_id"],
        responsibility_id=mandate["responsibility_id"],
        mandate_id=mandate["mandate_id"],
        payload=_grant_payload(mandate),
    )


# ---------------------------------------------------------------------------
# Replay tests
# ---------------------------------------------------------------------------


def test_query_returns_mandate_state(svc, broker, now):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    state = mgr.query("principal:alice")
    assert "mandate:replay-001" in state.mandates
    m = state.mandates["mandate:replay-001"]
    assert m.status == "active"
    assert m.mandate_version == 1


def test_query_empty_for_new_principal(svc, broker, now):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    state = mgr.query("principal:bob")
    assert len(state.mandates) == 0


def test_get_returns_mandate_or_none(svc, broker, now):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    assert mgr.get("mandate:replay-001", "principal:alice") is not None
    assert mgr.get("mandate:nonexistent", "principal:alice") is None


def test_state_reconstructed_after_fresh_service(svc, broker, now):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    # Fresh broker connection
    fresh_broker = LedgerBroker.connect(db_path)
    fresh_mgr = MandateManager(fresh_broker)
    try:
        state = fresh_mgr.query("principal:alice")
        assert "mandate:replay-001" in state.mandates
        m = state.mandates["mandate:replay-001"]
        assert m.status == "active"
        assert m.mandate_version == 1
    finally:
        fresh_broker.close()


def test_malformed_event_raises_replay_error(broker, now):
    mgr = MandateManager(broker)
    svc = SovereigntyService(broker)
    _setup_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    # Inject a malformed event directly
    fresh_broker = LedgerBroker.connect(db_path)
    fresh_broker.append(
        event_type=EVT_MANDATE_GRANT,
        producer=MANDATE_PRODUCER,
        principal_id="principal:alice",
        space_id="sovereignty",
        correlation_id="malformed-test",
        idempotency_key="malformed-1",
        episode_id="episode_replay",
        role_context_id="role:family-steward",
        responsibility_id="responsibility:family-commitments",
        mandate_id="mandate:malformed",
        payload={
            "kind": "grant",
            "mandate_id": "mandate:malformed",
            "principal_id": "principal:alice",
            "episode_id": "episode_replay",
            "role_context_id": "role:family-steward",
            "responsibility_id": "responsibility:family-commitments",
        },
    )
    fresh_broker.close()

    # Re-open and replay - should raise
    check_broker = LedgerBroker.connect(db_path)
    check_mgr = MandateManager(check_broker)
    try:
        with pytest.raises(MandateReplayError):
            check_mgr.query("principal:alice")
    finally:
        check_broker.close()


def test_replay_rejects_wildcard_capability_grant_row(svc, broker, now):
    """A Pydantic-valid grant row with a wildcard capability must fail replay."""
    mgr = MandateManager(broker)
    granted = _setup_mandate(svc, mgr, now)
    bad = granted.model_dump(mode="json")
    bad["capability_scope"] = ["bos://mail/*"]
    bad["mandate_id"] = "mandate:wildcard"
    _append_grant_row(broker, bad, "wildcard-1")

    with pytest.raises(MandateReplayError, match="wildcard"):
        mgr.query("principal:alice")


def test_replay_rejects_negative_budget_grant_row(svc, broker, now):
    """A Pydantic-valid grant row with a negative budget must fail replay."""
    mgr = MandateManager(broker)
    granted = _setup_mandate(svc, mgr, now)
    bad = granted.model_dump(mode="json")
    bad["budget_limit"] = -1.0
    bad["mandate_id"] = "mandate:neg-budget"
    _append_grant_row(broker, bad, "neg-budget-1")

    with pytest.raises(MandateReplayError, match="budget_limit"):
        mgr.query("principal:alice")


def test_replay_rejects_executor_mutation_on_revoke(svc, broker, now):
    """Any immutable generated field mutated on a v2 revoke must fail replay."""
    mgr = MandateManager(broker)
    granted = _setup_mandate(svc, mgr, now)
    revoked_payload = granted.model_dump(mode="json")
    revoked_payload.update(
        {
            "status": "revoked",
            "mandate_version": 2,
            "executor_id": "agent:intruder",
            "kind": "revoke",
            "prev_version": 1,
        }
    )
    broker.append(
        event_type="Mandate.Revoked.v1",
        producer=MANDATE_PRODUCER,
        principal_id="principal:alice",
        space_id="sovereignty",
        correlation_id="mutate-executor",
        idempotency_key="mutate-executor-1",
        episode_id="episode_replay",
        role_context_id="role:family-steward",
        responsibility_id=revoked_payload["responsibility_id"],
        mandate_id="mandate:replay-001",
        payload=revoked_payload,
    )

    with pytest.raises(MandateReplayError, match="executor_id"):
        mgr.query("principal:alice")


def test_grant_rejects_naive_clock(svc, broker, now):
    """A naive (non-tz-aware) clock must raise MandateError and not append."""
    mgr = MandateManager(broker, clock=lambda: now.isoformat().replace("+00:00", ""))
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        responsibilities=["family-commitments"],
    )
    resp = assignment.responsibilities[0]
    mandate = DelegationMandate(
        mandate_id="mandate:naive-clock",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_replay",
        role_context_id="role:family-steward",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version,
        purpose="Naive clock test",
        capability_scope=["bos://mail/draft"],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=now - timedelta(hours=1),
        expires_at=now + timedelta(days=365),
        budget_limit=1.0,
        budget_unit="call",
        revocable=True,
        trace_id="naive001234567890abcdef12",
        mandate_version=1,
        status="active",
    )
    with pytest.raises(MandateError, match="naive"):
        mgr.grant(mandate)
    assert len(list(broker.read(producer=MANDATE_PRODUCER))) == 0


def test_grant_rejects_malformed_clock(svc, broker, now):
    """A malformed clock must raise MandateError and not append."""
    mgr = MandateManager(broker, clock=lambda: "not-a-datetime")
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        responsibilities=["family-commitments"],
    )
    resp = assignment.responsibilities[0]
    mandate = DelegationMandate(
        mandate_id="mandate:bad-clock",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_replay",
        role_context_id="role:family-steward",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version,
        purpose="Bad clock test",
        capability_scope=["bos://mail/draft"],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=now - timedelta(hours=1),
        expires_at=now + timedelta(days=365),
        budget_limit=1.0,
        budget_unit="call",
        revocable=True,
        trace_id="badclock001234567890ab",
        mandate_version=1,
        status="active",
    )
    with pytest.raises(MandateError, match="clock"):
        mgr.grant(mandate)
    assert len(list(broker.read(producer=MANDATE_PRODUCER))) == 0


def test_grant_uses_validated_clock_for_occurred_at(svc, broker, now):
    """occurred_at must be the validated tz-aware clock value."""
    fixed = "2026-01-01T00:00:00+00:00"
    mgr = MandateManager(broker, clock=lambda: fixed)
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        responsibilities=["family-commitments"],
    )
    resp = assignment.responsibilities[0]
    mandate = DelegationMandate(
        mandate_id="mandate:fixed-clock",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_replay",
        role_context_id="role:family-steward",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version,
        purpose="Fixed clock test",
        capability_scope=["bos://mail/draft"],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
        expires_at=datetime.fromisoformat("2027-01-01T00:00:00+00:00"),
        budget_limit=1.0,
        budget_unit="call",
        revocable=True,
        trace_id="fixed001234567890abcdef12",
        mandate_version=1,
        status="active",
    )
    mgr.grant(mandate)
    rows = list(broker.read(producer=MANDATE_PRODUCER))
    assert rows[0]["occurred_at"] == fixed


def test_injected_clock_not_yet_valid(svc, broker, now):
    """Mandate valid_from is in the future relative to the injected clock."""
    clock_future = lambda: (now - timedelta(hours=2)).isoformat()
    mgr = MandateManager(broker, clock=clock_future)

    assignment = svc.assign(
        "principal:alice",
        "role:future",
        responsibilities=["future-duty"],
    )
    resp = assignment.responsibilities[0]
    mandate = DelegationMandate(
        mandate_id="mandate:future-001",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_future",
        role_context_id="role:future",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version,
        purpose="Future mandate",
        capability_scope=["bos://mail/draft"],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=now + timedelta(days=1),
        expires_at=now + timedelta(days=365),
        budget_limit=1.0,
        budget_unit="call",
        revocable=True,
        trace_id="future0123456789abcdef12",
        mandate_version=1,
        status="active",
    )
    mgr.grant(mandate)
    result = mgr.admit(
        "mandate:future-001",
        "principal:alice",
        "agent:planner",
        "episode_future",
        "role:future",
        resp.resp_id,
        "bos://mail/draft",
        "R2",
        1.0,
        "call",
        "disclosure:private",
    )
    assert result.reason == "mandate_not_yet_valid"
    assert not result.allowed


def test_injected_clock_expired(svc, broker, now):
    """Mandate expired via injected clock advancement."""
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)

    clock_advanced = lambda: (now + timedelta(days=400)).isoformat()
    mgr2 = MandateManager(broker, clock=clock_advanced)
    assignment = svc.current_assignment("principal:alice", "role:family-steward")
    resp = assignment.responsibilities[0]
    result = mgr2.admit(
        "mandate:replay-001",
        "principal:alice",
        "agent:planner",
        "episode_replay",
        "role:family-steward",
        resp.resp_id,
        "bos://mail/draft",
        "R2",
        1.0,
        "call",
        "disclosure:private",
    )
    assert result.reason == "mandate_expired"
    assert not result.allowed


def test_ledger_count_unchanged_after_admission(svc, broker, now):
    """Admission is pure read: ledger event count does not change."""
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)

    rows_before = list(broker.read(producer=MANDATE_PRODUCER))
    count_before = len(rows_before)

    assignment = svc.current_assignment("principal:alice", "role:family-steward")
    resp = assignment.responsibilities[0]
    mgr.admit(
        "mandate:replay-001",
        "principal:alice",
        "agent:planner",
        "episode_replay",
        "role:family-steward",
        resp.resp_id,
        "bos://mail/draft",
        "R2",
        1.0,
        "call",
        "disclosure:private",
    )
    mgr.admit(
        "mandate:nonexistent",
        "principal:alice",
        "agent:planner",
        "episode_replay",
        "role:family-steward",
        resp.resp_id,
        "bos://mail/draft",
        "R2",
        1.0,
        "call",
        "disclosure:private",
    )

    rows_after = list(broker.read(producer=MANDATE_PRODUCER))
    assert len(rows_after) == count_before


# ---------------------------------------------------------------------------
# CLI-path regressions (mandate-admit maps errors to stable reasons)
# ---------------------------------------------------------------------------


def _cli_admit(db_path, capsys, **overrides):
    args = [
        "mandate-admit",
        "--db",
        str(db_path),
        "--json",
        "--mandate-id",
        "mandate:replay-001",
        "--principal-id",
        "principal:alice",
        "--executor-id",
        "agent:planner",
        "--episode-id",
        "episode_replay",
        "--role-context-id",
        "role:family-steward",
        "--responsibility-id",
        "responsibility:family-commitments",
        "--capability",
        "bos://mail/draft",
        "--risk-level",
        "R2",
        "--requested-budget",
        "1.0",
        "--budget-unit",
        "call",
        "--disclosure-policy",
        "disclosure:private",
    ]
    for flag, value in overrides.items():
        args += ["--" + flag.replace("_", "-"), str(value)]
    rc = omo_ledger.main(args)
    out = capsys.readouterr().out
    return rc, out


def test_cli_admit_maps_corrupted_ledger_to_replay_error(
    svc,
    broker,
    now,
    capsys,
):
    mgr = MandateManager(broker)
    granted = _setup_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    corrupt_broker = LedgerBroker.connect(db_path)
    bad = granted.model_dump(mode="json")
    bad["capability_scope"] = ["bos://mail/*"]
    bad["mandate_id"] = "mandate:cli-wildcard"
    _append_grant_row(corrupt_broker, bad, "cli-wildcard-1")
    corrupt_broker.close()

    rc, out = _cli_admit(db_path, capsys)
    assert rc == 1
    assert "malformed_mandate_replay" in out


def test_cli_admit_denies_negative_budget(svc, broker, now, capsys):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    rc, out = _cli_admit(db_path, capsys, requested_budget="-5.0")
    assert rc == 1
    assert "budget_exceeded" in out


def test_cli_admit_denies_nan_budget(svc, broker, now, capsys):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    rc, out = _cli_admit(db_path, capsys, requested_budget="nan")
    assert rc == 1
    assert "budget_exceeded" in out


def test_cli_admit_denies_infinite_budget(svc, broker, now, capsys):
    mgr = MandateManager(broker)
    _setup_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    rc, out = _cli_admit(db_path, capsys, requested_budget="inf")
    assert rc == 1
    assert "budget_exceeded" in out
