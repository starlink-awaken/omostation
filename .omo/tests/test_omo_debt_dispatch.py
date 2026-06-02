from __future__ import annotations

import pytest

from scripts.omo_debt_dispatch import build_dispatch_packet


def _owner_routing() -> dict[str, object]:
    return {
        "generated_at": "2026-06-10T00:00:00Z",
        "source_action_packet_ref": ".omo/debt/action-packet/current.yaml",
        "defaults": {
            "review_window_days": 7,
            "escalation_threshold_days": 3,
        },
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "summary": {
                    "total_count": 2,
                    "lane_counts": {
                        "revalidate_now": 1,
                        "schedule_now": 1,
                        "escalate_now": 0,
                        "continue_mitigation": 0,
                        "watch_only": 0,
                    },
                },
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "title": "SharedBrain decomposition remains partially governed",
                        "owner": "sharedbrain-governance",
                        "primary_lane": "revalidate_now",
                        "recommended_action": "revalidate",
                        "reason": "stale_due_item",
                        "priority_flags": ["gate_attention", "escalation_watch"],
                        "command_template": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at <RUN_AT>",
                        "shell_command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
                        "suggested_command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
                        "next_review_at": "2026-06-07T00:00:00Z",
                        "last_reviewed_at": "2026-06-02T00:00:00Z",
                        "overdue_by": 3,
                        "gate_level": "gate",
                        "severity": "critical",
                    },
                    {
                        "id": "SB_ROOT_CLEANUP",
                        "title": "Root SharedBrain shell cleanup remains deferred",
                        "owner": "sharedbrain-governance",
                        "primary_lane": "schedule_now",
                        "recommended_action": "schedule",
                        "reason": "missing_next_review_at",
                        "priority_flags": [],
                        "command_template": "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at <NEXT_REVIEW_AT>",
                        "shell_command": "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-17T00:00:00Z",
                        "suggested_command": "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-17T00:00:00Z",
                        "next_review_at": None,
                        "last_reviewed_at": "2026-06-02T00:00:00Z",
                        "overdue_by": 0,
                        "gate_level": "none",
                        "severity": "low",
                    },
                ],
            },
        ],
        "summary": {
            "owner_count": 1,
            "total_routed_items": 2,
            "lane_counts": {
                "revalidate_now": 1,
                "schedule_now": 1,
                "escalate_now": 0,
                "continue_mitigation": 0,
                "watch_only": 0,
            },
        },
    }


def test_build_dispatch_packet_freezes_commands_and_adds_run_ref() -> None:
    packet = build_dispatch_packet(_owner_routing(), dispatched_at="2026-06-10T00:00:00Z")

    assert packet["dispatched_at"] == "2026-06-10T00:00:00Z"
    assert packet["source_owner_routing_ref"] == ".omo/debt/owner-routing/current.yaml"
    assert packet["source_owner_routing_generated_at"] == "2026-06-10T00:00:00Z"
    assert packet["latest_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    first_entry = packet["owners"][0]["entries"][0]
    assert first_entry["command"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION "
        "--reviewed-at 2026-06-10T00:00:00Z "
        "--dispatch-run-ref .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    )
    assert "command_template" not in first_entry
    assert "shell_command" not in first_entry
    assert "suggested_command" not in first_entry
    assert first_entry["priority_flags"] == ["gate_attention", "escalation_watch"]


def test_build_dispatch_packet_uses_shell_command_for_non_revalidate_lanes() -> None:
    packet = build_dispatch_packet(_owner_routing(), dispatched_at="2026-06-10T00:00:00Z")

    schedule_entry = packet["owners"][0]["entries"][1]
    assert schedule_entry["command"] == (
        "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-17T00:00:00Z"
    )


def test_build_dispatch_packet_rejects_missing_or_unresolved_command_metadata() -> None:
    broken = _owner_routing()
    broken["owners"][0]["entries"][0]["command_template"] = (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION "
        "--reviewed-at <RUN_AT> $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    )

    with pytest.raises(ValueError, match="unresolved or unsafe dispatch command"):
        build_dispatch_packet(broken, dispatched_at="2026-06-10T00:00:00Z")
