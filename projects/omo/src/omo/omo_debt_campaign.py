from __future__ import annotations

from .omo_debt_approval import dispatch_entry_requires_approval
from .omo_debt_execution import run_slug_from_ref


def _empty_counts() -> dict[str, int]:
    return {"pending_approval": 0, "ready_to_execute": 0, "executed": 0}


def _campaign_state(
    entry: dict[str, object],
    has_matching_approval: bool,
    execution_record_ref: str | None,
) -> str:
    if execution_record_ref:
        return "executed"
    if dispatch_entry_requires_approval(entry) and not has_matching_approval:
        return "pending_approval"
    return "ready_to_execute"


def build_campaign_packet(
    run_packet: dict[str, object],
    dispatch_run_ref: str,
    generated_at: str,
    approval_lookup: dict[str, bool],
    execution_lookup: dict[str, str],
) -> dict[str, object]:
    run_stamp = run_slug_from_ref(dispatch_run_ref)
    summary_counts = _empty_counts()
    owners: list[dict[str, object]] = []

    for owner_packet in run_packet["owners"]:
        owner_counts = _empty_counts()
        entries: list[dict[str, object]] = []
        for entry in owner_packet["entries"]:
            item_id = str(entry["id"])
            execution_record_ref = execution_lookup.get(item_id)
            campaign_state = _campaign_state(
                entry, approval_lookup.get(item_id, False), execution_record_ref
            )
            owner_counts[campaign_state] += 1
            summary_counts[campaign_state] += 1
            packet_entry = dict(entry)
            packet_entry["campaign_state"] = campaign_state
            packet_entry["dispatch_run_ref"] = dispatch_run_ref
            if execution_record_ref:
                packet_entry["execution_record_ref"] = execution_record_ref
            entries.append(packet_entry)
        owners.append(
            {
                "owner": owner_packet["owner"],
                "item_count": len(entries),
                "state_counts": owner_counts,
                "entries": entries,
            }
        )

    return {
        "generated_at": generated_at,
        "dispatch_run_ref": dispatch_run_ref,
        "run_stamp": run_stamp,
        "source_dispatch_ref": dispatch_run_ref,
        "summary": {
            "owner_count": len(owners),
            "total_items": sum(owner["item_count"] for owner in owners),
            "state_counts": summary_counts,
        },
        "owners": owners,
    }


def render_campaign_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Campaign Packet",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Dispatch run: {packet['dispatch_run_ref']}",
        (
            "State counts: "
            f"pending_approval={packet['summary']['state_counts']['pending_approval']}, "
            f"ready_to_execute={packet['summary']['state_counts']['ready_to_execute']}, "
            f"executed={packet['summary']['state_counts']['executed']}"
        ),
        "",
    ]
    for owner in packet["owners"]:
        lines.extend([f"## Owner: {owner['owner']}", ""])
        for state, title in [
            ("pending_approval", "Pending Approval"),
            ("ready_to_execute", "Ready To Execute"),
            ("executed", "Executed"),
        ]:
            state_entries = [
                entry for entry in owner["entries"] if entry["campaign_state"] == state
            ]
            if not state_entries:
                continue
            lines.extend([f"### {title}", ""])
            for entry in state_entries:
                lines.append(f"- `{entry['id']}` — `{entry['command']}`")
            lines.append("")
    return "\n".join(lines)
