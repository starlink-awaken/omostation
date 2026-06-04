from __future__ import annotations

import pytest

from scripts.omo_debt_owner_routing import build_owner_routing_packet


def _entry(
    item_id: str,
    *,
    owner: str,
    primary_lane: str = "revalidate_now",
    recommended_action: str = "revalidate",
    reason: str = "stale_due_item",
    severity: str = "high",
    gate_level: str = "none",
    overdue_by: int = 0,
    last_reviewed_at: str | None = "2026-06-02T00:00:00Z",
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": f"{item_id} title",
        "owner": owner,
        "current_lane": primary_lane,
        "recommended_action": recommended_action,
        "reason": reason,
        "severity": severity,
        "gate_level": gate_level,
        "next_review_at": "2026-06-10T00:00:00Z",
        "last_reviewed_at": last_reviewed_at,
        "stale_evidence": True,
        "overdue_by": overdue_by,
        "command_template": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at <RUN_AT>",
        "shell_command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id ITEM --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
    }


def test_build_owner_routing_groups_entries_by_owner_and_sets_flags() -> None:
    action_packet = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {"review_window_days": 7, "escalation_threshold_days": 3},
        "lanes": {
            "revalidate_now": [
                _entry("A_GATE", owner="sharedbrain-governance", severity="critical", gate_level="gate", overdue_by=4),
                _entry("A_FIRST", owner="omo-governance", overdue_by=2, last_reviewed_at=None),
            ],
            "schedule_now": [
                _entry(
                    "B_SCHEDULE",
                    owner="commerce-governance",
                    primary_lane="schedule_now",
                    recommended_action="schedule",
                    reason="missing_next_review_at",
                ),
            ],
            "escalate_now": [],
            "continue_mitigation": [
                _entry(
                    "C_MITIGATE",
                    owner="omo-governance",
                    primary_lane="continue_mitigation",
                    recommended_action="continue_mitigation",
                    reason="active_mitigation_due",
                ),
            ],
            "watch_only": [],
        },
        "summary": {},
    }

    packet = build_owner_routing_packet(action_packet)

    assert [owner["owner"] for owner in packet["owners"]] == [
        "sharedbrain-governance",
        "omo-governance",
        "commerce-governance",
    ]
    assert packet["owners"][0]["entries"][0]["priority_flags"] == ["gate_attention", "escalation_watch"]
    assert packet["owners"][1]["entries"][0]["priority_flags"] == ["initial_review_required"]
    assert packet["owners"][1]["entries"][1]["priority_flags"] == ["active_mitigation"]
    assert packet["summary"] == {
        "owner_count": 3,
        "total_routed_items": 4,
        "lane_counts": {
            "revalidate_now": 2,
            "schedule_now": 1,
            "escalate_now": 0,
            "continue_mitigation": 1,
            "watch_only": 0,
        },
    }


def test_build_owner_routing_normalizes_ownerless_entries_and_rejects_unknown_lanes() -> None:
    action_packet = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {"review_window_days": 7, "escalation_threshold_days": 3},
        "lanes": {
            "revalidate_now": [_entry("UNOWNED", owner="")],
            "schedule_now": [],
            "escalate_now": [],
            "continue_mitigation": [],
            "watch_only": [],
        },
        "summary": {},
    }

    packet = build_owner_routing_packet(action_packet)

    assert packet["owners"][0]["owner"] == "unowned"
    assert packet["owners"][0]["summary"]["lane_counts"]["revalidate_now"] == 1

    broken_packet = {
        **action_packet,
        "lanes": {
            **action_packet["lanes"],
            "mystery_lane": [_entry("BROKEN", owner="omo-governance")],
        },
    }

    with pytest.raises(ValueError, match="unknown primary lane"):
        build_owner_routing_packet(broken_packet)
