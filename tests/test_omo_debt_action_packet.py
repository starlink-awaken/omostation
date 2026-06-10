from __future__ import annotations

from omo.omo_debt_action_packet import build_action_packet


def _entry(
    item_id: str,
    *,
    lifecycle_state: str = "scheduled",
    gate_level: str = "none",
    stale_evidence: bool = False,
    overdue_by: int = 0,
    owner: str = "omo-governance",
    next_review_at: str | None = "2026-06-10T00:00:00Z",
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": f"{item_id} title",
        "owner": owner,
        "severity": "high",
        "dimension": "governance_process",
        "subdimension": "cadence",
        "lifecycle_state": lifecycle_state,
        "gate_level": gate_level,
        "next_review_at": next_review_at,
        "last_reviewed_at": "2026-06-02T00:00:00Z",
        "stale_evidence": stale_evidence,
        "overdue_by": overdue_by,
        "affected_roots": [".omo"],
        "priority_reason": "due_now",
    }


def test_build_action_packet_routes_entries_into_primary_lanes() -> None:
    review_queue = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {
            "review_window_days": 7,
            "escalation_threshold_days": 3,
        },
        "due_now": [
            _entry("REVALIDATE", stale_evidence=True, overdue_by=1),
            _entry("ESCALATE", gate_level="watchlist", stale_evidence=False, overdue_by=4),
            _entry("MITIGATE", lifecycle_state="in_progress", stale_evidence=False, overdue_by=1),
        ],
        "upcoming": [
            _entry("WATCH", overdue_by=0, next_review_at="2026-06-12T00:00:00Z"),
        ],
        "escalation_candidates": [
            _entry("REVALIDATE", stale_evidence=True, overdue_by=1),
            _entry("ESCALATE", gate_level="watchlist", stale_evidence=False, overdue_by=4),
        ],
        "unscheduled": [
            _entry("SCHEDULE", next_review_at=None),
        ],
        "summary": {},
    }

    packet = build_action_packet(review_queue, now="2026-06-10T00:00:00Z")

    assert [entry["id"] for entry in packet["lanes"]["revalidate_now"]] == ["REVALIDATE"]
    assert [entry["id"] for entry in packet["lanes"]["schedule_now"]] == ["SCHEDULE"]
    assert [entry["id"] for entry in packet["lanes"]["escalate_now"]] == ["ESCALATE"]
    assert [entry["id"] for entry in packet["lanes"]["continue_mitigation"]] == ["MITIGATE"]
    assert [entry["id"] for entry in packet["lanes"]["watch_only"]] == ["WATCH"]
    assert packet["lanes"]["revalidate_now"][0]["command_template"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id REVALIDATE --reviewed-at <RUN_AT>"
    )
    assert packet["lanes"]["revalidate_now"][0]["shell_command"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id REVALIDATE --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    )
    assert packet["lanes"]["revalidate_now"][0]["suggested_command"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id REVALIDATE --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    )
    assert packet["lanes"]["schedule_now"][0]["command_template"] == (
        "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SCHEDULE --next-review-at <NEXT_REVIEW_AT>"
    )
    assert packet["lanes"]["schedule_now"][0]["shell_command"] == (
        "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SCHEDULE --next-review-at 2026-06-17T00:00:00Z"
    )
    assert packet["lanes"]["schedule_now"][0]["suggested_command"] == (
        "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SCHEDULE --next-review-at 2026-06-17T00:00:00Z"
    )
    assert packet["lanes"]["continue_mitigation"][0]["shell_command"] == (
        "manual: continue mitigation with omo-governance"
    )


def test_build_action_packet_keeps_revalidate_above_escalate_for_stale_items() -> None:
    review_queue = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {
            "review_window_days": 7,
            "escalation_threshold_days": 3,
        },
        "due_now": [
            _entry("STALE_GATE", gate_level="watchlist", stale_evidence=True, overdue_by=5),
        ],
        "upcoming": [],
        "escalation_candidates": [
            _entry("STALE_GATE", gate_level="watchlist", stale_evidence=True, overdue_by=5),
        ],
        "unscheduled": [],
        "summary": {},
    }

    packet = build_action_packet(review_queue, now="2026-06-10T00:00:00Z")

    assert [entry["id"] for entry in packet["lanes"]["revalidate_now"]] == ["STALE_GATE"]
    assert packet["lanes"]["escalate_now"] == []
