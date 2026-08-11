"""W2-04 episode projection read models (tests).

Covers:
- empty ledger -> well-formed minimal snapshot
- role isolation (per-principal replay of RoleAssigned/Replaced/Revoked)
- episode aggregation by legal episode_id + inbox cards (FYI/Approval/Decision)
- deterministic rebuild (same ledger -> identical snapshot)
- malformed payload / missing episode_id / invalid M2 -> stable blocked reasons
- unknown / other-principal events ignored (not blocked, not in views)
- ledger untouched: count + hash-chain identical before/after projection
- broker-path vs from_path equivalence

Episode ids use the M2-legal ``episode_<n>`` shape (``[A-Za-z0-9_-]{8,}``);
colon-scoped ids are invalid M2 and must land in ``blocked``.
"""

from __future__ import annotations

from typing import Any

import pytest

from omo.episode_projection import (
    REASON_INVALID_EPISODE_M2,
    REASON_MALFORMED_PAYLOAD,
    REASON_MISSING_EPISODE_ID,
    SCHEMA_VERSION,
    build_episode_projection_snapshot,
    build_episode_projection_snapshot_from_path,
)
from omo.event_ledger import LedgerBroker
from omo.sovereignty import SovereigntyService


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def broker(tmp_path) -> LedgerBroker:
    b = LedgerBroker.connect(tmp_path / "ledger.db")
    yield b
    b.close()


def _assign(svc: SovereigntyService, principal_id: str, role_id: str, role_name: str) -> str:
    resp = svc.assign(
        principal_id=principal_id,
        role_id=role_id,
        role_name=role_name,
        scope="episode",
        responsibilities=["review"],
    )
    return resp.assignment_id


def _ledger_controls(broker: LedgerBroker) -> dict[str, Any]:
    chain = broker.verify_chain()
    assert chain["ok"] is True, chain
    return {"count": broker.count(), "chain": chain}


def _episode(
    broker: LedgerBroker,
    event_type: str,
    episode_id: str,
    payload: dict[str, Any],
    *,
    correlation_id: str,
    idempotency_key: str,
) -> int:
    return broker.append(
        event_type,
        producer="episode-ecos",
        principal_id="principal:alice",
        space_id="episodes",
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        episode_id=episode_id,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# 1. empty ledger -> well-formed empty snapshot
# ---------------------------------------------------------------------------


def test_empty_ledger_produces_minimal_snapshot(broker: LedgerBroker) -> None:
    snap = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    assert snap["schema_version"] == SCHEMA_VERSION == "episode-projection/v1"
    assert snap["status"] == "live"
    assert snap["principal_id"] == "principal:alice"
    assert snap["episodes"] == []
    assert snap["role_portfolio"]["principal_id"] == "principal:alice"
    assert snap["role_portfolio"]["active_assignments"] == []
    assert snap["role_portfolio"]["responsibilities"] == []
    assert snap["role_portfolio"]["episode_counts"] == {}
    assert snap["inbox"] == []
    assert snap["blocked"] == []
    assert snap["controls"]["events_read"] == 0


# ---------------------------------------------------------------------------
# 2. role isolation: Alice's replay does not leak into Bob's portfolio
# ---------------------------------------------------------------------------


def test_role_portfolio_is_isolated_per_principal(broker: LedgerBroker) -> None:
    svc = SovereigntyService(broker)
    _assign(svc, "principal:alice", "role:reviewer", "Reviewer")

    snap_alice = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    snap_bob = build_episode_projection_snapshot(broker, principal_id="principal:bob")

    assert len(snap_alice["role_portfolio"]["active_assignments"]) == 1
    assert snap_alice["role_portfolio"]["active_assignments"][0]["role_id"] == "role:reviewer"
    assert snap_bob["role_portfolio"]["active_assignments"] == []
    assert snap_bob["role_portfolio"]["responsibilities"] == []
    assert snap_bob["role_portfolio"]["episode_counts"] == {}


# ---------------------------------------------------------------------------
# 3. episode aggregation + inbox cards (missing fields -> None)
# ---------------------------------------------------------------------------


def test_episodes_and_inbox_cards(broker: LedgerBroker) -> None:
    _episode(
        broker,
        "Episode.Decision.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "summary": "approve rollout", "risk": "low"},
        correlation_id="c1",
        idempotency_key="k1",
    )
    _episode(
        broker,
        "Episode.FYI.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "why_now": "context"},
        correlation_id="c2",
        idempotency_key="k2",
    )
    _episode(
        broker,
        "Episode.Approval.v1",
        "episode_ep2",
        {"episode_id": "episode_ep2", "deadline": "2026-08-20", "status": "pending"},
        correlation_id="c3",
        idempotency_key="k3",
    )
    # role/responsibility backfill from the envelope's role_context_id /
    # responsibility_id when the payload carries no role keys
    broker.append(
        "Episode.FYI.v1",
        producer="episode-ecos",
        principal_id="principal:alice",
        space_id="episodes",
        correlation_id="c4",
        idempotency_key="k4",
        episode_id="episode_ep2",
        role_context_id="role:reviewer",
        responsibility_id="responsibility:review",
        payload={"episode_id": "episode_ep2", "summary": "role ctx"},
    )

    snap = build_episode_projection_snapshot(broker, principal_id="principal:alice")

    # episodes aggregated by episode_id, deterministic ordering
    eps = snap["episodes"]
    assert [e["episode_id"] for e in eps] == ["episode_ep1", "episode_ep2"]
    assert eps[0]["schema_version"] == "episode/v1"
    assert len(eps[0]["contains_event_refs"]) == 2
    assert len(eps[1]["contains_event_refs"]) == 2
    for e in eps:
        assert set(e) >= {"episode_id", "schema_version", "contains_event_refs", "opened_at"}
    # envelopes are the full EventEnvelope M2 dump
    first_env = eps[0]["contains_event_refs"][0]
    assert set(first_env) >= {"event_id", "schema_version", "source_ref", "emitted_at", "payload"}
    assert first_env["schema_version"] == "event-envelope/v1"
    assert first_env["payload"]["summary"] == "approve rollout"

    # inbox cards only FYI/Approval/Decision, ordered deterministically
    cards = snap["inbox"]
    assert len(cards) == 4
    required_fields = {
        "card_type",
        "episode",
        "principal",
        "role",
        "responsibility",
        "why_now",
        "summary",
        "risk",
        "authority",
        "status",
        "evidence_refs",
        "deadline",
    }
    for card in cards:
        assert set(card) >= required_fields
    # missing fields default to None; provided fields are carried through
    assert cards[0]["card_type"] == "decision"
    assert cards[0]["episode"] == "episode_ep1"
    assert cards[0]["principal"] == "principal:alice"
    assert cards[0]["role"] is None
    assert cards[0]["responsibility"] is None
    assert cards[0]["why_now"] is None
    assert cards[0]["summary"] == "approve rollout"
    assert cards[0]["risk"] == "low"
    assert cards[1]["why_now"] == "context"
    assert cards[2]["deadline"] == "2026-08-20"
    assert cards[2]["status"] == "pending"
    # envelope role context backfills card role/responsibility
    assert cards[3]["role"] == "role:reviewer"
    assert cards[3]["responsibility"] == "responsibility:review"


# ---------------------------------------------------------------------------
# 4. deterministic rebuild: two builds on the same ledger are identical
# ---------------------------------------------------------------------------


def test_deterministic_rebuild(broker: LedgerBroker) -> None:
    svc = SovereigntyService(broker)
    _assign(svc, "principal:alice", "role:reviewer", "Reviewer")
    _episode(
        broker,
        "Episode.Decision.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "summary": "decide X"},
        correlation_id="c1",
        idempotency_key="k1",
    )

    first = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    second = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    assert first == second


# ---------------------------------------------------------------------------
# 5. ledger untouched: count + hash chain identical before/after projection
# ---------------------------------------------------------------------------


def test_projection_never_mutates_ledger(broker: LedgerBroker) -> None:
    svc = SovereigntyService(broker)
    _assign(svc, "principal:alice", "role:reviewer", "Reviewer")
    _episode(
        broker,
        "Episode.FYI.v1",
        "episode_ep1",
        {"summary": "heads up"},
        correlation_id="c1",
        idempotency_key="k1",
    )

    before = _ledger_controls(broker)
    snap = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    after = _ledger_controls(broker)

    assert before["count"] == after["count"]
    assert before["chain"] == after["chain"]
    assert snap["controls"]["ledger_count_before"] == before["count"]
    assert snap["controls"]["ledger_count_after"] == after["count"]
    assert snap["controls"]["ledger_unchanged"] is True


# ---------------------------------------------------------------------------
# 5b. non-card chain members (EPISODE_REQUIRED_CLASSES) join their Episode but
#     never land in Inbox — the real W2-03 chain must stay visible to W2-04.
# ---------------------------------------------------------------------------


def test_non_card_members_aggregate_into_episode_only(broker: LedgerBroker) -> None:
    _episode(
        broker,
        "Decision.Policy.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "policy": "P1"},
        correlation_id="c1",
        idempotency_key="k1",
    )
    _episode(
        broker,
        "Action.Started.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "action": "run-check"},
        correlation_id="c2",
        idempotency_key="k2",
    )
    _episode(
        broker,
        "Episode.Decision.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "summary": "approve"},
        correlation_id="c3",
        idempotency_key="k3",
    )

    snap = build_episode_projection_snapshot(broker, principal_id="principal:alice")

    # all three rows aggregate into the episode (deterministic order)
    assert len(snap["episodes"]) == 1
    assert len(snap["episodes"][0]["contains_event_refs"]) == 3
    payloads = [env["payload"] for env in snap["episodes"][0]["contains_event_refs"]]
    assert any(p.get("policy") == "P1" for p in payloads)
    assert any(p.get("action") == "run-check" for p in payloads)

    # only the card reaches the inbox; non-card members do not
    assert len(snap["inbox"]) == 1
    assert snap["inbox"][0]["card_type"] == "decision"
    assert snap["inbox"][0]["summary"] == "approve"

    assert snap["controls"]["events_read"] == 3
    assert snap["controls"]["events_ignored"] == 0
    assert snap["controls"]["events_blocked"] == 0


# ---------------------------------------------------------------------------
# 6. malformed / missing / invalid rows -> stable blocked reasons (FakeBroker)
#    The projection must be defensive against bad rows without touching the
#    ledger (pure read path).
# ---------------------------------------------------------------------------


class _FakeBroker:
    """Minimal read-only broker surface: fixed rows + fixed integrity."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def read(self, from_sequence: int = 1, *, producer: str | None = None, **_: Any) -> list[dict[str, Any]]:
        rows = [r for r in self._rows if r["sequence"] >= from_sequence]
        if producer is not None:
            rows = [r for r in rows if r.get("producer") == producer]
        return rows

    def count(self) -> int:
        return len(self._rows)

    def last_sequence(self) -> int:
        return len(self._rows)

    def verify_chain(self, from_sequence: int = 1, **_: Any) -> dict[str, Any]:
        return {"ok": True, "total": len(self._rows), "first_bad_sequence": None, "error": None}

    def close(self) -> None:
        pass


def _fake_row(
    sequence: int, event_type: str, payload_json: str, *, episode_id: str | None
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "event_id": f"evt_{sequence:06d}",
        "event_type": event_type,
        "schema_version": "event-envelope/v1",
        "episode_id": episode_id,
        "principal_id": "principal:alice",
        "space_id": "episodes",
        "role_context_id": None,
        "responsibility_id": None,
        "mandate_id": None,
        "correlation_id": f"c{sequence}",
        "causation_id": None,
        "producer": "episode-ecos",
        "idempotency_key": f"k{sequence}",
        "occurred_at": "2026-08-11T00:00:00Z",
        "recorded_at": "2026-08-11T00:00:00Z",
        "privacy_class": "internal",
        "payload_json": payload_json,
        "evidence_uri": None,
        "previous_hash": f"prev-{sequence}",
        "event_hash": f"hash-{sequence}",
    }


def test_malformed_and_invalid_rows_blocked_with_stable_reason() -> None:
    fake = _FakeBroker(
        [
            # valid JSON but NOT an object -> malformed_payload
            _fake_row(1, "Episode.FYI.v1", "[]", episode_id="episode_ep1"),
            # mapping payload but no episode_id anywhere -> missing_episode_id
            _fake_row(2, "Episode.FYI.v1", '{"summary": "x"}', episode_id=None),
            # mapping payload but colon-scoped episode_id fails the M2 pattern
            _fake_row(
                3,
                "Episode.Decision.v1",
                '{"episode_id": "episode:bad", "summary": "x"}',
                episode_id="episode:bad",
            ),
        ]
    )
    snap = build_episode_projection_snapshot(fake, principal_id="principal:alice")

    assert snap["inbox"] == []
    assert snap["episodes"] == []
    assert [b["reason"] for b in snap["blocked"]] == [
        REASON_MALFORMED_PAYLOAD,
        REASON_MISSING_EPISODE_ID,
        REASON_INVALID_EPISODE_M2,
    ]
    assert snap["blocked"][0]["event_id"] == "evt_000001"
    assert snap["blocked"][0]["event_type"] == "Episode.FYI.v1"
    assert snap["blocked"][0]["sequence"] == 1

    # deterministic: second build produces the identical blocked entries
    snap2 = build_episode_projection_snapshot(fake, principal_id="principal:alice")
    assert snap2["blocked"] == snap["blocked"]


# ---------------------------------------------------------------------------
# 7. unknown event type -> ignored, not blocked, not counted into views
# ---------------------------------------------------------------------------


def test_unknown_event_type_ignored(broker: LedgerBroker) -> None:
    broker.append(
        "Some.Unrelated.Event.v1",
        producer="other-producer",
        principal_id="principal:alice",
        space_id="elsewhere",
        correlation_id="c1",
        idempotency_key="k1",
        payload={"x": 1},
    )
    snap = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    assert snap["episodes"] == []
    assert snap["inbox"] == []
    assert snap["blocked"] == []
    assert snap["controls"]["events_read"] == 1
    assert snap["controls"]["events_ignored"] == 1


# ---------------------------------------------------------------------------
# 8. from_path equivalent to broker-path build
# ---------------------------------------------------------------------------


def test_from_path_equivalence(broker: LedgerBroker, tmp_path) -> None:
    svc = SovereigntyService(broker)
    _assign(svc, "principal:alice", "role:reviewer", "Reviewer")
    _episode(
        broker,
        "Episode.Decision.v1",
        "episode_ep1",
        {"episode_id": "episode_ep1", "summary": "approve rollout"},
        correlation_id="c1",
        idempotency_key="k1",
    )
    db_path = tmp_path / "ledger.db"

    from_broker = build_episode_projection_snapshot(broker, principal_id="principal:alice")
    from_path = build_episode_projection_snapshot_from_path(db_path, principal_id="principal:alice")
    assert from_broker == from_path

    assert from_path["schema_version"] == "episode-projection/v1"
    assert len(from_path["episodes"]) == 1
    assert from_path["episodes"][0]["episode_id"] == "episode_ep1"
    assert len(from_path["role_portfolio"]["active_assignments"]) == 1
    assert from_path["blocked"] == []
