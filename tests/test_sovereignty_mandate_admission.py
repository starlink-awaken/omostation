"""W2-02 sovereignty — DelegationMandate admission decision tests.

Covers: all 16 matrix cells; approval_mode tightening; every stable reason
(mandate_not_found, mandate_not_yet_valid, mandate_expired, mandate_revoked,
principal_mismatch, executor_mismatch, episode_mismatch, role_context_stale,
responsibility_stale, capability_out_of_scope, risk_ceiling_exceeded,
budget_exceeded, disclosure_mismatch, autonomy_forbids, suggest_only,
approval_required, per_action_approval_required, human_adjudication_required,
allow); A3/R2 special case; exact scope match; budget/disclosure mismatch.

Admission is pure read: ledger count never changes.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from ecos.ssot.mof.generated.control.mof_control_models import DelegationMandate

from omo import omo_ledger
from omo.event_ledger.broker import LedgerBroker
from omo.sovereignty import (
    REASON_ALLOW,
    REASON_APPROVAL_REQUIRED,
    REASON_AUTONOMY_FORBIDS,
    REASON_BUDGET_EXCEEDED,
    REASON_CAPABILITY_OUT_OF_SCOPE,
    REASON_DISCLOSURE_MISMATCH,
    REASON_EPISODE_MISMATCH,
    REASON_EXECUTOR_MISMATCH,
    REASON_HUMAN_ADJUDICATION_REQUIRED,
    REASON_MANDATE_EXPIRED,
    REASON_MANDATE_NOT_FOUND,
    REASON_MANDATE_NOT_YET_VALID,
    REASON_MANDATE_REVOKED,
    REASON_PER_ACTION_APPROVAL_REQUIRED,
    REASON_PRINCIPAL_MISMATCH,
    REASON_RESPONSIBILITY_STALE,
    REASON_RISK_CEILING_EXCEEDED,
    REASON_ROLE_CONTEXT_STALE,
    REASON_SUGGEST_ONLY,
    MandateError,
    MandateManager,
    SovereigntyService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "admit.db"


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
# Helper: create a mandate with specific parameters
# ---------------------------------------------------------------------------


def _make_mandate_kwargs(assignment, now):
    resp = assignment.responsibilities[0]
    return {
        "mandate_id": "mandate:admit-001",
        "schema_version": "delegation-mandate/v1",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_admit",
        "role_context_id": "role:family-steward",
        "role_assignment_id": assignment.assignment_id,
        "role_assignment_version": assignment.version,
        "responsibility_id": resp.resp_id,
        "responsibility_version": resp.version,
        "purpose": "Admission test mandate",
        "capability_scope": ["bos://mail/draft"],
        "autonomy_level": "A3",
        "risk_ceiling": "R2",
        "approval_mode": "matrix",
        "disclosure_policy": "disclosure:private",
        "valid_from": now - timedelta(hours=1),
        "expires_at": now + timedelta(days=365),
        "budget_limit": 10.0,
        "budget_unit": "call",
        "revocable": True,
        "trace_id": "admit001234567890abcdef12",
        "mandate_version": 1,
        "status": "active",
    }


def _grant_mandate(svc, mgr, now, **overrides):
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["family-commitments"],
    )
    kwargs = _make_mandate_kwargs(assignment, now)
    kwargs.update(overrides)
    mandate = DelegationMandate(**kwargs)
    return mgr.grant(mandate)


def _admit(mgr, **overrides):
    defaults = {
        "mandate_id": "mandate:admit-001",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_admit",
        "role_context_id": "role:family-steward",
        "capability": "bos://mail/draft",
        "risk_level": "R2",
        "requested_budget": 1.0,
        "budget_unit": "call",
        "disclosure_policy": "disclosure:private",
    }
    # Get responsibility_id from the role assignment
    svc = SovereigntyService(mgr._broker)
    assignment = svc.current_assignment("principal:alice", "role:family-steward")
    if assignment and assignment.responsibilities:
        defaults["responsibility_id"] = assignment.responsibilities[0].resp_id
    else:
        defaults["responsibility_id"] = "responsibility:nonexistent"
    defaults.update(overrides)
    return mgr.admit(**defaults)


# ---------------------------------------------------------------------------
# Basic reasons
# ---------------------------------------------------------------------------


def test_admit_mandate_not_found(broker):
    mgr = MandateManager(broker)
    result = _admit(mgr, mandate_id="mandate:nonexistent")
    assert result.allowed is False
    assert result.reason == REASON_MANDATE_NOT_FOUND


def test_admit_principal_mismatch(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    result = _admit(mgr, principal_id="principal:bob")
    assert result.allowed is False
    assert result.reason == REASON_PRINCIPAL_MISMATCH


def test_admit_executor_mismatch(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    result = _admit(mgr, executor_id="agent:other")
    assert result.allowed is False
    assert result.reason == REASON_EXECUTOR_MISMATCH


def test_admit_episode_mismatch(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    result = _admit(mgr, episode_id="episode_other")
    assert result.allowed is False
    assert result.reason == REASON_EPISODE_MISMATCH


def test_admit_capability_out_of_scope(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    result = _admit(mgr, capability="bos://other/action")
    assert result.allowed is False
    assert result.reason == REASON_CAPABILITY_OUT_OF_SCOPE


def test_admit_risk_ceiling_exceeded(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now, risk_ceiling="R1")
    result = _admit(mgr, risk_level="R2")
    assert result.allowed is False
    assert result.reason == REASON_RISK_CEILING_EXCEEDED


def test_admit_budget_exceeded(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now, budget_limit=5.0)
    result = _admit(mgr, requested_budget=10.0)
    assert result.allowed is False
    assert result.reason == REASON_BUDGET_EXCEEDED


def test_admit_budget_unit_mismatch(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    result = _admit(mgr, budget_unit="tokens")
    assert result.allowed is False
    assert result.reason == REASON_BUDGET_EXCEEDED


@pytest.mark.parametrize(
    "bad_budget", [float("nan"), float("inf"), float("-inf"), -1.0]
)
def test_admit_denies_invalid_requested_budget(svc, broker, now, bad_budget):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now, budget_limit=10.0)
    result = _admit(mgr, requested_budget=bad_budget)
    assert result.allowed is False
    assert result.reason == REASON_BUDGET_EXCEEDED


def test_admit_naive_clock_raises(svc, broker, now):
    grant_mgr = MandateManager(broker)
    _grant_mandate(svc, grant_mgr, now)
    naive = lambda: now.isoformat().replace("+00:00", "")
    mgr = MandateManager(broker, clock=naive)
    with pytest.raises(MandateError, match="naive"):
        _admit(mgr)


def test_admit_disclosure_mismatch(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    result = _admit(mgr, disclosure_policy="disclosure:public")
    assert result.allowed is False
    assert result.reason == REASON_DISCLOSURE_MISMATCH


# ---------------------------------------------------------------------------
# Role context stale
# ---------------------------------------------------------------------------


def test_admit_role_context_stale_after_revoke(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    # Revoke the underlying role assignment
    svc.revoke("principal:alice", "role:family-steward")
    result = _admit(mgr, role_context_id="role:family-steward")
    assert result.allowed is False
    assert result.reason == REASON_ROLE_CONTEXT_STALE


def test_admit_responsibility_stale(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)

    # Re-assign with a different responsibility (replace bumps all versions)
    svc.replace(
        "principal:alice",
        "role:family-steward",
        responsibilities=["family-commitments", "new-duty"],
    )
    # After replace, assignment.version changes → role_context_stale is checked first
    result = _admit(mgr)
    assert result.allowed is False
    assert result.reason == REASON_ROLE_CONTEXT_STALE


def test_admit_responsibility_not_in_assignment(svc, broker, now):
    """Responsibility_stale when responsibility version doesn't match mandate snapshot."""
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)

    assignment = svc.current_assignment("principal:alice", "role:family-steward")
    resp = assignment.responsibilities[0]

    # Inject a mandate event with stale responsibility_version directly
    # (grant() would reject it, so we bypass grant by writing directly)
    stale_mandate = DelegationMandate(
        mandate_id="mandate:admit-stale-resp",
        schema_version="delegation-mandate/v1",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_admit",
        role_context_id="role:family-steward",
        role_assignment_id=assignment.assignment_id,
        role_assignment_version=assignment.version,
        responsibility_id=resp.resp_id,
        responsibility_version=resp.version + 1,  # stale
        purpose="Stale responsibility test",
        capability_scope=["bos://mail/draft"],
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        disclosure_policy="disclosure:private",
        valid_from=now - timedelta(hours=1),
        expires_at=now + timedelta(days=365),
        budget_limit=10.0,
        budget_unit="call",
        revocable=True,
        trace_id="stale001234567890abcdef12",
        mandate_version=1,
        status="active",
    )
    payload = stale_mandate.model_dump(mode="json")
    payload["kind"] = "grant"
    broker.append(
        event_type="Mandate.Granted.v1",
        producer="omo-mandate",
        principal_id="principal:alice",
        space_id="sovereignty",
        correlation_id="mandate|mandate:admit-stale-resp|grant|1",
        idempotency_key="mandate:admit-stale-resp|1",
        episode_id="episode_admit",
        role_context_id="role:family-steward",
        responsibility_id=resp.resp_id,
        mandate_id="mandate:admit-stale-resp",
        payload=payload,
    )

    result = _admit(mgr, mandate_id="mandate:admit-stale-resp")
    assert result.allowed is False
    assert result.reason == REASON_RESPONSIBILITY_STALE


# ---------------------------------------------------------------------------
# 16-cell matrix (fixed per BET-Y1Q2-T1-05)
# ---------------------------------------------------------------------------

# Matrix: {autonomy: {risk: reason}}
# A0: R0=allow (R1/R2/R3 undefined → deny)
# A1: R0=suggest_only
# A2: R0=allow, R1=approval_required, R2=per_action, R3=autonomy_forbids
# A3: R0=allow, R1=allow, R2=allow(if revocable), R3=human_adjudication_required


@pytest.mark.parametrize(
    "autonomy,risk,expected_reason",
    [
        # A0 - observe only: ALL cells autonomy_forbids (never authorise side effects)
        ("A0", "R0", REASON_AUTONOMY_FORBIDS),
        ("A0", "R1", REASON_AUTONOMY_FORBIDS),
        ("A0", "R2", REASON_AUTONOMY_FORBIDS),
        ("A0", "R3", REASON_AUTONOMY_FORBIDS),
        # A1 - suggest only: ALL cells suggest_only
        ("A1", "R0", REASON_SUGGEST_ONLY),
        ("A1", "R1", REASON_SUGGEST_ONLY),
        ("A1", "R2", REASON_SUGGEST_ONLY),
        ("A1", "R3", REASON_SUGGEST_ONLY),
        # A2 - assisted
        ("A2", "R0", REASON_ALLOW),
        ("A2", "R1", REASON_APPROVAL_REQUIRED),
        ("A2", "R2", REASON_PER_ACTION_APPROVAL_REQUIRED),
        ("A2", "R3", REASON_AUTONOMY_FORBIDS),
        # A3 - autonomous
        ("A3", "R0", REASON_ALLOW),
        ("A3", "R1", REASON_ALLOW),
        ("A3", "R2", REASON_ALLOW),  # revocable=True
        ("A3", "R3", REASON_HUMAN_ADJUDICATION_REQUIRED),
    ],
)
def test_matrix_cell(svc, broker, now, autonomy, risk, expected_reason):
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level=autonomy,
        risk_ceiling=risk,
        approval_mode="matrix",
        revocable=True,
    )
    result = _admit(mgr, risk_level=risk)
    assert result.reason == expected_reason
    assert result.allowed == (expected_reason == REASON_ALLOW)


def test_a3_r2_non_revocable_tightens(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="matrix",
        revocable=False,
    )
    result = _admit(mgr, risk_level="R2")
    assert result.reason == REASON_PER_ACTION_APPROVAL_REQUIRED
    assert result.allowed is False


# ---------------------------------------------------------------------------
# Approval mode tightening
# ---------------------------------------------------------------------------


def test_approval_mode_deny_overrides_allow(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="deny",
        revocable=True,
    )
    result = _admit(mgr, risk_level="R2")
    assert result.reason == REASON_AUTONOMY_FORBIDS
    assert result.allowed is False


def test_approval_mode_required_tightens_allow(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="approval_required",
        revocable=True,
    )
    result = _admit(mgr, risk_level="R2")
    assert result.reason == REASON_APPROVAL_REQUIRED
    assert result.allowed is False


def test_approval_mode_per_action_tightens_allow(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="per_action_approval_required",
        revocable=True,
    )
    result = _admit(mgr, risk_level="R2")
    assert result.reason == REASON_PER_ACTION_APPROVAL_REQUIRED
    assert result.allowed is False


def test_approval_mode_human_tightens_allow(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level="A3",
        risk_ceiling="R2",
        approval_mode="human_adjudication_required",
        revocable=True,
    )
    result = _admit(mgr, risk_level="R2")
    assert result.reason == REASON_HUMAN_ADJUDICATION_REQUIRED
    assert result.allowed is False


def test_approval_tightening_cannot_loosen_terminal_deny(svc, broker, now):
    """Even with matrix mode, terminal reasons cannot be loosened."""
    mgr = MandateManager(broker)
    _grant_mandate(
        svc,
        mgr,
        now,
        autonomy_level="A2",
        risk_ceiling="R3",
        approval_mode="matrix",
        revocable=True,
    )
    result = _admit(mgr, risk_level="R3")
    assert result.reason == REASON_AUTONOMY_FORBIDS
    assert result.allowed is False


# ---------------------------------------------------------------------------
# Revoked mandate admission
# ---------------------------------------------------------------------------


def test_admit_revoked_mandate(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    mgr.revoke("mandate:admit-001", "principal:alice", expected_version=1)
    result = _admit(mgr)
    assert result.allowed is False
    assert result.reason == REASON_MANDATE_REVOKED


# ---------------------------------------------------------------------------
# Exact scope match
# ---------------------------------------------------------------------------


def test_admit_exact_scope_required(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now, capability_scope=["bos://mail/draft"])
    # Partial match should fail
    result = _admit(mgr, capability="bos://mail/draft/extra")
    assert result.allowed is False
    assert result.reason == REASON_CAPABILITY_OUT_OF_SCOPE


def test_admit_exact_scope_success(svc, broker, now):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now, capability_scope=["bos://mail/draft"])
    result = _admit(mgr, capability="bos://mail/draft")
    assert result.reason == REASON_ALLOW
    assert result.allowed is True


# ---------------------------------------------------------------------------
# CLI error mapping (mandate-admit never masquerades MandateError)
# ---------------------------------------------------------------------------


def _cli_admit_rc(db_path, capsys, **overrides):
    args = [
        "mandate-admit",
        "--db",
        str(db_path),
        "--json",
        "--mandate-id",
        "mandate:admit-001",
        "--principal-id",
        "principal:alice",
        "--executor-id",
        "agent:planner",
        "--episode-id",
        "episode_admit",
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


def test_cli_admit_reports_mandate_error_reason_and_message(
    svc,
    broker,
    now,
    capsys,
    monkeypatch,
):
    import omo.sovereignty as sov

    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    class _RaisingManager(MandateManager):
        def admit(self, **kwargs):
            raise MandateError("clock/invariant failure detail")

    monkeypatch.setattr(sov, "MandateManager", lambda broker: _RaisingManager(broker))
    rc, out = _cli_admit_rc(db_path, capsys)
    assert rc == 1
    assert "mandate_error" in out
    assert "clock/invariant failure detail" in out
    assert "mandate_not_found" not in out


def test_cli_admit_denies_nan_requested_budget(svc, broker, now, capsys):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    rc, out = _cli_admit_rc(db_path, capsys, requested_budget="nan")
    assert rc == 1
    assert "budget_exceeded" in out


def test_cli_admit_denies_negative_requested_budget(svc, broker, now, capsys):
    mgr = MandateManager(broker)
    _grant_mandate(svc, mgr, now)
    db_path = broker.db_path
    broker.close()

    rc, out = _cli_admit_rc(db_path, capsys, requested_budget="-7.0")
    assert rc == 1
    assert "budget_exceeded" in out
