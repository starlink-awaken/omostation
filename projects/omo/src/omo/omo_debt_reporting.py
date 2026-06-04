from __future__ import annotations


def _rate(numerator: int, denominator: int, *, empty_value: float) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator


def _owner_rollup(owner_packet: dict[str, object]) -> dict[str, object]:
    entries = owner_packet["entries"]
    state_counts = dict(owner_packet["state_counts"])
    gate_item_count = sum(1 for entry in entries if entry.get("gate_level") == "gate")
    approved_gate_item_count = sum(
        1
        for entry in entries
        if entry.get("gate_level") == "gate" and entry.get("campaign_state") != "pending_approval"
    )
    executed_item_count = int(state_counts.get("executed", 0))
    item_count = int(owner_packet["item_count"])
    return {
        "owner": owner_packet["owner"],
        "item_count": item_count,
        "state_counts": state_counts,
        "gate_item_count": gate_item_count,
        "approved_gate_item_count": approved_gate_item_count,
        "approval_coverage_rate": _rate(approved_gate_item_count, gate_item_count, empty_value=1.0),
        "executed_item_count": executed_item_count,
        "execution_completion_rate": _rate(executed_item_count, item_count, empty_value=0.0),
    }


def build_reporting_packet(campaign_packet: dict[str, object]) -> dict[str, object]:
    owners = [_owner_rollup(owner_packet) for owner_packet in campaign_packet["owners"]]
    summary = campaign_packet["summary"]
    gate_item_count = sum(owner["gate_item_count"] for owner in owners)
    approved_gate_item_count = sum(owner["approved_gate_item_count"] for owner in owners)
    executed_item_count = sum(owner["executed_item_count"] for owner in owners)
    total_items = int(summary["total_items"])
    return {
        "generated_at": campaign_packet["generated_at"],
        "dispatch_run_ref": campaign_packet["dispatch_run_ref"],
        "run_stamp": campaign_packet["run_stamp"],
        "summary": {
            "owner_count": int(summary["owner_count"]),
            "total_items": total_items,
            "state_counts": dict(summary["state_counts"]),
            "gate_item_count": gate_item_count,
            "approved_gate_item_count": approved_gate_item_count,
            "approval_coverage_rate": _rate(approved_gate_item_count, gate_item_count, empty_value=1.0),
            "executed_item_count": executed_item_count,
            "execution_completion_rate": _rate(executed_item_count, total_items, empty_value=0.0),
        },
        "owners": owners,
    }


def render_reporting_markdown(packet: dict[str, object]) -> str:
    summary = packet["summary"]
    lines = [
        "# Debt Reporting Packet",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Dispatch run: {packet['dispatch_run_ref']}",
        f"Approval coverage: {summary['approval_coverage_rate']:.2f}",
        f"Execution completion: {summary['execution_completion_rate']:.2f}",
        "",
    ]
    for owner in packet["owners"]:
        lines.extend(
            [
                f"## Owner: {owner['owner']}",
                "",
                (
                    f"item_count={owner['item_count']}, "
                    f"gate_items={owner['gate_item_count']}, "
                    f"approved_gate_items={owner['approved_gate_item_count']}, "
                    f"executed_items={owner['executed_item_count']}"
                ),
                "",
            ]
        )
    return "\n".join(lines)
