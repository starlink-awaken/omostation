from __future__ import annotations

from datetime import datetime, timedelta


def _schedule_command(item_id: str, now: str, review_window_days: int) -> str:
    next_review = (
        datetime.fromisoformat(now.replace("Z", "+00:00"))
        + timedelta(days=review_window_days)
    ).isoformat()
    next_review = next_review.replace("+00:00", "Z")
    return f"python3 scripts/omo_debt.py schedule --omo-dir .omo --id {item_id} --next-review-at {next_review}"


def _schedule_command_template(item_id: str) -> str:
    return f"python3 scripts/omo_debt.py schedule --omo-dir .omo --id {item_id} --next-review-at <NEXT_REVIEW_AT>"


def _revalidate_command_template(item_id: str) -> str:
    return f"python3 scripts/omo_debt.py revalidate --omo-dir .omo --id {item_id} --reviewed-at <RUN_AT>"


def _revalidate_shell_command(item_id: str) -> str:
    return (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo "
        f"--id {item_id} --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    )


def _escalate_command(item_id: str) -> str:
    return f"python3 scripts/omo_debt.py escalate --omo-dir .omo --id {item_id} --gate-level gate"


def build_action_packet(review_queue: dict[str, object], now: str) -> dict[str, object]:
    defaults = review_queue["defaults"]
    review_window_days = int(defaults["review_window_days"])
    escalation_ids = {entry["id"] for entry in review_queue["escalation_candidates"]}
    lanes = {
        "revalidate_now": [],
        "schedule_now": [],
        "escalate_now": [],
        "continue_mitigation": [],
        "watch_only": [],
    }

    for entry in review_queue["unscheduled"]:
        lanes["schedule_now"].append(
            {
                **entry,
                "current_lane": "schedule_now",
                "recommended_action": "schedule",
                "reason": "missing_next_review_at",
                "command_template": _schedule_command_template(entry["id"]),
                "shell_command": _schedule_command(
                    entry["id"], now, review_window_days
                ),
                "suggested_command": _schedule_command(
                    entry["id"], now, review_window_days
                ),
            }
        )

    for entry in review_queue["due_now"]:
        if entry["stale_evidence"]:
            lanes["revalidate_now"].append(
                {
                    **entry,
                    "current_lane": "revalidate_now",
                    "recommended_action": "revalidate",
                    "reason": "stale_due_item",
                    "command_template": _revalidate_command_template(entry["id"]),
                    "shell_command": _revalidate_shell_command(entry["id"]),
                    "suggested_command": _revalidate_shell_command(entry["id"]),
                }
            )
            continue
        if entry["id"] in escalation_ids and entry["gate_level"] != "gate":
            lanes["escalate_now"].append(
                {
                    **entry,
                    "current_lane": "escalate_now",
                    "recommended_action": "escalate",
                    "reason": "escalation_candidate",
                    "command_template": _escalate_command(entry["id"]),
                    "shell_command": _escalate_command(entry["id"]),
                    "suggested_command": _escalate_command(entry["id"]),
                }
            )
            continue
        if entry["lifecycle_state"] in {"in_progress", "mitigated"}:
            lanes["continue_mitigation"].append(
                {
                    **entry,
                    "current_lane": "continue_mitigation",
                    "recommended_action": "continue_mitigation",
                    "reason": "active_mitigation_due",
                    "command_template": "manual: continue mitigation with <OWNER>",
                    "shell_command": f"manual: continue mitigation with {entry['owner']}",
                    "suggested_command": f"manual: continue mitigation with {entry['owner']}",
                }
            )
            continue
        lanes["watch_only"].append(
            {
                **entry,
                "current_lane": "watch_only",
                "recommended_action": "watch",
                "reason": "due_without_stronger_action",
                "command_template": "manual: keep item on review radar",
                "shell_command": "manual: keep item on review radar",
                "suggested_command": "manual: keep item on review radar",
            }
        )

    for entry in review_queue["upcoming"]:
        lanes["watch_only"].append(
            {
                **entry,
                "current_lane": "watch_only",
                "recommended_action": "watch",
                "reason": "upcoming_not_due",
                "command_template": "manual: keep item on review radar",
                "shell_command": "manual: keep item on review radar",
                "suggested_command": "manual: keep item on review radar",
            }
        )

    return {
        "generated_at": now,
        "defaults": defaults,
        "lanes": lanes,
        "summary": {lane: len(entries) for lane, entries in lanes.items()},
    }
