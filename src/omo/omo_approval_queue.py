from __future__ import annotations

_PROPOSAL_STATUS_ORDER = {"missing": 0, "proposed": 1, "approved": 2, "verified": 3}


def _entry_priority(entry: dict[str, object]) -> tuple[int, int, str]:
    next_action = str(entry.get("next_action", ""))
    if next_action == "request_approval":
        bucket = 0
    elif next_action == "governance_approve":
        bucket = 1
    elif next_action == "governance_apply":
        bucket = 2
    elif next_action == "promote_apply":
        bucket = 3
    else:
        bucket = 4
    proposal_status = _PROPOSAL_STATUS_ORDER.get(
        str(entry.get("proposal_status", "missing")), 99
    )
    return (bucket, proposal_status, str(entry.get("task_id", "")))


def build_approval_queue_packet(
    *, generated_at: str, tasks: list[dict[str, object]]
) -> dict[str, object]:
    ordered = sorted(tasks, key=_entry_priority)
    return {
        "generated_at": generated_at,
        "task_count": len(ordered),
        "approval_missing_count": sum(
            1 for entry in ordered if entry.get("approval_status") == "missing"
        ),
        "proposed_count": sum(
            1 for entry in ordered if entry.get("proposal_status") == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1
            for entry in ordered
            if entry.get("proposal_status") == "approved"
            and str(entry.get("approval_status")) in {"requested", "granted"}
        ),
        "ready_to_promote_count": sum(
            1 for entry in ordered if entry.get("next_action") == "promote_apply"
        ),
        "blocked_count": sum(1 for entry in ordered if entry.get("blockers")),
        "tasks": ordered,
    }


def render_approval_queue_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Approval Queue Status",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Task count: {packet['task_count']}",
        f"Approval missing: {packet['approval_missing_count']}",
        f"Proposed: {packet['proposed_count']}",
        f"Approved pending apply: {packet['approved_pending_apply_count']}",
        f"Ready to promote: {packet['ready_to_promote_count']}",
        f"Blocked: {packet['blocked_count']}",
    ]
    for entry in packet["tasks"]:
        lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"task_ref={entry['task_ref']}",
                f"phase={entry['phase'] if entry['phase'] is not None else 'n/a'}",
                f"approval_status={entry['approval_status']}",
                f"proposal_status={entry['proposal_status']}",
                f"next_action={entry['next_action']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
            ]
        )
    return "\n".join(lines) + "\n"
