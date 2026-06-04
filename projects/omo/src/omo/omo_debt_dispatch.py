from __future__ import annotations


def _run_slug(dispatched_at: str) -> str:
    return dispatched_at.replace(":", "-")


def _freeze_command(entry: dict[str, object], dispatched_at: str) -> str:
    entry_id = str(entry.get("id") or "<unknown>")
    lane = str(entry.get("primary_lane") or "")
    template = str(entry.get("command_template") or "")
    shell_command = str(entry.get("shell_command") or "")
    run_ref = f".omo/debt/dispatch/runs/{_run_slug(dispatched_at)}.yaml"

    if not template and not shell_command:
        raise ValueError(f"missing command metadata for {entry_id}")

    if lane == "revalidate_now":
        if "<RUN_AT>" not in template:
            raise ValueError(f"missing <RUN_AT> template for {entry_id}")
        command = template.replace("<RUN_AT>", dispatched_at)
        if "<RUN_AT>" in command or "$(" in command:
            raise ValueError(f"unresolved or unsafe dispatch command for {entry_id}")
        return f"{command} --dispatch-run-ref {run_ref}"

    if not shell_command:
        raise ValueError(f"missing shell_command for {entry_id}")
    return shell_command


def _dispatch_entry(entry: dict[str, object], dispatched_at: str) -> dict[str, object]:
    dispatch_entry = dict(entry)
    dispatch_entry["command"] = _freeze_command(entry, dispatched_at)
    dispatch_entry.pop("command_template", None)
    dispatch_entry.pop("shell_command", None)
    dispatch_entry.pop("suggested_command", None)
    return dispatch_entry


def build_dispatch_packet(owner_routing: dict[str, object], dispatched_at: str) -> dict[str, object]:
    generated_at = owner_routing.get("generated_at")
    owners = owner_routing.get("owners")
    summary = owner_routing.get("summary")

    if not generated_at:
        raise ValueError("owner routing packet missing generated_at")
    if not isinstance(owners, list) or not isinstance(summary, dict):
        raise ValueError("owner routing packet missing owners or summary")

    dispatch_owners: list[dict[str, object]] = []
    for owner_packet in owners:
        entries = [_dispatch_entry(entry, dispatched_at) for entry in owner_packet["entries"]]
        dispatch_owners.append(
            {
                "owner": owner_packet["owner"],
                "dispatched_at": dispatched_at,
                "item_count": len(entries),
                "summary": owner_packet["summary"],
                "entries": entries,
            }
        )

    return {
        "dispatched_at": dispatched_at,
        "source_owner_routing_ref": ".omo/debt/owner-routing/current.yaml",
        "source_owner_routing_generated_at": generated_at,
        "latest_run_ref": f".omo/debt/dispatch/runs/{_run_slug(dispatched_at)}.yaml",
        "owners": dispatch_owners,
        "summary": {
            "owner_count": len(dispatch_owners),
            "total_dispatched_items": sum(owner["item_count"] for owner in dispatch_owners),
            "lane_counts": dict(summary["lane_counts"]),
        },
    }
