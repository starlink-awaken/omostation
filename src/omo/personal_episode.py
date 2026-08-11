"""W2-05 personal episode kernel over the causal Event Ledger.

This deliberately small service is the local, single-user seam between the
W2-04 inbox and the existing W2-02/03 authorization machinery.  It writes no
state outside :class:`LedgerBroker`: restarting the process therefore cannot
lose an approved episode or manufacture an authorization context.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Mapping

from ecos.ssot.mof.generated.control.mof_control_models import DelegationMandate

from omo.event_ledger.broker import LedgerBroker
from omo.sovereignty.mandates import MandateError, MandateManager, STATUS_ACTIVE
from omo.sovereignty.roles import SovereigntyError, SovereigntyService


PERSONAL_EPISODE_PRODUCER = "omo-personal-episode"
PERSONAL_EPISODE_SPACE_ID = "personal"
CAPABILITY = "bos://personal/followup/draft"
RISK = "R0"
DISCLOSURE_POLICY = "disclosure:private"

EVT_EPISODE_DECISION = "Episode.Decision.v1"
EVT_EVIDENCE_LOCAL_DRAFT = "Evidence.LocalDraft.v1"
EVT_OUTCOME_HUMAN = "Outcome.Human.v1"

_OUTCOMES = frozenset({"accept", "edit", "reject", "defer"})


class PersonalEpisodeError(ValueError):
    """Stable domain error for the personal golden slice."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class PersonalEpisodeCard:
    episode_id: str
    request_id: str
    summary: str
    reused: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "request_id": self.request_id,
            "summary": self.summary,
            "reused": self.reused,
        }


@dataclass(frozen=True)
class PersonalEpisodeConfirmation:
    episode_id: str
    mandate_id: str
    reused: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "mandate_id": self.mandate_id,
            "reused": self.reused,
        }


@dataclass(frozen=True)
class PersonalExecutionContext:
    """Ledger-replayed context consumable as ``arguments._omo_policy``."""

    episode_id: str
    mandate_id: str
    principal_id: str
    executor_id: str
    role_context_id: str
    responsibility_id: str
    action_id: str
    trace_id: str

    @property
    def omo_policy(self) -> dict[str, Any]:
        """Return the complete fail-closed W2-03 PEP envelope."""
        return {
            "action_id": self.action_id,
            "principal_id": self.principal_id,
            "executor_id": self.executor_id,
            "episode_id": self.episode_id,
            "mandate_id": self.mandate_id,
            "role_context_id": self.role_context_id,
            "responsibility_id": self.responsibility_id,
            "capability": CAPABILITY,
            "server_risk": RISK,
            "requested_risk": RISK,
            "requested_budget": 1.0,
            "budget_unit": "call",
            "disclosure_policy": DISCLOSURE_POLICY,
            "trace_id": self.trace_id,
            "mandate_version": 1,
        }

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.omo_policy)
        result["_omo_policy"] = dict(self.omo_policy)
        return result


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PersonalEpisodeService:
    """A deterministic, ledger-backed personal draft episode service."""

    def __init__(
        self, broker: LedgerBroker, *, clock: Callable[[], str] = _utc_now
    ) -> None:
        self._broker = broker
        self._clock = clock

    @classmethod
    def open(
        cls, db_path: str | Any, *, clock: Callable[[], str] = _utc_now
    ) -> PersonalEpisodeService:
        return cls(LedgerBroker.connect(db_path), clock=clock)

    def start(
        self,
        *,
        principal_id: str,
        role_id: str,
        responsibility_id: str,
        executor_id: str,
        request_id: str,
        summary: str,
        why_now: str = "",
        deadline: str | None = None,
    ) -> PersonalEpisodeCard:
        """Append exactly one Inbox Decision card, idempotent by request id."""
        self._required("request_id", request_id)
        self._required("summary", summary)
        self._required("executor_id", executor_id)
        existing = self._find_start(principal_id, request_id)
        if existing is not None:
            payload = _payload(existing)
            return PersonalEpisodeCard(
                episode_id=str(existing["episode_id"]),
                request_id=request_id,
                summary=str(payload.get("summary", "")),
                reused=True,
            )

        self._active_assignment(principal_id, role_id, responsibility_id)
        episode_id = _deterministic("episode_", principal_id, role_id, responsibility_id, request_id)
        payload = {
            "episode_id": episode_id,
            "request_id": request_id,
            "summary": summary,
            "why_now": why_now or None,
            "deadline": deadline,
            "risk": RISK,
            "authority": "human_confirmation_required",
            "status": "pending_confirmation",
            "executor_id": executor_id,
            "role_id": role_id,
            "responsibility_id": responsibility_id,
        }
        self._broker.append(
            EVT_EPISODE_DECISION,
            producer=PERSONAL_EPISODE_PRODUCER,
            principal_id=principal_id,
            space_id=PERSONAL_EPISODE_SPACE_ID,
            correlation_id=f"personal-episode|{episode_id}",
            idempotency_key=f"start|{principal_id}|{request_id}",
            episode_id=episode_id,
            role_context_id=role_id,
            responsibility_id=responsibility_id,
            payload=payload,
            occurred_at=self._clock_ts(),
        )
        return PersonalEpisodeCard(episode_id=episode_id, request_id=request_id, summary=summary)

    def confirm(
        self,
        *,
        episode_id: str,
        principal_id: str,
        executor_id: str,
        human_confirmed: bool,
    ) -> PersonalEpisodeConfirmation:
        """Grant one revocable A2/R0 local-draft mandate after human confirmation."""
        if human_confirmed is not True:
            raise PersonalEpisodeError(
                "human_confirmation_required", "human_confirmed must be true"
            )
        start_row = self._start_for_episode(episode_id, principal_id)
        payload = _payload(start_row)
        if payload.get("executor_id") != executor_id:
            raise PersonalEpisodeError("executor_mismatch", "executor does not match episode")
        role_id = _required_payload(payload, "role_id")
        responsibility_id = _required_payload(payload, "responsibility_id")
        assignment = self._active_assignment(principal_id, role_id, responsibility_id)
        mandate_id = _deterministic("mandate:personal-", episode_id)
        manager = MandateManager(self._broker, clock=self._clock)
        current = manager.get(mandate_id, principal_id)
        if current is not None:
            if current.status != STATUS_ACTIVE:
                raise PersonalEpisodeError("mandate_not_active", "episode mandate is revoked")
            return PersonalEpisodeConfirmation(episode_id, mandate_id, reused=True)

        responsibility = next(
            item
            for item in assignment.responsibilities
            if item.resp_id == responsibility_id
        )
        now = self._clock_datetime()
        mandate = DelegationMandate(
            mandate_id=mandate_id,
            schema_version="delegation-mandate/v1",
            principal_id=principal_id,
            executor_id=executor_id,
            episode_id=episode_id,
            role_context_id=role_id,
            role_assignment_id=assignment.assignment_id,
            role_assignment_version=assignment.version,
            responsibility_id=responsibility_id,
            responsibility_version=responsibility.version,
            purpose="Create one local follow-up draft after human confirmation",
            capability_scope=[CAPABILITY],
            autonomy_level="A2",
            risk_ceiling=RISK,
            approval_mode="matrix",
            disclosure_policy=DISCLOSURE_POLICY,
            valid_from=now - timedelta(seconds=1),
            expires_at=now + timedelta(days=1),
            budget_limit=1.0,
            budget_unit="call",
            revocable=True,
            trace_id=_deterministic("trace_", episode_id, executor_id),
            mandate_version=1,
            status=STATUS_ACTIVE,
        )
        try:
            manager.grant(mandate)
        except MandateError as exc:
            raise PersonalEpisodeError("mandate_grant_failed", str(exc)) from exc
        return PersonalEpisodeConfirmation(episode_id, mandate_id)

    def reload_execution_context(
        self, episode_id: str, principal_id: str
    ) -> PersonalExecutionContext:
        """Rebuild the PEP envelope exclusively from persisted ledger events."""
        start_row = self._start_for_episode(episode_id, principal_id)
        payload = _payload(start_row)
        executor_id = _required_payload(payload, "executor_id")
        role_id = _required_payload(payload, "role_id")
        responsibility_id = _required_payload(payload, "responsibility_id")
        mandate_id = _deterministic("mandate:personal-", episode_id)
        mandate = MandateManager(self._broker, clock=self._clock).get(mandate_id, principal_id)
        if mandate is None or mandate.status != STATUS_ACTIVE:
            raise PersonalEpisodeError("episode_not_confirmed", "episode has no active mandate")
        return PersonalExecutionContext(
            episode_id=episode_id,
            mandate_id=mandate_id,
            principal_id=principal_id,
            executor_id=executor_id,
            role_context_id=role_id,
            responsibility_id=responsibility_id,
            action_id=_deterministic("action:personal-", episode_id),
            trace_id=mandate.trace_id,
        )

    def record_evidence(self, context: PersonalExecutionContext, evidence_uri: str) -> int:
        """Record the server-created local-draft artifact in the same episode."""
        self._required("evidence_uri", evidence_uri)
        existing = self._find_event(
            context.episode_id, EVT_EVIDENCE_LOCAL_DRAFT, "evidence_uri", evidence_uri
        )
        if existing is not None:
            return int(existing["sequence"])
        return self._broker.append(
            EVT_EVIDENCE_LOCAL_DRAFT,
            producer=PERSONAL_EPISODE_PRODUCER,
            principal_id=context.principal_id,
            space_id=PERSONAL_EPISODE_SPACE_ID,
            correlation_id=f"personal-episode|{context.episode_id}",
            idempotency_key=f"evidence|{context.episode_id}|{_short_hash(evidence_uri)}",
            episode_id=context.episode_id,
            role_context_id=context.role_context_id,
            responsibility_id=context.responsibility_id,
            mandate_id=context.mandate_id,
            payload={"evidence_uri": evidence_uri, "action_id": context.action_id},
            evidence_uri=evidence_uri,
            occurred_at=self._clock_ts(),
        )

    def record_outcome(self, context: PersonalExecutionContext, verdict: str) -> int:
        """Record one human feedback outcome using the closed vocabulary."""
        if verdict not in _OUTCOMES:
            raise PersonalEpisodeError(
                "invalid_outcome_verdict", "verdict must be accept/edit/reject/defer"
            )
        existing = self._find_event(context.episode_id, EVT_OUTCOME_HUMAN, "verdict", verdict)
        if existing is not None:
            return int(existing["sequence"])
        return self._broker.append(
            EVT_OUTCOME_HUMAN,
            producer=PERSONAL_EPISODE_PRODUCER,
            principal_id=context.principal_id,
            space_id=PERSONAL_EPISODE_SPACE_ID,
            correlation_id=f"personal-episode|{context.episode_id}",
            idempotency_key=f"outcome|{context.episode_id}|{verdict}",
            episode_id=context.episode_id,
            role_context_id=context.role_context_id,
            responsibility_id=context.responsibility_id,
            mandate_id=context.mandate_id,
            payload={"verdict": verdict, "action_id": context.action_id},
            occurred_at=self._clock_ts(),
        )

    def _active_assignment(self, principal_id: str, role_id: str, responsibility_id: str):
        try:
            assignment = SovereigntyService(self._broker).current_assignment(principal_id, role_id)
        except SovereigntyError as exc:
            raise PersonalEpisodeError("role_not_active", str(exc)) from exc
        if assignment is None or assignment.status != STATUS_ACTIVE:
            raise PersonalEpisodeError("role_not_active", "role assignment is not active")
        if not any(item.resp_id == responsibility_id for item in assignment.responsibilities):
            raise PersonalEpisodeError(
                "responsibility_not_active", "responsibility is not assigned to active role"
            )
        return assignment

    def _find_start(self, principal_id: str, request_id: str) -> Mapping[str, Any] | None:
        for row in self._broker.read(producer=PERSONAL_EPISODE_PRODUCER):
            if row.get("event_type") != EVT_EPISODE_DECISION or row.get("principal_id") != principal_id:
                continue
            if _payload(row).get("request_id") == request_id:
                return row
        return None

    def _start_for_episode(self, episode_id: str, principal_id: str) -> Mapping[str, Any]:
        for row in self._broker.read(episode_id=episode_id):
            if row.get("event_type") == EVT_EPISODE_DECISION and row.get("principal_id") == principal_id:
                return row
        raise PersonalEpisodeError("episode_not_found", "personal episode decision was not found")

    def _find_event(
        self, episode_id: str, event_type: str, payload_key: str, payload_value: str
    ) -> Mapping[str, Any] | None:
        for row in self._broker.read(episode_id=episode_id):
            if row.get("event_type") == event_type and _payload(row).get(payload_key) == payload_value:
                return row
        return None

    def _clock_ts(self) -> str:
        return self._clock_datetime().isoformat()

    def _clock_datetime(self) -> datetime:
        try:
            value = datetime.fromisoformat(self._clock())
        except (TypeError, ValueError) as exc:
            raise PersonalEpisodeError("invalid_clock", "clock must return ISO-8601") from exc
        if value.tzinfo is None:
            raise PersonalEpisodeError("invalid_clock", "clock must be timezone-aware")
        return value

    @staticmethod
    def _required(name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise PersonalEpisodeError("invalid_request", f"{name} must be non-empty")


def _payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        value = json.loads(str(row["payload_json"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise PersonalEpisodeError("malformed_episode", "episode payload is invalid") from exc
    if not isinstance(value, Mapping):
        raise PersonalEpisodeError("malformed_episode", "episode payload must be an object")
    return value


def _required_payload(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise PersonalEpisodeError("malformed_episode", f"episode payload missing {key}")
    return value


def _short_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def _deterministic(prefix: str, *parts: str) -> str:
    return prefix + _short_hash(*parts)


__all__ = [
    "CAPABILITY",
    "DISCLOSURE_POLICY",
    "EVT_EPISODE_DECISION",
    "EVT_EVIDENCE_LOCAL_DRAFT",
    "EVT_OUTCOME_HUMAN",
    "PERSONAL_EPISODE_PRODUCER",
    "PersonalEpisodeCard",
    "PersonalEpisodeConfirmation",
    "PersonalEpisodeError",
    "PersonalEpisodeService",
    "PersonalExecutionContext",
]
