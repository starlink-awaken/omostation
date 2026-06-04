from __future__ import annotations


_PROPOSAL_STATUS_ORDER = {"proposed": 0, "approved": 1, "verified": 2, "missing": 3}


def _ordered_tasks(tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        tasks,
        key=lambda item: (
            0 if item["blockers"] else 1,
            _PROPOSAL_STATUS_ORDER.get(str(item["proposal_status"]), 99),
            str(item["task_id"]),
        ),
    )


def build_promotion_approval_status_packet(
    *, generated_at: str, tasks: list[dict[str, object]]
) -> dict[str, object]:
    ordered = _ordered_tasks(tasks)
    return {
        "generated_at": generated_at,
        "approval_task_count": len(ordered),
        "requested_count": sum(
            1
            for entry in ordered
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1
            for entry in ordered
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "approved"
        ),
        "granted_count": sum(
            1 for entry in ordered if entry["approval_status"] == "granted"
        ),
        "tasks": ordered,
    }


def _operator_action(entry: dict[str, object]) -> str:
    if entry["proposal_status"] == "proposed":
        return "run governance approve"
    if entry["proposal_status"] == "approved":
        return "run governance apply"
    return "approval blocker cleared; check readiness"


def render_promotion_approval_status_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Promotion Approval Status",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Approval tasks: {packet['approval_task_count']}",
        f"Requested: {packet['requested_count']}",
        f"Approved pending apply: {packet['approved_pending_apply_count']}",
        f"Granted: {packet['granted_count']}",
    ]
    for entry in packet["tasks"]:
        lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"proposal_status={entry['proposal_status']}",
                f"approval_status={entry['approval_status']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
                f"action={_operator_action(entry)}",
            ]
        )
    return "\n".join(lines) + "\n"
