"""W2-03 integration — real LedgerBroker enforcement, replay and hash chain.

Runs the full enforcement lifecycle against a REAL SQLite LedgerBroker with a
controlled fake provider and asserts: the ordered decision → started →
terminal replay; ledger hash-chain integrity (verify_chain green); the
fail-closed matrix (allow / no mandate / request mismatch / PDP failure /
decision / started / terminal append failures / provider failure / same-
process idempotent retry / terminal failure); deterministic replay across a
fresh service instance; and W2-01/W2-02 read-path non-regression (mandate
admission and sovereignty query still work on a ledger that carries
enforcement events).  No real external side effects.
"""

from __future__ import annotations

import json
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
    ActionRequest,
    MandateManager,
    PolicyEnforcementService,
    SovereigntyService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "w2-03-integration.db"


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


def _grant_mandate(svc, mgr, now, *, mandate_id="mandate:w2-03-001", cap="bos://mail/draft"):
    assignment = svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["family-commitments"],
    )
    resp = assignment.responsibilities[0]
    return mgr.grant(
        DelegationMandate(
            mandate_id=mandate_id,
            schema_version="delegation-mandate/v1",
            principal_id="principal:alice",
            executor_id="agent:planner",
            episode_id="episode_w203",
            role_context_id="role:family-steward",
            role_assignment_id=assignment.assignment_id,
            role_assignment_version=assignment.version,
            responsibility_id=resp.resp_id,
            responsibility_version=resp.version,
            purpose="W2-03 integration mandate",
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
            trace_id="w203001234567890abcdef12",
            mandate_version=1,
            status="active",
        )
    )


def _request(**overrides) -> ActionRequest:
    kwargs = {
        "action_id": "action:integrate-send",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_w203",
        "mandate_id": "mandate:w2-03-001",
        "role_context_id": "role:family-steward",
        "responsibility_id": "responsibility:family-commitments",
        "capability": "bos://mail/draft",
        "server_risk": "R2",
        "requested_budget": 1.0,
        "budget_unit": "call",
        "disclosure_policy": "disclosure:private",
        "request_hash": "req-hash-w2-03-integration",
    }
    kwargs.update(overrides)
    return ActionRequest(**kwargs)  # type: ignore[arg-type]


class FakeProvider:
    """Controlled fake provider; counts invocations, may raise."""

    def __init__(self, *, raise_error: Exception | None = None):
        self.calls = 0
        self._raise_error = raise_error

    def __call__(self, request: ActionRequest) -> dict:
        self.calls += 1
        if self._raise_error is not None:
            raise self._raise_error
        return {"ok": True, "action": request.action_id}


class FailingAppendBroker:
    """Real reads; append raises LedgerError from call ``fails_from`` on."""

    def __init__(self, broker, *, fails_from: int):
        self._broker = broker
        self._fails_from = fails_from
        self._calls = 0

    def read(self, *args, **kwargs):
        return self._broker.read(*args, **kwargs)

    def append(self, *args, **kwargs):
        self._calls += 1
        if self._calls >= self._fails_from:
            raise LedgerError("simulated append failure")
        return self._broker.append(*args, **kwargs)


class FailingReadBroker:
    def __init__(self, broker):
        self._broker = broker

    def read(self, *args, **kwargs):
        raise LedgerError("simulated read failure")

    def append(self, *args, **kwargs):
        return self._broker.append(*args, **kwargs)


# ---------------------------------------------------------------------------
# Happy path: allow + ordered durable causality + hash chain
# ---------------------------------------------------------------------------


def test_ordered_replay_and_hash_chain_green(pdp, svc, mgr, now, broker):
    _grant_mandate(svc, mgr, now)
    provider = FakeProvider()
    outcome = pdp.execute(_request(), provider)

    assert outcome.status == "succeeded"
    assert outcome.reason == REASON_ALLOWED
    assert provider.calls == 1

    # Ordered causality: decision -> started -> succeeded (sequence order).
    events = pdp.replay_events()
    assert [e["event_type"] for e in events] == [
        EVT_POLICY_DECISION,
        EVT_ACTION_STARTED,
        EVT_ACTION_SUCCEEDED,
    ]
    assert all(e["producer"] == PDP_PRODUCER for e in events)
    sequences = [e["sequence"] for e in events]
    assert sequences == sorted(sequences)

    # Every enforcement event links the same episode + decision via causation.
    for e in events:
        assert e["episode_id"] == "episode_w203"
    decision_id = json.loads(events[0]["payload_json"])["decision_id"]
    assert events[1]["causation_id"] == decision_id
    assert events[2]["causation_id"] == decision_id

    # Ledger hash chain is contiguous and green.
    chain = broker.verify_chain(from_sequence=1)
    assert chain["ok"] is True, chain
    assert chain["total"] == broker.count()


def test_deterministic_replay_across_fresh_service(pdp, svc, mgr, now, db_path):
    _grant_mandate(svc, mgr, now)
    pdp.execute(_request(), FakeProvider())

    before_decisions = [d.model_dump(mode="json") for d in pdp.replay_decisions()]
    before_receipts = [r.model_dump(mode="json") for r in pdp.replay_receipts()]

    # Fresh broker + service on the same db: replay is deterministic.
    broker2 = LedgerBroker.connect(db_path)
    try:
        pdp2 = PolicyEnforcementService(broker2)
        assert [d.model_dump(mode="json") for d in pdp2.replay_decisions()] == before_decisions
        assert [r.model_dump(mode="json") for r in pdp2.replay_receipts()] == before_receipts
        assert broker2.verify_chain(from_sequence=1)["ok"] is True
    finally:
        broker2.close()


def test_same_process_idempotent_retry_no_recall(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    provider = FakeProvider()
    first = pdp.execute(_request(), provider)
    second = pdp.execute(_request(), provider)
    third = pdp.execute(_request(), provider)
    assert first.status == second.status == third.status == "succeeded"
    assert provider.calls == 1
    assert second.decision_id == first.decision_id
    assert second.terminal_receipt_id == first.terminal_receipt_id
    assert pdp.replay_receipts("action:integrate-send")[0].status == "started"


# ---------------------------------------------------------------------------
# Fail-closed matrix
# ---------------------------------------------------------------------------


def test_no_mandate_denied_zero_calls(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    provider = FakeProvider()
    outcome = pdp.execute(_request(mandate_id="mandate:missing"), provider)
    assert outcome.status == "denied"
    assert outcome.reason == REASON_POLICY_DENIED
    assert outcome.provider_calls == 0
    assert provider.calls == 0
    assert pdp.replay_receipts("action:integrate-send") == []


def test_request_mismatch_denied_zero_calls(pdp, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    provider = FakeProvider()
    assert pdp.execute(_request(), provider).status == "succeeded"
    outcome = pdp.execute(_request(request_hash="req-hash-different"), provider)
    assert outcome.status == "denied"
    assert outcome.reason == REASON_POLICY_DENIED
    assert outcome.provider_calls == 0
    assert provider.calls == 1  # only the first request ever reached the provider


def test_pdp_failure_denied_zero_calls(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = FailingReadBroker(broker)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    provider = FakeProvider()
    outcome = pdp.execute(_request(), provider)
    assert outcome.status == "denied"
    assert outcome.reason == REASON_PDP_UNAVAILABLE
    assert outcome.provider_calls == 0
    assert provider.calls == 0


def test_decision_append_failure_denied_zero_calls(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = FailingAppendBroker(broker, fails_from=1)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    provider = FakeProvider()
    outcome = pdp.execute(_request(), provider)
    assert outcome.status == "denied"
    assert outcome.reason == REASON_LEDGER_UNAVAILABLE
    assert outcome.provider_calls == 0
    assert provider.calls == 0


def test_started_append_failure_zero_calls(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = FailingAppendBroker(broker, fails_from=2)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    provider = FakeProvider()
    outcome = pdp.execute(_request(), provider)
    assert outcome.status == "failed"
    assert outcome.reason == REASON_LEDGER_UNAVAILABLE
    assert outcome.provider_calls == 0
    assert provider.calls == 0


def test_provider_failure_writes_failed_receipt(pdp, svc, mgr, now, broker):
    _grant_mandate(svc, mgr, now)
    provider = FakeProvider(raise_error=RuntimeError("provider crash"))
    outcome = pdp.execute(_request(), provider)
    assert outcome.status == "failed"
    assert outcome.reason == REASON_PROVIDER_FAILED
    assert outcome.provider_calls == 1
    receipts = pdp.replay_receipts("action:integrate-send")
    assert [r.status for r in receipts] == ["started", "failed"]
    assert receipts[1].reason == REASON_PROVIDER_FAILED
    assert broker.verify_chain(from_sequence=1)["ok"] is True


def test_terminal_append_failure_never_succeeded_started_visible(broker, svc, mgr, now):
    _grant_mandate(svc, mgr, now)
    failing = FailingAppendBroker(broker, fails_from=3)
    pdp = PolicyEnforcementService(failing)  # type: ignore[arg-type]
    provider = FakeProvider()
    outcome = pdp.execute(_request(), provider)
    assert outcome.status == "unconfirmed"
    assert outcome.reason == REASON_RECEIPT_UNCONFIRMED
    assert outcome.provider_calls == 1
    assert outcome.terminal_receipt_id is None
    receipts = pdp.replay_receipts("action:integrate-send")
    assert [r.status for r in receipts] == ["started"]  # started stays visible
    # A retry of an unconfirmed action never re-invokes the provider.
    retry = pdp.execute(_request(), provider)
    assert retry.status == "unconfirmed"
    assert provider.calls == 1


def test_read_path_non_regression_after_enforcement(pdp, svc, mgr, now):
    """W2-01/W2-02 read paths keep working on a ledger with enforcement events."""
    _grant_mandate(svc, mgr, now)
    pdp.execute(_request(), FakeProvider())
    # W2-02 pure-read admission still decides.
    admit = mgr.admit(
        mandate_id="mandate:w2-03-001",
        principal_id="principal:alice",
        executor_id="agent:planner",
        episode_id="episode_w203",
        role_context_id="role:family-steward",
        responsibility_id="responsibility:family-commitments",
        capability="bos://mail/draft",
        risk_level="R2",
        requested_budget=1.0,
        budget_unit="call",
        disclosure_policy="disclosure:private",
    )
    assert admit.allowed is True
    # W2-01 sovereignty query still replays the role assignment.
    state = svc.query("principal:alice")
    assert "role:family-steward" in state.assignments
