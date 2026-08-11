"""W2-04 Episode projection read models — read-only deterministic rebuild.

Pure-read projection over the causal event ledger (``LedgerBroker``) that
builds per-principal views without ever appending:

- ``episodes`` — Episode M2 aggregates keyed by legal ``episode_id``.  Every
  row whose event class is a card (``Episode.FYI/Approval/Decision``) or an
  ``EPISODE_REQUIRED_CLASSES`` chain member (Decision/Mandate/Action/Evidence/
  Outcome, e.g. W2-03 ``Decision.Policy.v1`` / ``Action.Started.v1``) joins
  its episode.  Each entry is constructed through the ECOS generated
  ``EventEnvelope`` / ``Episode`` pydantic models and serialized with
  ``model_dump(mode="json")``.
- ``role_portfolio`` — per-principal role state via ``SovereigntyService``,
  which replays only ``EVT_ASSIGN`` / ``EVT_REPLACE`` / ``EVT_REVOKE`` for
  the requested principal (strict isolation).
- ``inbox`` — FYI / Approval / Decision cards only (never the non-card chain
  members), with stable field defaults and role/responsibility backfill.
- ``blocked`` — stable enum-like reasons for malformed / missing / invalid
  rows (never a silent skip, never an exception message).
- ``controls`` — read counts plus a ledger-unchanged proof (count + hash
  chain both sampled before and after the projection).

Explicitly out of scope: duplicate handling, raw SQL, concurrency,
persistence, DDL, checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ecos.ssot.mof.generated.control.mof_control_models import Episode, EventEnvelope
from pydantic import ValidationError

from omo.event_ledger import EPISODE_REQUIRED_CLASSES, LedgerBroker
from omo.sovereignty import STATUS_ACTIVE, SovereigntyError, SovereigntyService

SCHEMA_VERSION = "episode-projection/v1"
EPISODE_SCHEMA_VERSION = "episode/v1"

#: Episode card classes projected into ``inbox`` (and, when carrying a legal
#: ``episode_id``, into ``episodes``).
EPISODE_CARD_EVENTS = frozenset(
    {"Episode.FYI.v1", "Episode.Approval.v1", "Episode.Decision.v1"}
)

#: Stable blocked reasons (enum-like, never exception text).
REASON_MALFORMED_PAYLOAD = "malformed_payload"
REASON_MISSING_EPISODE_ID = "missing_episode_id"
REASON_INVALID_EPISODE_M2 = "invalid_episode_m2"
REASON_ROLE_REPLAY_FAILED = "role_replay_failed"

_CARD_TYPE_BY_EVENT = {
    "Episode.FYI.v1": "fyi",
    "Episode.Approval.v1": "approval",
    "Episode.Decision.v1": "decision",
}


def build_episode_projection_snapshot(
    broker: LedgerBroker, *, principal_id: str
) -> dict[str, Any]:
    """Build the W2-04 read models for ``principal_id`` from ``broker``.

    Pure read: only ``broker.read`` / ``broker.count`` / ``broker.verify_chain``
    are used; nothing is ever appended.  The ledger is provably unchanged
    (count before/after plus hash-chain verification) and every replay is
    deterministic.
    """
    count_before = broker.count()
    chain_before = broker.verify_chain()
    rows = broker.read()
    events_read = len(rows)
    events_ignored = 0
    blocked: list[dict[str, Any]] = []
    episodes_dump: dict[str, dict[str, Any]] = {}
    episode_order: list[str] = []
    episode_counts: dict[str, int] = {}
    inbox: list[dict[str, Any]] = []

    for row in rows:
        if row.get("principal_id") != principal_id:
            events_ignored += 1
            continue
        event_type = row.get("event_type") or ""
        cls_name = event_type.split(".", 1)[0] if event_type else ""
        is_card = event_type in EPISODE_CARD_EVENTS
        if not (is_card or cls_name in EPISODE_REQUIRED_CLASSES):
            events_ignored += 1
            continue

        try:
            raw_payload = json.loads(row["payload_json"])
        except (KeyError, TypeError, ValueError):
            blocked.append(
                _blocked_entry(
                    row, REASON_MALFORMED_PAYLOAD, "payload is not valid JSON"
                )
            )
            continue
        if not isinstance(raw_payload, Mapping):
            blocked.append(
                _blocked_entry(
                    row, REASON_MALFORMED_PAYLOAD, "payload must be a JSON object"
                )
            )
            continue
        payload = raw_payload

        episode_id = row.get("episode_id") or payload.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id:
            blocked.append(
                _blocked_entry(row, REASON_MISSING_EPISODE_ID, "missing episode_id")
            )
            continue

        try:
            envelope = EventEnvelope(
                event_id=row["event_id"],
                schema_version=row.get("schema_version") or "event-envelope/v1",
                source_ref=row.get("producer") or row["event_id"],
                emitted_at=row.get("occurred_at") or row.get("recorded_at"),
                payload=dict(payload),
            )
        except ValidationError as exc:
            blocked.append(
                _blocked_entry(
                    row, REASON_INVALID_EPISODE_M2, _first_validation_error(exc)
                )
            )
            continue
        envelope_dump = envelope.model_dump(mode="json")

        if episode_id not in episodes_dump:
            try:
                episode = Episode(
                    episode_id=episode_id,
                    schema_version=EPISODE_SCHEMA_VERSION,
                    contains_event_refs=[envelope],
                    opened_at=envelope.emitted_at,
                )
            except ValidationError as exc:
                blocked.append(
                    _blocked_entry(
                        row, REASON_INVALID_EPISODE_M2, _first_validation_error(exc)
                    )
                )
                continue
            episodes_dump[episode_id] = episode.model_dump(mode="json")
            episode_order.append(episode_id)
        else:
            episodes_dump[episode_id]["contains_event_refs"].append(envelope_dump)

        episode_counts[episode_id] = episode_counts.get(episode_id, 0) + 1
        if is_card:
            inbox.append(_inbox_card(event_type, row, payload, episode_id))

    episodes = [episodes_dump[episode_id] for episode_id in episode_order]
    role_portfolio = _role_portfolio(broker, principal_id, episode_counts, blocked)

    count_after = broker.count()
    chain_after = broker.verify_chain()

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "live",
        "principal_id": principal_id,
        "episodes": episodes,
        "role_portfolio": role_portfolio,
        "inbox": inbox,
        "blocked": blocked,
        "controls": {
            "events_read": events_read,
            "events_ignored": events_ignored,
            "events_blocked": len(blocked),
            "ledger_count_before": count_before,
            "ledger_count_after": count_after,
            "ledger_unchanged": (
                count_before == count_after and chain_before == chain_after
            ),
            "chain_before": {
                "ok": chain_before["ok"],
                "total": chain_before["total"],
            },
            "chain_after": {"ok": chain_after["ok"], "total": chain_after["total"]},
        },
    }


def build_episode_projection_snapshot_from_path(
    db_path: Path | str, *, principal_id: str
) -> dict[str, Any]:
    """Open ``db_path``, build the snapshot, and always close the broker."""
    broker = LedgerBroker.connect(db_path)
    try:
        return build_episode_projection_snapshot(broker, principal_id=principal_id)
    finally:
        broker.close()


def _role_portfolio(
    broker: LedgerBroker,
    principal_id: str,
    episode_counts: dict[str, int],
    blocked: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replay the principal's role state via ``SovereigntyService``.

    ``SovereigntyService.query`` replays only sovereignty events
    (``EVT_ASSIGN`` / ``EVT_REPLACE`` / ``EVT_REVOKE``) for this principal —
    no other producer's events can leak into the portfolio.
    """
    base = {
        "principal_id": principal_id,
        "active_assignments": [],
        "responsibilities": [],
        "episode_counts": dict(sorted(episode_counts.items())),
    }
    try:
        principal = SovereigntyService(broker).query(principal_id)
    except SovereigntyError as exc:
        blocked.append(
            {
                "event_id": None,
                "event_type": None,
                "sequence": None,
                "reason": REASON_ROLE_REPLAY_FAILED,
                "detail": str(exc),
            }
        )
        return base

    active = sorted(
        (a for a in principal.assignments.values() if a.status == STATUS_ACTIVE),
        key=lambda a: a.role_id,
    )
    responsibilities: dict[str, dict[str, Any]] = {}
    for assignment in active:
        for resp in assignment.responsibilities:
            responsibilities.setdefault(resp.resp_id, resp.to_dict())
    return {
        "principal_id": principal_id,
        "active_assignments": [a.to_dict() for a in active],
        "responsibilities": [responsibilities[k] for k in sorted(responsibilities)],
        "episode_counts": dict(sorted(episode_counts.items())),
    }


def _inbox_card(
    event_type: str,
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
    episode_id: str,
) -> dict[str, Any]:
    """One FYI/Approval/Decision card; missing fields default to None.

    ``role`` / ``responsibility`` backfill from the payload's ``role``/
    ``role_id`` / ``responsibility`` / ``responsibility_id`` keys and fall
    back to the envelope's ``role_context_id`` / ``responsibility_id``.
    """
    return {
        "card_type": _CARD_TYPE_BY_EVENT.get(event_type, event_type),
        "episode": episode_id,
        "principal": row.get("principal_id") or None,
        "role": payload.get("role")
        or payload.get("role_id")
        or row.get("role_context_id"),
        "responsibility": (
            payload.get("responsibility")
            or payload.get("responsibility_id")
            or row.get("responsibility_id")
        ),
        "why_now": payload.get("why_now"),
        "summary": payload.get("summary"),
        "risk": payload.get("risk"),
        "authority": payload.get("authority"),
        "status": payload.get("status"),
        "evidence_refs": payload.get("evidence_refs"),
        "deadline": payload.get("deadline"),
    }


def _blocked_entry(
    row: Mapping[str, Any], reason: str, detail: str
) -> dict[str, Any]:
    return {
        "event_id": row.get("event_id"),
        "event_type": row.get("event_type"),
        "sequence": row.get("sequence"),
        "reason": reason,
        "detail": detail,
    }


def _first_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return str(exc)
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()))
    msg = first.get("msg", "invalid value")
    return f"{loc}: {msg}" if loc else msg


__all__ = [
    "EPISODE_CARD_EVENTS",
    "EPISODE_SCHEMA_VERSION",
    "REASON_INVALID_EPISODE_M2",
    "REASON_MALFORMED_PAYLOAD",
    "REASON_MISSING_EPISODE_ID",
    "REASON_ROLE_REPLAY_FAILED",
    "SCHEMA_VERSION",
    "build_episode_projection_snapshot",
    "build_episode_projection_snapshot_from_path",
]
