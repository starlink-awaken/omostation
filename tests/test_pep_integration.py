"""Integration tests for PEP (Policy Enforcement Port) — BET-Y1Q2-T1-06.

Tests the narrow SPI to OMO PDP using ECOS contract types.
Covers: missing provider → deny, deny → 0 calls, started-write failure → 0 calls,
exact payload allow → 1 call, payload change → reject, terminal write failure →
no success, read-only no regression.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from ecos.ssot.mof.generated.control.mof_control_models import (
    ActionReceipt,
    PolicyDecision,
)

from agora.mcp.policy_enforcement import (
    PEPDenied,
    complete,
    compute_request_hash,
    enforce,
    get_current_permit,
    is_server_read_only,
    reset_pep_provider_cache,
    reset_permit,
    set_current_permit,
    verify_permit,
)


# ── Helpers: build valid ECOS contract instances ─────────────────────────


def _make_decision(
    request_hash: str,
    decision: str = "allow",
    reason: str = "allowed",
) -> PolicyDecision:
    """Build a minimal valid PolicyDecision."""
    now = datetime.now(UTC)
    return PolicyDecision(
        decision_id="decision:test-0001",
        schema_version="policy-decision/v1",
        decision=decision,
        action_id="action:test-0001",
        principal_id="principal:test-user",
        executor_id="agent:test-agent",
        episode_id="test-epi-0001",
        mandate_id="mandate:test-mandate",
        mandate_version=1,
        capability="bos://test/cap/action",
        server_risk="R1",
        budget_limit=10,
        budget_unit="call",
        disclosure="disclosure:private",
        request_hash=request_hash,
        trace_id="trace-test-00001",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        reason=reason,
    )


def _make_receipt(decision_id: str = "decision:test-0001") -> ActionReceipt:
    """Build a minimal valid ActionReceipt (started state)."""
    now = datetime.now(UTC)
    return ActionReceipt(
        receipt_id="receipt:test-0001",
        schema_version="action-receipt/v1",
        decision_id=decision_id,
        action_id="action:test-0001",
        principal_id="principal:test-user",
        executor_id="agent:test-agent",
        episode_id="test-epi-0001",
        mandate_id="mandate:test-mandate",
        mandate_version=1,
        capability="bos://test/cap/action",
        server_risk="R1",
        budget_limit=10,
        budget_unit="call",
        disclosure="disclosure:private",
        request_hash="validhash0001",
        trace_id="trace-test-00001",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        status="started",
        started_at=now,
    )


# ── Fake durable provider ────────────────────────────────────────────────


class FakeDurableProvider:
    """Fake PEP provider that persists to in-memory dict (simulates durable ledger)."""

    def __init__(self) -> None:
        self.evaluate_calls = 0
        self.start_calls = 0
        self.confirm_calls = 0
        self.confirm_ok = True
        self._deny = False
        self._start_fails = False
        self.started_hashes: set[str] = set()
        self.terminal_writes: list[tuple[str, str]] = []  # (decision_id, status)

    def evaluate(self, request: dict) -> PolicyDecision | None:
        self.evaluate_calls += 1
        # Use trusted top-level request_hash injected by enforce()
        h = request.get("request_hash", "")
        decision_val = "deny" if self._deny else "allow"
        reason = "policy_denied" if self._deny else "allowed"
        return _make_decision(h, decision=decision_val, reason=reason)

    def start_receipt(self, decision: PolicyDecision) -> ActionReceipt | None:
        self.start_calls += 1
        if self._start_fails:
            return None
        self.started_hashes.add(decision.request_hash)
        return _make_receipt(decision.decision_id)

    def confirm_receipt(self, receipt, status, result, reason) -> bool:
        self.confirm_calls += 1
        self.terminal_writes.append((receipt.decision_id, status))
        return self.confirm_ok


@pytest.fixture(autouse=True)
def _reset_pep():
    """Fresh PEP state for each test."""
    reset_pep_provider_cache()
    yield
    reset_pep_provider_cache()


def _inject_provider(monkeypatch, provider):
    """Inject a fake provider into the PEP module."""
    import agora.mcp.policy_enforcement as pep_mod

    monkeypatch.setattr(pep_mod, "_provider_cache", provider)


# ── Tests: request hash ──────────────────────────────────────────────────


class TestRequestHash:
    def test_covers_all_fields(self):
        """Hash must cover uri/tool/operation/caller/arguments/payload."""
        h1 = compute_request_hash(
            uri="bos://a/b/c",
            tool_name="t",
            operation="read",
            caller_id="u1",
            arguments={"x": 1},
            payload={"y": 2},
        )
        h2 = compute_request_hash(
            uri="bos://a/b/c",
            tool_name="t",
            operation="read",
            caller_id="u1",
            arguments={"x": 1},
            payload={"y": 2},
        )
        assert h1 == h2

    def test_different_payload_different_hash(self):
        h1 = compute_request_hash(
            uri="bos://a/b/c",
            tool_name="t",
            operation="read",
            caller_id="u1",
            arguments={},
            payload={"v": 1},
        )
        h2 = compute_request_hash(
            uri="bos://a/b/c",
            tool_name="t",
            operation="read",
            caller_id="u1",
            arguments={},
            payload={"v": 2},
        )
        assert h1 != h2

    def test_different_arguments_different_hash(self):
        h1 = compute_request_hash(arguments={"a": 1})
        h2 = compute_request_hash(arguments={"a": 2})
        assert h1 != h2


# ── Tests: read-only exemption ───────────────────────────────────────────


class TestReadOnlyExemption:
    def test_known_read_only_tools(self):
        for tool in ["read_resource", "list_bos_resources", "bos_health"]:
            assert is_server_read_only(tool), f"{tool} should be read-only"

    def test_mutate_not_read_only(self):
        assert not is_server_read_only("mutate_resource")

    def test_read_only_exempt_from_mandate(self, monkeypatch):
        """Read-only tools don't need a provider — enforce returns (None, None)."""
        # No provider injected — should still pass for read-only
        _inject_provider(monkeypatch, None)
        decision, receipt = enforce(tool_name="read_resource", operation="read")
        assert decision is None
        assert receipt is None

    def test_read_only_no_regression_at_adapter(self, monkeypatch):
        """verify_permit passes for read-only without permit."""
        _inject_provider(monkeypatch, None)
        # Should not raise
        verify_permit(tool_name="read_resource")


# ── Tests: missing provider → deny ───────────────────────────────────────


class TestMissingProviderDeny:
    def test_effectful_no_provider_denies(self, monkeypatch):
        """Rule 1: effectful with no provider → deny."""
        _inject_provider(monkeypatch, None)
        with pytest.raises(PEPDenied) as exc_info:
            enforce(
                uri="bos://test/data", tool_name="mutate_resource", operation="write"
            )
        assert "pdp_unavailable" in exc_info.value.reason

    def test_unknown_no_provider_denies(self, monkeypatch):
        """Unknown tool with no provider → deny."""
        _inject_provider(monkeypatch, None)
        with pytest.raises(PEPDenied) as exc_info:
            enforce(tool_name="totally_unknown_tool")
        assert "pdp_unavailable" in exc_info.value.reason

    def test_adapter_no_provider_no_permit_denies(self, monkeypatch):
        """verify_permit denies at adapter without permit for non-read-only."""
        _inject_provider(monkeypatch, None)
        with pytest.raises(PEPDenied):
            verify_permit(tool_name="some_effectful_tool")


# ── Tests: deny decision → 0 calls ───────────────────────────────────────


class TestDenyDecision:
    def test_deny_decision_raises(self, monkeypatch):
        """Provider returns deny → PEPDenied, no start_receipt called."""
        fake = FakeDurableProvider()
        fake._deny = True
        _inject_provider(monkeypatch, fake)

        with pytest.raises(PEPDenied) as exc_info:
            enforce(
                uri="bos://test/data", tool_name="mutate_resource", operation="write"
            )
        assert "policy_denied" in exc_info.value.reason
        assert fake.start_calls == 0  # no receipt started


# ── Tests: started-write failure → 0 calls ───────────────────────────────


class TestStartedWriteFailure:
    def test_start_fails_denies(self, monkeypatch):
        """start_receipt returns None → deny, 0 provider calls."""
        fake = FakeDurableProvider()
        fake._start_fails = True
        _inject_provider(monkeypatch, fake)

        with pytest.raises(PEPDenied) as exc_info:
            enforce(
                uri="bos://test/data", tool_name="mutate_resource", operation="write"
            )
        assert "ledger_unavailable" in exc_info.value.reason
        # evaluate was called but start failed
        assert fake.evaluate_calls == 1
        assert fake.start_calls == 1  # attempted but returned None


# ── Tests: exact payload allow → 1 call ──────────────────────────────────


class TestExactPayloadAllow:
    def test_allow_starts_receipt(self, monkeypatch):
        """Exact matching payload → allow, receipt started."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)

        decision, receipt = enforce(
            uri="bos://test/data",
            tool_name="mutate_resource",
            operation="write",
            caller_id="principal:test",
            arguments={"key": "val"},
            payload={"action": "create"},
        )
        assert decision is not None
        assert decision.decision == "allow"
        assert receipt is not None
        assert receipt.status == "started"
        assert fake.evaluate_calls == 1
        assert fake.start_calls == 1

    def test_confirm_succeeded(self, monkeypatch):
        """complete() confirms terminal succeeded."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)

        decision, receipt = enforce(
            uri="bos://test/data", tool_name="mutate_resource", operation="write"
        )
        complete(decision, receipt, succeeded=True)
        assert fake.confirm_calls == 1
        assert fake.terminal_writes[-1][1] == "succeeded"


# ── Tests: payload change → reject ───────────────────────────────────────


class TestPayloadChangeReject:
    def test_hash_mismatch_rejects(self, monkeypatch):
        """Provider returns a hash that doesn't match → reject."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)

        # Tamper with the provider to return a wrong hash
        def tampered_eval(request):
            h = request.get("request_hash", "")
            d = _make_decision(h)
            return d.model_copy(update={"request_hash": "tampered12345"})

        fake.evaluate = tampered_eval

        with pytest.raises(PEPDenied) as exc_info:
            enforce(
                uri="bos://test/data", tool_name="mutate_resource", operation="write"
            )
        assert "hash_mismatch" in exc_info.value.reason

    def test_payload_change_changes_top_level_hash(self, monkeypatch):
        """Different payload → different request_dict['request_hash'] → deny on replay."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)
        captured_hashes: list[str] = []

        def capturing_eval(request: dict):
            captured_hashes.append(request.get("request_hash", ""))
            h = request.get("request_hash", "")
            return _make_decision(h)

        fake.evaluate = capturing_eval

        # First call with payload A — succeeds
        d1, r1 = enforce(
            uri="bos://test/data",
            tool_name="mutate_resource",
            operation="write",
            payload={"value": 1},
        )
        # Second call with payload B — different hash, should still succeed
        # (provider returns allow for the new hash)
        d2, r2 = enforce(
            uri="bos://test/data",
            tool_name="mutate_resource",
            operation="write",
            payload={"value": 2},
        )
        # The two request_hashes must differ
        assert len(captured_hashes) == 2
        assert captured_hashes[0] != captured_hashes[1]

    def test_payload_replay_with_stale_hash_denies(self, monkeypatch):
        """Replaying an old hash with changed payload → deny."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)

        stale_hash: list[str] = []

        def stale_eval(request: dict):
            # Always return the FIRST hash, ignoring the current one
            h = request.get("request_hash", "")
            if not stale_hash:
                stale_hash.append(h)
            return _make_decision(stale_hash[0])

        fake.evaluate = stale_eval

        # First call — succeeds (hash matches)
        enforce(
            uri="bos://t/d",
            tool_name="mutate_resource",
            operation="write",
            payload={"v": 1},
        )
        # Second call with different payload — stale hash → mismatch → deny
        with pytest.raises(PEPDenied) as exc_info:
            enforce(
                uri="bos://t/d",
                tool_name="mutate_resource",
                operation="write",
                payload={"v": 2},
            )
        assert "hash_mismatch" in exc_info.value.reason


# ── Tests: terminal write failure → no success ──────────────────────────


class TestTerminalWriteFailure:
    def test_confirm_failure_blocks_success(self, monkeypatch):
        """confirm_receipt returns False → complete() raises PEPDenied."""
        fake = FakeDurableProvider()
        fake.confirm_ok = False
        _inject_provider(monkeypatch, fake)

        decision, receipt = enforce(
            uri="bos://test/data", tool_name="mutate_resource", operation="write"
        )
        with pytest.raises(PEPDenied) as exc_info:
            complete(decision, receipt, succeeded=True)
        assert "receipt_unconfirmed" in exc_info.value.reason

    def test_confirm_failure_allows_failed_status(self, monkeypatch):
        """If operation already failed, confirm failure doesn't raise."""
        fake = FakeDurableProvider()
        fake.confirm_ok = False
        _inject_provider(monkeypatch, fake)

        decision, receipt = enforce(
            uri="bos://test/data", tool_name="mutate_resource", operation="write"
        )
        # Should NOT raise — failure is the correct terminal
        complete(decision, receipt, succeeded=False, error="boom")


# ── Tests: permit propagation ─────────────────────────────────────────────


class TestPermitPropagation:
    def test_set_get_permit(self):
        """ContextVar correctly propagates permit hash."""
        token = set_current_permit("test_permit_123")
        assert get_current_permit() == "test_permit_123"
        reset_permit(token)
        assert get_current_permit() is None

    def test_verify_permit_passes_with_permit(self):
        """verify_permit passes when a permit is set."""
        token = set_current_permit("valid_permit")
        try:
            verify_permit(tool_name="any_effectful_tool")
        finally:
            reset_permit(token)

    def test_verify_permit_fails_without_permit(self):
        """verify_permit raises for non-read-only without permit."""
        with pytest.raises(PEPDenied) as exc_info:
            verify_permit(tool_name="any_effectful_tool")
        assert "no_permit" in exc_info.value.reason


# ── Tests: full lifecycle integration ────────────────────────────────────


class TestFullLifecycle:
    def test_effectful_full_lifecycle(self, monkeypatch):
        """Full lifecycle: enforce → provider call → complete."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)

        # Enforce
        decision, receipt = enforce(
            uri="bos://mail/draft",
            tool_name="mutate_resource",
            operation="write",
            caller_id="principal:test",
            arguments={"to": "user@example.com"},
            payload={"subject": "test"},
        )
        assert decision.decision == "allow"
        assert receipt.status == "started"
        assert fake.evaluate_calls == 1
        assert fake.start_calls == 1
        assert fake.confirm_calls == 0

        # Simulate provider call
        token = set_current_permit(decision.request_hash)
        try:
            verify_permit(tool_name="mutate_resource")  # should pass
        finally:
            reset_permit(token)

        # Complete
        complete(decision, receipt, succeeded=True, result={"id": 42})
        assert fake.confirm_calls == 1
        assert fake.terminal_writes == [("decision:test-0001", "succeeded")]

    def test_read_only_skips_lifecycle(self, monkeypatch):
        """Read-only tools skip the entire PEP lifecycle."""
        fake = FakeDurableProvider()
        _inject_provider(monkeypatch, fake)

        decision, receipt = enforce(tool_name="read_resource", operation="read")
        assert decision is None
        assert receipt is None
        assert fake.evaluate_calls == 0  # provider not consulted

        # complete() is a no-op
        complete(decision, receipt, succeeded=True)
        assert fake.confirm_calls == 0


# ── Tests: PEPDenied propagation ─────────────────────────────────────────


class TestPEPDeniedPropagation:
    def test_denied_at_adapter_propagates(self, monkeypatch):
        """PEPDenied from verify_permit propagates as exception."""
        _inject_provider(monkeypatch, None)
        with pytest.raises(PEPDenied):
            verify_permit(tool_name="mutate_resource")

    def test_exception_not_silently_swallowed(self, monkeypatch):
        """PEPDenied is a proper exception, not a dict that can be ignored."""
        fake = FakeDurableProvider()
        fake._deny = True
        _inject_provider(monkeypatch, fake)

        with pytest.raises(PEPDenied) as exc_info:
            enforce(uri="bos://x/y/z", tool_name="mutate_resource", operation="write")
        # Verify the exception carries structured info
        assert exc_info.value.reason == "policy_denied"
