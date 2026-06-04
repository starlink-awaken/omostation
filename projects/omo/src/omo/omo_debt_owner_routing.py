from __future__ import annotations


LANE_PRIORITY = {
    "revalidate_now": 0,
    "schedule_now": 1,
    "escalate_now": 2,
    "continue_mitigation": 3,
    "watch_only": 4,
}

SEVERITY_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _normalize_owner(owner: object) -> str:
    return str(owner or "unowned")


def _priority_flags(
    entry: dict[str, object], escalation_threshold_days: int
) -> list[str]:
    flags: list[str] = []
    if entry.get("last_reviewed_at") is None:
        flags.append("initial_review_required")
    if entry.get("gate_level") == "gate":
        flags.append("gate_attention")
    if (
        entry.get("current_lane") == "revalidate_now"
        and int(entry.get("overdue_by", 0)) >= escalation_threshold_days
    ):
        flags.append("escalation_watch")
    if entry.get("current_lane") == "continue_mitigation":
        flags.append("active_mitigation")
    return flags


def _severity_rank(entry: dict[str, object]) -> int:
    return SEVERITY_PRIORITY.get(str(entry.get("severity")), 99)


def build_owner_routing_packet(action_packet: dict[str, object]) -> dict[str, object]:
    defaults = action_packet["defaults"]
    grouped: dict[str, list[dict[str, object]]] = {}

    for lane_name, entries in action_packet["lanes"].items():
        if lane_name not in LANE_PRIORITY:
            raise ValueError(f"unknown primary lane: {lane_name}")
        for entry in entries:
            owner = _normalize_owner(entry.get("owner"))
            grouped.setdefault(owner, []).append(
                {
                    **entry,
                    "primary_lane": lane_name,
                    "priority_flags": _priority_flags(
                        entry, int(defaults["escalation_threshold_days"])
                    ),
                }
            )

    owners: list[dict[str, object]] = []
    for owner, entries in grouped.items():
        ordered_entries = sorted(
            entries,
            key=lambda item: (
                LANE_PRIORITY[str(item["primary_lane"])],
                0 if item["gate_level"] == "gate" else 1,
                _severity_rank(item),
                -int(item.get("overdue_by", 0)),
                str(item["id"]),
            ),
        )
        lane_counts = {
            lane: sum(1 for item in ordered_entries if item["primary_lane"] == lane)
            for lane in LANE_PRIORITY
        }
        owners.append(
            {
                "owner": owner,
                "summary": {
                    "total_count": len(ordered_entries),
                    "lane_counts": lane_counts,
                },
                "entries": ordered_entries,
            }
        )

    owners.sort(
        key=lambda owner_packet: (
            0
            if any(
                "gate_attention" in item["priority_flags"]
                for item in owner_packet["entries"]
            )
            else 1,
            min(_severity_rank(item) for item in owner_packet["entries"]),
            -int(owner_packet["summary"]["total_count"]),
            -int(owner_packet["summary"]["lane_counts"]["revalidate_now"]),
            -max(int(item.get("overdue_by", 0)) for item in owner_packet["entries"]),
            str(owner_packet["owner"]),
        )
    )

    return {
        "generated_at": action_packet["generated_at"],
        "source_action_packet_ref": ".omo/debt/action-packet/current.yaml",
        "defaults": defaults,
        "owners": owners,
        "summary": {
            "owner_count": len(owners),
            "total_routed_items": sum(
                owner["summary"]["total_count"] for owner in owners
            ),
            "lane_counts": {
                lane: sum(owner["summary"]["lane_counts"][lane] for owner in owners)
                for lane in LANE_PRIORITY
            },
        },
    }
