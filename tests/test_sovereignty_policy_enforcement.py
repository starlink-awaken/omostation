"""W2-03 sovereignty — PDP/Ledger single-user enforcement unit tests.

Covers: allow/deny decisions; no-mandate and admission denials map to the
stable ``policy_denied`` reason; durable PolicyDecision append; idempotency
(same action+hash reuses prior state, different hash rejected); PDP and
decision/started/terminal ledger failures are fail-closed with 0 or 1
provider calls and stable reasons (pdp_unavailable, ledger_unavailable,
provider_failed, receipt_unconfirmed); the AgoraPepProvider narrow injection
port (trusted top-level request_hash, ignored _omo_policy request_hash, no
hard agora import, explicit False on terminal ledger failure).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pytest
from ecos.ssot.mof.generated.control.mof_control_models import DelegationMandate

from omo.event_ledger.broker import LedgerBroker, LedgerError
from omo.sovereignty import (
    EVT_ACTION_STARTED,
    EVT_ACTION_SUCCEEDED,
    EVT_POLICY_DECISION,
    PDP_PRODUCER,
    REASON_ALLOWED,
    REASON_LEDGER_UNAVAILABLE,
    REASON_PDP_UNAVAILABLE,
    REASON_POLICY_DENIED,
    REASON_PROVIDER_FAILED,
    REASON_RECEIPT_UNCONFIRMED,
    STABLE_REASONS,
    ActionRequest,
    AgoraPepProvider,
    InvalidActionRequestError,
    MandateManager,
    PolicyEnforcementService,
    SovereigntyService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "enforce.db"


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
def pdp(broker):
    yield PolicyEnforcementService(broker)


@pytest.fixture()
def now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _grant_mandate(svc, mgr, now, *, cap="bos://mail/draft", **overrides):
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["family-commitments"],
    )
    resp = assignment.responsibilities[0]
    kwargs = {
        "mandate_id": "mandate:enforce-001",
        "schema_version": "delegation-mandate/v1",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_enforce",
        "role_context_id": "role:family-steward",
        "role_assignment_id": assignment.assignment_id,
        "role_assignment_version": assignment.version,
        "responsibility_id": resp.resp_id,
        "responsibility_version": resp.version,
        "purpose": "Enforcement test mandate",
        "capability_scope": [cap],
        "autonomy_level": "A3",
        "risk_ceiling": "R2",
        "approval_mode": "matrix",
        "disclosure_policy": "disclosure:private",
        "valid_from": now - timedelta(hours=1),
        "expires_at": now + timedelta(days=365),
        "budget_limit": 10.0,
        "budget_unit": "call",
        "revocable": True,
        "trace_id": "enforce001234567890abcdef12",
        "mandate_version": 1,
        "status": "active",
    }
    kwargs.update(overrides)
    return mgr.grant(DelegationMandate(**kwargs))


def _make_request(**overrides: object) -> ActionRequest:
    kwargs: dict[str, object] = {
        "action_id": "action:draft-reply",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_enforce",
        "mandate_id": "mandate:enforce-001",
        "role_context_id": "role:family-steward",
        "responsibility_id": "responsibility:family-commitments",
        "capability": "bos://mail/draft",
        "server_risk": "R2",
        "requested_budget": 1.0,
        "budget_unit": "call",
        "disclosure_policy": "disclosure:private",
        "request_hash": "req-hash-enforce-001",
    }
    kwargs.update(overrides)
    return ActionRequest(**kwargs)  # type: ignore[arg-type]


def _make_request_dict(*, request_hash="req-hash-enforce-001", **overrides):
    """Full Agora-style request dict: trusted top-level hash + _omo_policy."""
    req = _make_request(**overrides)
    envelope = {
        "action_id": req.action_id,
        "principal_id": req.principal_id,
        "executor_id": req.executor_id,
        "episode_id": req.episode_id,
        "mandate_id": req.mandate_id,
        "role_context_id": req.role_context_id,
        "responsibility_id": req.responsibility_id,
        "capability": req.capability,
        "server_risk": req.server_risk,
        "requested_budget": req.requested_budget,
        "budget_unit": req.budget_unit,
        "disclosure_policy": req.disclosure_policy,
        "request_hash": "caller-controlled-hash-IGNORED",  # must be ignored
        "trace_id": req.trace_id,
        "mandate_version": req.mandate_version,
    }
    return {
        "uri": req.capability,
        "tool_name": "mutate_resource",
        "operation": "write",
        "caller_id": req.executor_id,
        "arguments": {"_omo_policy": envelope},
        "capability_descriptor": {"effect_class": "effectful", "risk_level": "medium"},
        "request_hash": request_hash,
    }


class _FailingAppendBroker:
    """Delegates reads to a real broker; append raises from call ``n`` on."""

    def __init__(self, broker, *, fails_from: int = 1):
        self._broker = broker
        self._fails_from = fails_from
        self._calls = 0

    def read(self, *args, **kwargs):
        return self._broker.read(*args, **kwargs)

    def append(self, *args, **kwargs):
        self._calls += 1
        if self._calls >= self._fails_from:
            raise LedgerError("simulated ledger append failure")
        return self._broker.append(*args, **kwargs)


class _FailingReadBroker:
    """A broker whose reads always fail (PDP unavailable)."""

    def __init__(self, broker):
        self._broker = broker

    def read(self, *args, **kwargs):
        raise LedgerError("simulated ledger read failure")

    def append(self, *args, **kwargs):
        return self._broker.append(*args, **kwargs)


class _CountingProvider:
    def __init__(self, *, raise_error: Exception | None = None, result=None):
        self.calls = 0
        self._raise_error = raise_error
        self._result = result or {"ok": True}

    def __call__(self, request: ActionRequest) -> dict:
        self.calls += 1
        if self._raise_error is not None:
            raise self._raise_error
        return self._result


# ---------------------------------------------------------------------------
# PDP decisions
# ---------------------------------------------------------------------------


def test_stable_reasons_vocabulary():
    assert STABLE_REASONS == (
        REASON_ALLOWED,
        REASON_POLICY_DENIED,
        REASON_PDP_UNAVAILABLE,
        REASON_LEDGER_UNAVAILABLE,
        REASON_PROVIDER_FAILED,
        REASON_RECEIPT_UNCONFIRMED,
    )


def test_decide_allow_is_durable(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    result = pdp.decide(_make_request())
    assert result.decision.decision == "allow"
    assert result.decision.reason == REASON_ALLOWED
    assert result.persisted is True
    assert result.reused is False
    # Decision is durably replayable.
    replayed = pdp.replay_decisions("action:draft-reply")
    assert len(replayed) == 1
    assert replayed[0].decision_id == result.decision.decision_id
    assert replayed[0].schema_version == "policy-decision/v1"
    assert replayed[0].request_hash == "req-hash-enforce-001"
    assert replayed[0].capability == "bos://mail/draft"
    # Exactly one Decision event (no receipts yet).
    events = pdp.replay_events()
    assert [e["event_type"] for e in events] == [EVT_POLICY_DECISION]
    assert events[0]["producer"] == PDP_PRODUCER


def test_decide_no_mandate_is_policy_denied_and_durable(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    result = pdp.decide(_make_request(mandate_id="mandate:missing"))
    assert result.decision.decision == "deny"
    assert result.decision.reason == REASON_POLICY_DENIED
    assert result.persisted is True
    assert pdp.decision("action:draft-reply").decision == "deny"


def test_admission_denial_maps_to_policy_denied(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    result = pdp.decide(_make_request(requested_budget=999.0))
    assert result.decision.decision == "deny"
    # Fine-grained mandate reason goes to description; the stable vocabulary
    # only ever says policy_denied.
    assert result.decision.reason == REASON_POLICY_DENIED
    assert "budget" in (result.decision.description or "")


def test_idempotent_reuse_same_action_same_hash(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    first = pdp.decide(_make_request())
    count_after_first = len(pdp.replay_events())
    second = pdp.decide(_make_request())
    assert second.decision.decision_id == first.decision.decision_id
    assert second.reused is True
    assert second.persisted is False
    assert len(pdp.replay_events()) == count_after_first


def test_request_mismatch_same_action_different_hash_is_denied(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    first = pdp.decide(_make_request())
    second = pdp.decide(_make_request(request_hash="req-hash-different-002"))
    assert first.decision.decision == "allow"
    assert second.decision.decision == "deny"
    assert second.decision.reason == REASON_POLICY_DENIED
    assert "request_hash_mismatch" in (second.decision.description or "")
    # The original hash stays reusable (idempotent), the conflict is durable.
    assert pdp.decide(_make_request()).decision.decision_id == first.decision.decision_id
    assert pdp.decide(_make_request(request_hash="req-hash-different-002")).reused is True


def test_pdp_failure_denies_with_zero_calls(broker):
    failing = _FailingReadBroker(broker)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    result = pdp.decide(_make_request())
    assert result.decision.decision == "deny"
    assert result.decision.reason == REASON_PDP_UNAVAILABLE
    assert result.persisted is False
    outcome = pdp.execute(_make_request(), _CountingProvider())
    assert outcome.status == "denied"
    assert outcome.provider_calls == 0


def test_decision_append_failure_denies_with_zero_calls(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = _FailingAppendBroker(broker, fails_from=1)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    outcome = pdp.execute(_make_request(), _CountingProvider())
    assert outcome.status == "denied"
    assert outcome.reason == REASON_LEDGER_UNAVAILABLE
    assert outcome.provider_calls == 0
    assert outcome.started_receipt_id is None


# ---------------------------------------------------------------------------
# Execution flow
# ---------------------------------------------------------------------------


def test_execute_success_order_and_replay(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    provider = _CountingProvider()
    outcome = pdp.execute(_make_request(), provider)
    assert outcome.status == "succeeded"
    assert outcome.reason == REASON_ALLOWED
    assert outcome.provider_calls == 1
    assert provider.calls == 1
    # Ordered replay: decision -> started -> succeeded.
    events = pdp.replay_events()
    assert [e["event_type"] for e in events] == [
        EVT_POLICY_DECISION,
        EVT_ACTION_STARTED,
        EVT_ACTION_SUCCEEDED,
    ]
    receipts = pdp.replay_receipts("action:draft-reply")
    assert [r.status for r in receipts] == ["started", "succeeded"]
    assert receipts[0].decision_id == outcome.decision_id
    assert receipts[1].decision_id == outcome.decision_id
    assert receipts[1].completed_at is not None
    assert receipts[1].result == {"ok": True}


def test_execute_provider_failure_writes_failed_receipt(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    provider = _CountingProvider(raise_error=RuntimeError("provider boom"))
    outcome = pdp.execute(_make_request(), provider)
    assert outcome.status == "failed"
    assert outcome.reason == REASON_PROVIDER_FAILED
    assert outcome.provider_calls == 1
    receipts = pdp.replay_receipts("action:draft-reply")
    assert [r.status for r in receipts] == ["started", "failed"]
    assert receipts[1].reason == REASON_PROVIDER_FAILED
    assert receipts[1].completed_at is not None


def test_execute_started_append_failure_never_calls_provider(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = _FailingAppendBroker(broker, fails_from=2)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    provider = _CountingProvider()
    outcome = pdp.execute(_make_request(), provider)
    assert outcome.status == "failed"
    assert outcome.reason == REASON_LEDGER_UNAVAILABLE
    assert outcome.provider_calls == 0
    assert provider.calls == 0
    assert outcome.started_receipt_id is None


def test_execute_terminal_append_failure_never_returns_succeeded(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = _FailingAppendBroker(broker, fails_from=3)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    provider = _CountingProvider()
    outcome = pdp.execute(_make_request(), provider)
    assert outcome.status == "unconfirmed"
    assert outcome.reason == REASON_RECEIPT_UNCONFIRMED
    assert outcome.provider_calls == 1
    assert outcome.terminal_receipt_id is None
    # Started receipt is visible in replay; no terminal exists.
    receipts = pdp.replay_receipts("action:draft-reply")
    assert [r.status for r in receipts] == ["started"]
    assert outcome.started_receipt_id == receipts[0].receipt_id


def test_idempotent_retry_returns_prior_state_without_recall(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    provider = _CountingProvider()
    first = pdp.execute(_make_request(), provider)
    assert first.status == "succeeded"
    second = pdp.execute(_make_request(), provider)
    assert second.status == "succeeded"
    assert second.decision_id == first.decision_id
    assert second.provider_calls == 0
    assert provider.calls == 1  # provider never re-invoked
    # Retry after failure returns the prior failed state without recall.
    pdp2 = PolicyEnforcementService(pdp.broker)
    provider2 = _CountingProvider()
    third = pdp2.execute(_make_request(), provider2)
    assert third.status == "succeeded"
    assert third.provider_calls == 0
    assert provider2.calls == 0


# ---------------------------------------------------------------------------
# AgoraPepProvider — narrow injection port
# ---------------------------------------------------------------------------


def test_provider_module_has_no_hard_agora_import():
    # The core OMO module must not hard-import Agora (no dependency cycle).
    assert "agora" not in sys.modules
    import omo.sovereignty.enforcement as en

    assert "agora" not in sys.modules
    assert hasattr(en.AgoraPepProvider, "evaluate")
    assert hasattr(en.AgoraPepProvider, "start_receipt")
    assert hasattr(en.AgoraPepProvider, "confirm_receipt")


def test_adapter_evaluate_uses_trusted_top_level_hash(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    adapter = AgoraPepProvider(service=pdp)
    request_dict = _make_request_dict(request_hash="trusted-hash-0001")
    decision = adapter.evaluate(request_dict)
    assert decision.decision == "allow"
    # The trusted top-level hash wins; the caller-controlled _omo_policy hash
    # ("caller-controlled-hash-IGNORED") is ignored.
    assert decision.request_hash == "trusted-hash-0001"


def test_adapter_missing_trusted_hash_raises(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    adapter = AgoraPepProvider(service=pdp)
    request_dict = _make_request_dict()
    request_dict.pop("request_hash")
    with pytest.raises(InvalidActionRequestError):
        adapter.evaluate(request_dict)
    request_dict["request_hash"] = "short"
    with pytest.raises(InvalidActionRequestError):
        adapter.evaluate(request_dict)


def test_adapter_missing_omo_policy_envelope_raises(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    adapter = AgoraPepProvider(service=pdp)
    request_dict = _make_request_dict()
    request_dict["arguments"] = {}
    with pytest.raises(InvalidActionRequestError):
        adapter.evaluate(request_dict)


def test_adapter_full_flow_persists_decision_started_terminal(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    adapter = AgoraPepProvider(service=pdp)
    decision = adapter.evaluate(_make_request_dict())
    assert decision.decision == "allow"
    started = adapter.start_receipt(decision)
    assert started.status == "started"
    ok = adapter.confirm_receipt(started, "succeeded", result={"ok": True})
    assert ok is True
    events = pdp.replay_events()
    assert [e["event_type"] for e in events] == [
        EVT_POLICY_DECISION,
        EVT_ACTION_STARTED,
        EVT_ACTION_SUCCEEDED,
    ]
    receipts = pdp.replay_receipts("action:draft-reply")
    assert [r.status for r in receipts] == ["started", "succeeded"]


def test_adapter_confirm_terminal_ledger_failure_returns_false(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = _FailingAppendBroker(broker, fails_from=3)
    adapter = AgoraPepProvider(service=PolicyEnforcementService(failing))  # type: ignore[arg-type]
    decision = adapter.evaluate(_make_request_dict())
    started = adapter.start_receipt(decision)
    assert adapter.confirm_receipt(started, "succeeded", result={"ok": True}) is False


def test_adapter_deny_path(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    adapter = AgoraPepProvider(service=pdp)
    request_dict = _make_request_dict(mandate_id="mandate:missing")
    decision = adapter.evaluate(request_dict)
    assert decision.decision == "deny"
    assert decision.reason == REASON_POLICY_DENIED
