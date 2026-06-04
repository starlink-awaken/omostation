from __future__ import annotations


def _delta_metric(
    latest: int | float, prior: int | float | None
) -> dict[str, int | float | None]:
    if prior is None:
        return {"latest": latest, "prior": None, "delta": None}
    return {"latest": latest, "prior": prior, "delta": latest - prior}


def _summary_diff(
    latest_summary: dict[str, object], prior_summary: dict[str, object] | None
) -> dict[str, object]:
    prior_state_counts = prior_summary["state_counts"] if prior_summary else None
    return {
        "total_items": _delta_metric(
            int(latest_summary["total_items"]),
            int(prior_summary["total_items"]) if prior_summary else None,
        ),
        "state_counts": {
            "pending_approval": _delta_metric(
                int(latest_summary["state_counts"]["pending_approval"]),
                int(prior_state_counts["pending_approval"])
                if prior_state_counts
                else None,
            ),
            "ready_to_execute": _delta_metric(
                int(latest_summary["state_counts"]["ready_to_execute"]),
                int(prior_state_counts["ready_to_execute"])
                if prior_state_counts
                else None,
            ),
            "executed": _delta_metric(
                int(latest_summary["state_counts"]["executed"]),
                int(prior_state_counts["executed"]) if prior_state_counts else None,
            ),
        },
        "gate_item_count": _delta_metric(
            int(latest_summary["gate_item_count"]),
            int(prior_summary["gate_item_count"]) if prior_summary else None,
        ),
        "approved_gate_item_count": _delta_metric(
            int(latest_summary["approved_gate_item_count"]),
            int(prior_summary["approved_gate_item_count"]) if prior_summary else None,
        ),
        "approval_coverage_rate": _delta_metric(
            float(latest_summary["approval_coverage_rate"]),
            float(prior_summary["approval_coverage_rate"]) if prior_summary else None,
        ),
        "executed_item_count": _delta_metric(
            int(latest_summary["executed_item_count"]),
            int(prior_summary["executed_item_count"]) if prior_summary else None,
        ),
        "execution_completion_rate": _delta_metric(
            float(latest_summary["execution_completion_rate"]),
            float(prior_summary["execution_completion_rate"])
            if prior_summary
            else None,
        ),
    }


def _owner_diff_entry(
    owner: str,
    latest_owner: dict[str, object],
    prior_owner: dict[str, object],
) -> dict[str, object]:
    latest_state_counts = latest_owner["state_counts"]
    prior_state_counts = prior_owner["state_counts"]
    return {
        "owner": owner,
        "item_count": _delta_metric(
            int(latest_owner["item_count"]), int(prior_owner["item_count"])
        ),
        "state_counts": {
            "pending_approval": _delta_metric(
                int(latest_state_counts["pending_approval"]),
                int(prior_state_counts["pending_approval"]),
            ),
            "ready_to_execute": _delta_metric(
                int(latest_state_counts["ready_to_execute"]),
                int(prior_state_counts["ready_to_execute"]),
            ),
            "executed": _delta_metric(
                int(latest_state_counts["executed"]),
                int(prior_state_counts["executed"]),
            ),
        },
        "gate_item_count": _delta_metric(
            int(latest_owner["gate_item_count"]), int(prior_owner["gate_item_count"])
        ),
        "approved_gate_item_count": _delta_metric(
            int(latest_owner["approved_gate_item_count"]),
            int(prior_owner["approved_gate_item_count"]),
        ),
        "approval_coverage_rate": _delta_metric(
            float(latest_owner["approval_coverage_rate"]),
            float(prior_owner["approval_coverage_rate"]),
        ),
        "executed_item_count": _delta_metric(
            int(latest_owner["executed_item_count"]),
            int(prior_owner["executed_item_count"]),
        ),
        "execution_completion_rate": _delta_metric(
            float(latest_owner["execution_completion_rate"]),
            float(prior_owner["execution_completion_rate"]),
        ),
    }


def _owners_diff(
    latest_owners: list[dict[str, object]], prior_owners: list[dict[str, object]]
) -> dict[str, object]:
    latest_by_owner = {str(owner["owner"]): owner for owner in latest_owners}
    prior_by_owner = {str(owner["owner"]): owner for owner in prior_owners}
    shared_names = sorted(latest_by_owner.keys() & prior_by_owner.keys())
    added_names = sorted(latest_by_owner.keys() - prior_by_owner.keys())
    removed_names = sorted(prior_by_owner.keys() - latest_by_owner.keys())
    return {
        "compared": [
            _owner_diff_entry(
                owner_name, latest_by_owner[owner_name], prior_by_owner[owner_name]
            )
            for owner_name in shared_names
        ],
        "added": [{"owner": owner_name} for owner_name in added_names],
        "removed": [{"owner": owner_name} for owner_name in removed_names],
    }


def build_reporting_diff_packet(
    *,
    generated_at: str,
    latest_packet: dict[str, object],
    prior_packet: dict[str, object] | None,
) -> dict[str, object]:
    latest_summary = latest_packet["summary"]
    prior_summary = prior_packet["summary"] if prior_packet else None
    owners = (
        None
        if prior_packet is None
        else _owners_diff(latest_packet["owners"], prior_packet["owners"])
    )
    return {
        "generated_at": generated_at,
        "diff_status": "diff_available" if prior_packet else "no_prior_run",
        "latest_run_stamp": latest_packet["run_stamp"],
        "prior_run_stamp": prior_packet["run_stamp"] if prior_packet else None,
        "latest_dispatch_run_ref": latest_packet["dispatch_run_ref"],
        "prior_dispatch_run_ref": prior_packet["dispatch_run_ref"]
        if prior_packet
        else None,
        "summary_diff": _summary_diff(latest_summary, prior_summary),
        "owners": owners,
    }


def render_reporting_diff_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Diff",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Diff status: {packet['diff_status']}",
        f"Latest run: {packet['latest_run_stamp']}",
        f"Prior run: {packet['prior_run_stamp'] or 'none'}",
        "",
    ]
    if packet["diff_status"] == "no_prior_run":
        lines.extend(["Prior baseline not established yet.", ""])
    for field, payload in packet["summary_diff"].items():
        if field == "state_counts":
            lines.append("## state_counts")
            lines.append("")
            for state_name, state_payload in payload.items():
                lines.append(
                    f"{state_name}: latest={state_payload['latest']}, prior={state_payload['prior']}, delta={state_payload['delta']}"
                )
            lines.append("")
            continue
        lines.append(
            f"{field}: latest={payload['latest']}, prior={payload['prior']}, delta={payload['delta']}"
        )
    if packet["owners"] is not None:
        lines.extend(["", "## Owner Diff", "", "### Shared owners", ""])
        compared = packet["owners"]["compared"]
        if compared:
            for owner in compared:
                lines.extend(
                    [
                        f"#### {owner['owner']}",
                        "",
                        f"- item_count: latest={owner['item_count']['latest']}, prior={owner['item_count']['prior']}, delta={owner['item_count']['delta']}",
                        f"- pending_approval: latest={owner['state_counts']['pending_approval']['latest']}, prior={owner['state_counts']['pending_approval']['prior']}, delta={owner['state_counts']['pending_approval']['delta']}",
                        f"- ready_to_execute: latest={owner['state_counts']['ready_to_execute']['latest']}, prior={owner['state_counts']['ready_to_execute']['prior']}, delta={owner['state_counts']['ready_to_execute']['delta']}",
                        f"- executed: latest={owner['state_counts']['executed']['latest']}, prior={owner['state_counts']['executed']['prior']}, delta={owner['state_counts']['executed']['delta']}",
                        f"- gate_item_count: latest={owner['gate_item_count']['latest']}, prior={owner['gate_item_count']['prior']}, delta={owner['gate_item_count']['delta']}",
                        f"- approved_gate_item_count: latest={owner['approved_gate_item_count']['latest']}, prior={owner['approved_gate_item_count']['prior']}, delta={owner['approved_gate_item_count']['delta']}",
                        f"- approval_coverage_rate: latest={owner['approval_coverage_rate']['latest']}, prior={owner['approval_coverage_rate']['prior']}, delta={owner['approval_coverage_rate']['delta']}",
                        f"- executed_item_count: latest={owner['executed_item_count']['latest']}, prior={owner['executed_item_count']['prior']}, delta={owner['executed_item_count']['delta']}",
                        f"- execution_completion_rate: latest={owner['execution_completion_rate']['latest']}, prior={owner['execution_completion_rate']['prior']}, delta={owner['execution_completion_rate']['delta']}",
                        "",
                    ]
                )
        else:
            lines.extend(["- none", ""])
        if packet["owners"]["added"]:
            lines.extend(["### Added owners", ""])
            lines.extend(
                [f"- `{entry['owner']}`" for entry in packet["owners"]["added"]]
            )
            lines.append("")
        if packet["owners"]["removed"]:
            lines.extend(["### Removed owners", ""])
            lines.extend(
                [f"- `{entry['owner']}`" for entry in packet["owners"]["removed"]]
            )
            lines.append("")
    return "\n".join(lines)
