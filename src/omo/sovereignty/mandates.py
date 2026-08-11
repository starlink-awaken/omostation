"""W2-02 Sovereignty — DelegationMandate runtime (grant / revoke / admit).

Model-first: imports and validates with the generated Pydantic
``DelegationMandate`` from the ECOS M2 deterministic control compiler.
Every write goes through ``LedgerBroker.append`` with the full envelope;
every query replays the mandate ledger per principal_id.

Event types: exactly Mandate.Granted.v1 and Mandate.Revoked.v1.
Lifecycle: absent -> active(v1 grant only) -> revoked(v2 with
expected_version); no replace/scope mutation/same-ID regrant.

Admission is pure read / pure decision: it never appends.  Default deny
with stable reasons; the 16-cell matrix is evaluated with request risk,
and approval_mode may only tighten the matrix output.

Explicitly out of scope: PDP/PEP interception, PolicyDecision, ActionReceipt,
projections, real side effects, DDL/trigger/broker changes, M3, W2-03/W2-04.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import uuid4

from ecos.ssot.mof.generated.control.mof_control_models import DelegationMandate
from pydantic import ValidationError as PydanticValidationError

from omo.event_ledger.broker import LedgerBroker
from omo.sovereignty.roles import SovereigntyService, validate_id

# ---------------------------------------------------------------------------
# Identity / event constants
# ---------------------------------------------------------------------------

MANDATE_PRODUCER = "omo-mandate"
MANDATE_SPACE_ID = "sovereignty"

EVT_MANDATE_GRANT = "Mandate.Granted.v1"
EVT_MANDATE_REVOKE = "Mandate.Revoked.v1"
_ALL_MANDATE_EVENTS = frozenset({EVT_MANDATE_GRANT, EVT_MANDATE_REVOKE})

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"

# ---------------------------------------------------------------------------
# Frozen stable reason constants (admission outcomes)
# ---------------------------------------------------------------------------

REASON_ALLOW = "allow"
REASON_SUGGEST_ONLY = "suggest_only"
REASON_AUTONOMY_FORBIDS = "autonomy_forbids"
REASON_APPROVAL_REQUIRED = "approval_required"
REASON_PER_ACTION_APPROVAL_REQUIRED = "per_action_approval_required"
REASON_HUMAN_ADJUDICATION_REQUIRED = "human_adjudication_required"

REASON_MANDATE_NOT_FOUND = "mandate_not_found"
REASON_MANDATE_NOT_YET_VALID = "mandate_not_yet_valid"
REASON_MANDATE_EXPIRED = "mandate_expired"
REASON_MANDATE_REVOKED = "mandate_revoked"
REASON_PRINCIPAL_MISMATCH = "principal_mismatch"
REASON_EXECUTOR_MISMATCH = "executor_mismatch"
REASON_EPISODE_MISMATCH = "episode_mismatch"
REASON_ROLE_CONTEXT_STALE = "role_context_stale"
REASON_RESPONSIBILITY_STALE = "responsibility_stale"
REASON_CAPABILITY_OUT_OF_SCOPE = "capability_out_of_scope"
REASON_RISK_CEILING_EXCEEDED = "risk_ceiling_exceeded"
REASON_BUDGET_EXCEEDED = "budget_exceeded"
REASON_DISCLOSURE_MISMATCH = "disclosure_mismatch"

# ---------------------------------------------------------------------------
# Reasons ordered by severity (higher = more restrictive).
# Used by _tighten to pick the max (never downgrade).
# ---------------------------------------------------------------------------

_SEVERITY: dict[str, int] = {
    REASON_ALLOW: 0,
    REASON_SUGGEST_ONLY: 1,
    REASON_APPROVAL_REQUIRED: 2,
    REASON_PER_ACTION_APPROVAL_REQUIRED: 3,
    REASON_HUMAN_ADJUDICATION_REQUIRED: 4,
    REASON_AUTONOMY_FORBIDS: 5,
}

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MandateError(ValueError):
    """Base error for the mandate layer with a stable dispatch reason."""

    reason = "mandate_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IllegalMandateTransitionError(MandateError):
    reason = "illegal_mandate_transition"


class StaleMandateVersionError(MandateError):
    reason = "stale_mandate_version"


class MandateReplayError(MandateError):
    """A mandate event row cannot be deterministically replayed."""

    reason = "malformed_mandate_replay"


# ---------------------------------------------------------------------------
# Admission result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdmissionResult:
    """Pure-read admission decision.  Never writes to the ledger."""

    allowed: bool
    reason: str
    mandate: DelegationMandate | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "mandate_id": self.mandate.mandate_id if self.mandate else None,
        }


# ---------------------------------------------------------------------------
# Mandate state (deterministic replay product)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MandateState:
    """Deterministic replay of mandate events for one principal."""

    mandates: Mapping[str, DelegationMandate]
    """All mandate_ids keyed to their *latest* DelegationMandate snapshot."""


# ---------------------------------------------------------------------------
# 16-cell autonomy/risk matrix (ALL cells explicit; fixed per BET-Y1Q2-T1-05)
# ---------------------------------------------------------------------------

# Matrix: autonomy_level x risk_level -> base reason
# All 16 cells are explicit — no sparse fallthrough.
# approval_mode may only tighten, never loosen.

_MATRIX: dict[str, dict[str, str]] = {
    "A0": {  # Observe only — NEVER authorise side effects
        "R0": REASON_AUTONOMY_FORBIDS,
        "R1": REASON_AUTONOMY_FORBIDS,
        "R2": REASON_AUTONOMY_FORBIDS,
        "R3": REASON_AUTONOMY_FORBIDS,
    },
    "A1": {  # Suggest only — all cells return suggest_only
        "R0": REASON_SUGGEST_ONLY,
        "R1": REASON_SUGGEST_ONLY,
        "R2": REASON_SUGGEST_ONLY,
        "R3": REASON_SUGGEST_ONLY,
    },
    "A2": {  # Assisted — risk-gated
        "R0": REASON_ALLOW,
        "R1": REASON_APPROVAL_REQUIRED,
        "R2": REASON_PER_ACTION_APPROVAL_REQUIRED,
        "R3": REASON_AUTONOMY_FORBIDS,
    },
    "A3": {  # Autonomous
        "R0": REASON_ALLOW,
        "R1": REASON_ALLOW,
        "R2": REASON_ALLOW,  # only when exact scope + within budget + revocable
        "R3": REASON_HUMAN_ADJUDICATION_REQUIRED,
    },
}

# Terminal outcomes: cannot be loosened by approval_mode tightening.
# Note: "deny" is NOT a frozen stable reason; approval_mode=deny maps to
# autonomy_forbids, which is a terminal reason.
_TERMINAL = frozenset(
    {
        REASON_SUGGEST_ONLY,
        REASON_AUTONOMY_FORBIDS,
        REASON_HUMAN_ADJUDICATION_REQUIRED,
    }
)


def _utc_now() -> str:
    """Default clock: current UTC ISO-8601 (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Local invariants (generated Pydantic does NOT enforce these)
# ---------------------------------------------------------------------------


def _check_local_invariants(mandate: DelegationMandate) -> None:
    """Reject values the generated Pydantic model allows but the contract forbids.

    - capability_scope: non-empty, no wildcard chars *? in any entry
    - budget_limit: finite and >= 0
    - mandate_version >= 1, role_assignment_version >= 1, responsibility_version >= 1
    - purpose must be non-empty
    - valid_from < expires_at (both must be timezone-aware)
    - valid_from / expires_at must be timezone-aware datetime
    """
    if not mandate.capability_scope or len(mandate.capability_scope) == 0:
        raise MandateError("capability_scope must be non-empty")
    for cap in mandate.capability_scope:
        if "*" in cap or "?" in cap:
            raise MandateError(f"capability_scope entry {cap!r} contains wildcard")
    if not math.isfinite(mandate.budget_limit) or mandate.budget_limit < 0:
        raise MandateError("budget_limit must be a finite number >= 0")
    if mandate.mandate_version < 1:
        raise MandateError("mandate_version must be >= 1")
    if mandate.role_assignment_version < 1:
        raise MandateError("role_assignment_version must be >= 1")
    if mandate.responsibility_version < 1:
        raise MandateError("responsibility_version must be >= 1")
    if not mandate.purpose or not mandate.purpose.strip():
        raise MandateError("purpose must be non-empty")
    # Both dates must be timezone-aware.
    if mandate.valid_from.tzinfo is None:
        raise MandateError("valid_from must be timezone-aware")
    if mandate.expires_at.tzinfo is None:
        raise MandateError("expires_at must be timezone-aware")
    if mandate.valid_from >= mandate.expires_at:
        raise MandateError("valid_from must be before expires_at")


# ---------------------------------------------------------------------------
# MandateManager
# ---------------------------------------------------------------------------


class MandateManager:
    """DelegationMandate operations over a causal event ledger.

    ``broker`` must be an already-connected :class:`LedgerBroker`.
    ``clock`` is a callable that returns an ISO-8601 string (default: UTC now).
    """

    def __init__(
        self,
        broker: LedgerBroker,
        *,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self._broker = broker
        self._clock = clock

    @classmethod
    def open(
        cls,
        db_path: str | Any,
        *,
        clock: Callable[[], str] = _utc_now,
    ) -> MandateManager:
        return cls(LedgerBroker.connect(db_path), clock=clock)

    # -- write path --------------------------------------------------------

    def grant(self, mandate: DelegationMandate) -> DelegationMandate:
        """Grant a new DelegationMandate (absent -> active v1).

        The mandate must be in active status with version 1.  The current
        W2-01 RoleAssignment must be active, role_context_id must match,
        and responsibility must belong to that assignment.  The assignment
        and responsibility versions are snapshotted into the mandate.

        Returns the mandate with trace_id populated (generated if not set).
        Raises :class:`IllegalMandateTransitionError` if a mandate with
        the same mandate_id already exists.
        """
        # Pydantic validation already ran on construction; enforce local invariants.
        _check_local_invariants(mandate)
        _validate_mandate_state(mandate, expect_version=1, expect_status=STATUS_ACTIVE)

        # Cross-principal existence check (not just per-principal replay)
        all_state = self._replay_all()
        if mandate.mandate_id in all_state.mandates:
            raise IllegalMandateTransitionError(
                f"mandate {mandate.mandate_id} already exists; cannot re-grant"
            )

        # Verify W2-01 role context and snapshot versions.
        actual = self._resolve_role_assignment_versions(mandate)
        # Compare assignment_id AND versions.
        if mandate.role_assignment_id != actual.role_assignment_id:
            raise MandateError(
                f"role_assignment_id mismatch in grant for {mandate.mandate_id}: "
                f"supplied {mandate.role_assignment_id!r} vs actual "
                f"{actual.role_assignment_id!r}"
            )
        if (
            mandate.role_assignment_version != actual.role_assignment_version
            or mandate.responsibility_version != actual.responsibility_version
        ):
            raise MandateError(
                f"version mismatch in grant for {mandate.mandate_id}: "
                f"supplied (assignment={mandate.role_assignment_version}, "
                f"responsibility={mandate.responsibility_version}) vs "
                f"actual (assignment={actual.role_assignment_version}, "
                f"responsibility={actual.responsibility_version})"
            )

        # trace_id is already validated by Pydantic; generate if not supplied
        if not mandate.trace_id:
            mandate = mandate.model_copy(update={"trace_id": uuid4().hex[:24]})

        payload = mandate.model_dump(mode="json")
        payload["kind"] = "grant"
        self._append_event(EVT_MANDATE_GRANT, mandate, payload)
        return mandate

    def revoke(
        self,
        mandate_id: str,
        principal_id: str,
        *,
        expected_version: int,
        trace_id: str | None = None,
    ) -> DelegationMandate:
        """Revoke an active mandate (active v1 -> revoked v2).

        ``expected_version`` is REQUIRED (no unsafe default). Must equal
        the current mandate version (1).
        Raises :class:`IllegalMandateTransitionError` for absent/revoked.
        Raises :class:`StaleMandateVersionError` on version mismatch.
        """
        # Cross-principal lookup
        state = self._replay_all()
        current = state.mandates.get(mandate_id)
        if current is None:
            raise IllegalMandateTransitionError(f"mandate {mandate_id} not found")
        if current.principal_id != principal_id:
            raise IllegalMandateTransitionError(
                f"principal mismatch for mandate {mandate_id}: "
                f"owned by {current.principal_id}, not {principal_id}"
            )
        if current.status == STATUS_REVOKED:
            raise IllegalMandateTransitionError(
                f"mandate {mandate_id} is already revoked"
            )
        if current.mandate_version != 1:
            raise IllegalMandateTransitionError(
                f"mandate {mandate_id} has unexpected version {current.mandate_version}"
            )
        if not current.revocable:
            raise IllegalMandateTransitionError(
                f"mandate {mandate_id} is not revocable"
            )
        if expected_version != current.mandate_version:
            raise StaleMandateVersionError(
                f"stale version for mandate {mandate_id}: expected "
                f"{expected_version}, current {current.mandate_version}"
            )

        # trace_id: only auto-generate when None.  A supplied empty or
        # otherwise invalid value must be rejected through Pydantic and
        # surfaced as a stable MandateError (never silently replaced).
        trace = uuid4().hex[:24] if trace_id is None else trace_id
        try:
            # Build full data dict and re-validate through Pydantic (never
            # model_copy without validation).
            revoked = DelegationMandate.model_validate(
                {
                    **current.model_dump(mode="json"),
                    "mandate_version": 2,
                    "status": STATUS_REVOKED,
                    "trace_id": trace,
                }
            )
        except PydanticValidationError as exc:
            raise MandateError(
                f"invalid revoke payload for mandate {mandate_id}: {exc.errors()}"
            ) from exc

        payload = revoked.model_dump(mode="json")
        payload["kind"] = "revoke"
        payload["prev_version"] = 1
        self._append_event(EVT_MANDATE_REVOKE, revoked, payload)
        return revoked

    # -- query path --------------------------------------------------------

    def query(self, principal_id: str) -> MandateState:
        """Replay the mandate ledger for ``principal_id``."""
        validate_id("principal", principal_id)
        return self._replay(principal_id)

    def get(self, mandate_id: str, principal_id: str) -> DelegationMandate | None:
        """Return the current (replayed) mandate, or None."""
        state = self._replay(principal_id)
        return state.mandates.get(mandate_id)

    # -- admission (pure read / pure decision, never appends) ---------------

    def admit(
        self,
        mandate_id: str,
        principal_id: str,
        executor_id: str,
        episode_id: str,
        role_context_id: str,
        responsibility_id: str,
        capability: str,
        risk_level: str,
        requested_budget: float,
        budget_unit: str,
        disclosure_policy: str,
    ) -> AdmissionResult:
        """Pure admission decision.  Never writes to the ledger."""
        # 1. Mandate existence (cross-principal)
        full_state = self._replay_all()
        mandate = full_state.mandates.get(mandate_id)
        if mandate is None:
            return AdmissionResult(False, REASON_MANDATE_NOT_FOUND)

        # 2. Identity checks
        if mandate.principal_id != principal_id:
            return AdmissionResult(False, REASON_PRINCIPAL_MISMATCH, mandate)
        if mandate.executor_id != executor_id:
            return AdmissionResult(False, REASON_EXECUTOR_MISMATCH, mandate)
        if mandate.episode_id != episode_id:
            return AdmissionResult(False, REASON_EPISODE_MISMATCH, mandate)

        # 3. Validity window (clock-driven)
        now = self._now_dt()
        if now < mandate.valid_from:
            return AdmissionResult(False, REASON_MANDATE_NOT_YET_VALID, mandate)
        if now >= mandate.expires_at:
            return AdmissionResult(False, REASON_MANDATE_EXPIRED, mandate)

        # 4. Status
        if mandate.status == STATUS_REVOKED:
            return AdmissionResult(False, REASON_MANDATE_REVOKED, mandate)

        # 5. Role context vs mandate snapshots + current assignment
        #    Compare request role_context_id/responsibility_id to mandate snapshots,
        #    AND compare current assignment (id/version/status, responsibility version).
        if mandate.role_context_id != role_context_id:
            return AdmissionResult(False, REASON_ROLE_CONTEXT_STALE, mandate)
        if mandate.responsibility_id != responsibility_id:
            return AdmissionResult(False, REASON_RESPONSIBILITY_STALE, mandate)

        svc = SovereigntyService(self._broker)
        assignment = svc.current_assignment(principal_id, role_context_id)
        if assignment is None or assignment.status != STATUS_ACTIVE:
            return AdmissionResult(False, REASON_ROLE_CONTEXT_STALE, mandate)
        # Compare assignment_id, version
        if assignment.assignment_id != mandate.role_assignment_id:
            return AdmissionResult(False, REASON_ROLE_CONTEXT_STALE, mandate)
        if assignment.version != mandate.role_assignment_version:
            return AdmissionResult(False, REASON_ROLE_CONTEXT_STALE, mandate)
        # Compare responsibility belongs to assignment and version matches
        resp = next(
            (r for r in assignment.responsibilities if r.resp_id == responsibility_id),
            None,
        )
        if resp is None:
            return AdmissionResult(False, REASON_RESPONSIBILITY_STALE, mandate)
        if resp.version != mandate.responsibility_version:
            return AdmissionResult(False, REASON_RESPONSIBILITY_STALE, mandate)

        # 6. Capability scope (exact match, no wildcard)
        if capability not in mandate.capability_scope:
            return AdmissionResult(False, REASON_CAPABILITY_OUT_OF_SCOPE, mandate)

        # 7. Risk ceiling
        if _risk_gt(risk_level, mandate.risk_ceiling):
            return AdmissionResult(False, REASON_RISK_CEILING_EXCEEDED, mandate)

        # 8. Budget (non-finite, negative, unit-mismatch, or over-limit
        #    all default to deny, per H1/H4).
        if (
            not math.isfinite(requested_budget)
            or requested_budget < 0
            or _budget_exceeds(requested_budget, budget_unit, mandate)
        ):
            return AdmissionResult(False, REASON_BUDGET_EXCEEDED, mandate)

        # 9. Disclosure policy (exact match)
        if disclosure_policy != mandate.disclosure_policy:
            return AdmissionResult(False, REASON_DISCLOSURE_MISMATCH, mandate)

        # 10. 16-cell matrix + approval_mode tightening
        matrix_reason = _evaluate_matrix_cell(
            mandate.autonomy_level, risk_level, mandate
        )
        reason = _tighten(matrix_reason, mandate.approval_mode)

        allowed = reason == REASON_ALLOW
        return AdmissionResult(allowed, reason, mandate)

    # -- internals ---------------------------------------------------------

    def _replay(self, principal_id: str) -> MandateState:
        """Deterministic per-principal replay with full lifecycle enforcement."""
        mandates: dict[str, DelegationMandate] = {}
        rows = self._broker.read(producer=MANDATE_PRODUCER)
        for row in rows:
            if row.get("principal_id") != principal_id:
                continue
            self._replay_one_row(row, mandates)
        return MandateState(mandates=MappingProxyType(dict(mandates)))

    def _replay_all(self) -> MandateState:
        """Deterministic cross-principal replay with full lifecycle enforcement."""
        mandates: dict[str, DelegationMandate] = {}
        rows = self._broker.read(producer=MANDATE_PRODUCER)
        for row in rows:
            self._replay_one_row(row, mandates)
        return MandateState(mandates=MappingProxyType(dict(mandates)))

    def _replay_one_row(
        self,
        row: Mapping[str, Any],
        mandates: dict[str, DelegationMandate],
    ) -> None:
        """Validate and apply one mandate event row with full lifecycle checks."""
        sequence = row.get("sequence")
        event_type = row.get("event_type", "")

        # Unknown event type under MANDATE_PRODUCER is malformed.
        if event_type not in _ALL_MANDATE_EVENTS:
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: "
                f"unknown event_type {event_type!r} under producer {MANDATE_PRODUCER}"
            )

        # Decode and validate payload via generated Pydantic.
        payload = self._decode_event(row)
        try:
            mandate = DelegationMandate.model_validate(payload)
        except PydanticValidationError as exc:
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: "
                f"invalid DelegationMandate payload: {exc}"
            ) from exc
        try:
            # Generated Pydantic does NOT enforce the local invariants;
            # run them on every replayed row so a Pydantic-valid but
            # locally invalid grant cannot be admitted by replay.
            _check_local_invariants(mandate)
        except MandateError as exc:
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: "
                f"mandate violates local invariant: {exc.message}"
            ) from exc
        kind = payload["kind"]

        # event_type / kind mismatch
        if event_type == EVT_MANDATE_GRANT and kind != "grant":
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: "
                f"event_type {EVT_MANDATE_GRANT} but kind={kind!r}"
            )
        if event_type == EVT_MANDATE_REVOKE and kind != "revoke":
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: "
                f"event_type {EVT_MANDATE_REVOKE} but kind={kind!r}"
            )

        # Envelope fields MUST be present and exactly equal to payload fields.
        # None/missing for required envelope fields is malformed.
        _REQUIRED_ENVELOPE = (
            "principal_id",
            "episode_id",
            "mandate_id",
            "role_context_id",
            "responsibility_id",
        )
        for fld in _REQUIRED_ENVELOPE:
            env_val = row.get(fld)
            payload_val = payload.get(fld)
            if env_val is None or not isinstance(env_val, str) or not env_val:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"missing/empty required envelope field {fld}"
                )
            if payload_val != env_val:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"payload.{fld}={payload_val!r} != envelope.{fld}={env_val!r}"
                )

        mandate_id = mandate.mandate_id
        previous = mandates.get(mandate_id)

        if kind == "grant":
            # grant: active v1, no prior ID
            if previous is not None:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"duplicate grant for mandate {mandate_id!r}"
                )
            if mandate.status != STATUS_ACTIVE:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"grant must have status active, got {mandate.status!r}"
                )
            if mandate.mandate_version != 1:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"grant must have version 1, got {mandate.mandate_version}"
                )
            mandates[mandate_id] = mandate

        elif kind == "revoke":
            # revoke: revoked v2, prev_version=1, prior active v1 MUST exist
            if previous is None:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"revoke without prior grant for mandate {mandate_id!r}"
                )
            if previous.status != STATUS_ACTIVE:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"revoke on non-active mandate {mandate_id!r} "
                    f"(status={previous.status!r})"
                )
            if previous.mandate_version != 1:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"prior mandate version is {previous.mandate_version}, should be 1"
                )
            if mandate.status != STATUS_REVOKED:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"revoke must have status revoked, got {mandate.status!r}"
                )
            if mandate.mandate_version != 2:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"revoke must have version 2, got {mandate.mandate_version}"
                )
            if payload.get("prev_version") != 1:
                raise MandateReplayError(
                    f"malformed mandate event at seq {sequence}: "
                    f"revoke prev_version must be 1, got {payload.get('prev_version')}"
                )
            # Future-proof immutable-field check: compare the full generated
            # model dump.  Only status, mandate_version, and trace_id may
            # change on revoke; any other generated field mutation is
            # malformed (this covers every field of the model, including any
            # added in later model revisions).
            prev_dump = previous.model_dump(mode="json")
            this_dump = mandate.model_dump(mode="json")
            for fname in prev_dump:
                if fname in ("status", "mandate_version", "trace_id"):
                    continue
                if prev_dump[fname] != this_dump[fname]:
                    raise MandateReplayError(
                        f"malformed mandate event at seq {sequence}: "
                        f"immutable field {fname} mutated on revoke: "
                        f"was {prev_dump[fname]!r}, got {this_dump[fname]!r}"
                    )
            mandates[mandate_id] = mandate

    def _decode_event(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Strictly decode one mandate event row."""
        sequence = row.get("sequence")
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError, KeyError):
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: payload is not valid JSON"
            ) from None
        if not isinstance(payload, dict):
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: "
                "payload must be a JSON object"
            )
        kind = payload.get("kind")
        if kind not in ("grant", "revoke"):
            raise MandateReplayError(
                f"malformed mandate event at seq {sequence}: unknown kind {kind!r}"
            )
        return payload

    def _resolve_role_assignment_versions(
        self, mandate: DelegationMandate
    ) -> _RoleSnapshot:
        """Verify W2-01 RoleAssignment and return actual versions."""
        svc = SovereigntyService(self._broker)
        assignment = svc.current_assignment(
            mandate.principal_id, mandate.role_context_id
        )
        if assignment is None or assignment.status != STATUS_ACTIVE:
            raise MandateError(
                f"role {mandate.role_context_id} not active for {mandate.principal_id}"
            )
        resp_ids = {r.resp_id for r in assignment.responsibilities}
        if mandate.responsibility_id not in resp_ids:
            raise MandateError(
                f"responsibility {mandate.responsibility_id} not in "
                f"assignment {assignment.assignment_id}"
            )
        resp = next(
            r
            for r in assignment.responsibilities
            if r.resp_id == mandate.responsibility_id
        )
        return _RoleSnapshot(
            role_assignment_id=assignment.assignment_id,
            role_assignment_version=assignment.version,
            responsibility_version=resp.version,
        )

    def _append_event(
        self,
        event_type: str,
        mandate: DelegationMandate,
        payload: dict[str, Any],
    ) -> int:
        kind = payload["kind"]
        return self._broker.append(
            event_type=event_type,
            producer=MANDATE_PRODUCER,
            principal_id=mandate.principal_id,
            space_id=MANDATE_SPACE_ID,
            correlation_id=(
                f"mandate|{mandate.mandate_id}|{kind}|{mandate.mandate_version}"
            ),
            idempotency_key=f"{mandate.mandate_id}|{mandate.mandate_version}",
            episode_id=mandate.episode_id,
            role_context_id=mandate.role_context_id,
            responsibility_id=mandate.responsibility_id,
            mandate_id=mandate.mandate_id,
            occurred_at=self._clock_ts(),
            payload=payload,
        )

    def _clock_ts(self) -> str:
        """Validate the injected clock and return the tz-aware ISO value.

        Raises a stable :class:`MandateError` for naive or malformed clock
        values BEFORE any event is appended or any comparison uses them.
        """
        ts = self._clock()
        try:
            dt = datetime.fromisoformat(ts)
        except (ValueError, TypeError) as exc:
            raise MandateError(
                f"clock returned invalid ISO datetime {ts!r}: {exc}"
            ) from exc
        if dt.tzinfo is None:
            raise MandateError(
                f"clock returned naive (non-timezone-aware) datetime {ts!r}"
            )
        return dt.isoformat()

    def _now_dt(self) -> datetime:
        return datetime.fromisoformat(self._clock_ts())


# ---------------------------------------------------------------------------
# _RoleSnapshot — outcome of _resolve_role_assignment_versions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RoleSnapshot:
    role_assignment_id: str
    role_assignment_version: int
    responsibility_version: int


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_mandate_state(
    mandate: DelegationMandate,
    expect_version: int,
    expect_status: str,
) -> None:
    if mandate.mandate_version != expect_version:
        raise IllegalMandateTransitionError(
            f"mandate {mandate.mandate_id}: expected version "
            f"{expect_version}, got {mandate.mandate_version}"
        )
    if mandate.status != expect_status:
        raise IllegalMandateTransitionError(
            f"mandate {mandate.mandate_id}: expected status "
            f"{expect_status!r}, got {mandate.status!r}"
        )


# ---------------------------------------------------------------------------
# Risk ordering
# ---------------------------------------------------------------------------

_RISK_ORDER: dict[str, int] = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}


def _risk_gt(level: str, ceiling: str) -> bool:
    lo = _RISK_ORDER.get(level, 99)
    lc = _RISK_ORDER.get(ceiling, -1)
    return lo > lc


def _budget_exceeds(
    requested: float,
    unit: str,
    mandate: DelegationMandate,
) -> bool:
    if unit != mandate.budget_unit:
        return True
    return requested > mandate.budget_limit


# ---------------------------------------------------------------------------
# 16-cell matrix evaluation
# ---------------------------------------------------------------------------


def _evaluate_matrix_cell(autonomy: str, risk: str, mandate: DelegationMandate) -> str:
    """Return the fixed matrix cell result.  All 16 cells are explicit."""
    row = _MATRIX.get(autonomy, {})
    base = row.get(risk, REASON_AUTONOMY_FORBIDS)

    # A3/R2 special: allow only when revocable
    if autonomy == "A3" and risk == "R2" and base == REASON_ALLOW:
        if not mandate.revocable:
            return REASON_PER_ACTION_APPROVAL_REQUIRED

    return base


def _tighten(matrix_reason: str, approval_mode: str) -> str:
    """Apply approval_mode tightening using severity max.

    approval_mode may only tighten (higher severity), never loosen.
    approval_mode=deny maps to autonomy_forbids (terminal).
    """
    base_severity = _SEVERITY.get(matrix_reason, 5)

    if approval_mode == "deny":
        # denial is a policy choice → autonomy_forbids
        mode_reason = REASON_AUTONOMY_FORBIDS
    elif approval_mode == "matrix":
        return matrix_reason
    elif approval_mode == "approval_required":
        mode_reason = REASON_APPROVAL_REQUIRED
    elif approval_mode == "per_action_approval_required":
        mode_reason = REASON_PER_ACTION_APPROVAL_REQUIRED
    elif approval_mode == "human_adjudication_required":
        mode_reason = REASON_HUMAN_ADJUDICATION_REQUIRED
    else:
        mode_reason = REASON_AUTONOMY_FORBIDS

    mode_severity = _SEVERITY.get(mode_reason, 5)
    # Pick the max severity — only tighten, never downgrade.
    if mode_severity >= base_severity:
        return mode_reason
    return matrix_reason


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "EVT_MANDATE_GRANT",
    "EVT_MANDATE_REVOKE",
    "MANDATE_PRODUCER",
    "MANDATE_SPACE_ID",
    "REASON_ALLOW",
    "REASON_APPROVAL_REQUIRED",
    "REASON_AUTONOMY_FORBIDS",
    "REASON_BUDGET_EXCEEDED",
    "REASON_CAPABILITY_OUT_OF_SCOPE",
    "REASON_DISCLOSURE_MISMATCH",
    "REASON_EPISODE_MISMATCH",
    "REASON_EXECUTOR_MISMATCH",
    "REASON_HUMAN_ADJUDICATION_REQUIRED",
    "REASON_MANDATE_EXPIRED",
    "REASON_MANDATE_NOT_FOUND",
    "REASON_MANDATE_NOT_YET_VALID",
    "REASON_MANDATE_REVOKED",
    "REASON_PER_ACTION_APPROVAL_REQUIRED",
    "REASON_PRINCIPAL_MISMATCH",
    "REASON_RESPONSIBILITY_STALE",
    "REASON_RISK_CEILING_EXCEEDED",
    "REASON_ROLE_CONTEXT_STALE",
    "REASON_SUGGEST_ONLY",
    "STATUS_ACTIVE",
    "STATUS_REVOKED",
    "AdmissionResult",
    "IllegalMandateTransitionError",
    "MandateError",
    "MandateManager",
    "MandateReplayError",
    "MandateState",
    "StaleMandateVersionError",
]
