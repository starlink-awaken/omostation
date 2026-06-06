from __future__ import annotations
from pathlib import Path

from .omo_debt_campaign import render_campaign_markdown
from .omo_debt_reporting import render_reporting_markdown
from .omo_debt_reporting_diff import render_reporting_diff_markdown
from .omo_debt_reporting_history import render_reporting_history_markdown
from .omo_debt_reporting_trend import render_reporting_trend_markdown
from .omo_debt_execution import execution_record_path, run_slug_from_ref

def _render_section(title: str, item_ids: list[str]) -> str:
    lines = [f"## {title}", ""]
    if item_ids:
        lines.extend([f"- `{item_id}`" for item_id in item_ids])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_queue_section(
    title: str, entries: list[dict[str, object]], reason_key: str
) -> str:
    lines = [f"## {title}", ""]
    if entries:
        for entry in entries:
            reason = entry.get(reason_key, "n/a")
            next_review = entry.get("next_review_at") or "unscheduled"
            lines.append(f"- `{entry['id']}` — {reason} ({next_review})")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)

def write_dashboard(
    omo_dir: Path, metrics, review_queue: dict[str, object], now: str, _write_yaml
) -> None:
    due_now = review_queue["due_now"]
    upcoming = review_queue["upcoming"]
    payload = {
        "generated_at": now,
        "debt_metrics": {
            "debt_health": metrics.debt_health,
            "classification_entropy": metrics.classification_entropy,
            "state_entropy": metrics.state_entropy,
            "pointer_entropy": metrics.pointer_entropy,
            "time_entropy": metrics.time_entropy,
            "backlog_pressure": metrics.backlog_pressure,
            "coupling_load": metrics.coupling_load,
        },
        "watchlist_item_ids": list(metrics.watchlist_item_ids),
        "gate_item_ids": list(metrics.gate_item_ids),
        "overdue_review_count": len(due_now),
        "overdue_review_item_ids": [entry["id"] for entry in due_now],
        "next_review_queue": [
            {"id": entry["id"], "next_review_at": entry["next_review_at"]}
            for entry in upcoming
        ],
    }
    _write_yaml(omo_dir / "debt" / "dashboard" / "current.yaml", payload)


def write_review_queue(omo_dir: Path, review_queue: dict[str, object], _write_yaml) -> None:
    _write_yaml(omo_dir / "debt" / "review-queue" / "current.yaml", review_queue)


def _render_action_packet_section(title: str, entries: list[dict[str, object]]) -> str:
    lines = [f"## {title}", ""]
    if entries:
        for entry in entries:
            lines.append(
                f"- `{entry['id']}` — {entry['reason']} — `{entry['suggested_command']}`"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_action_packet(omo_dir: Path, action_packet: dict[str, object], _write_yaml) -> None:
    _write_yaml(omo_dir / "debt" / "action-packet" / "current.yaml", action_packet)

    lanes = action_packet["lanes"]
    markdown = "\n".join(
        [
            f"# Debt Action Packet\n\nGenerated at: {action_packet['generated_at']}\n",
            _render_action_packet_section("Revalidate Now", lanes["revalidate_now"]),
            _render_action_packet_section("Schedule Now", lanes["schedule_now"]),
            _render_action_packet_section("Escalate Now", lanes["escalate_now"]),
            _render_action_packet_section(
                "Continue Mitigation", lanes["continue_mitigation"]
            ),
            _render_action_packet_section("Watch Only", lanes["watch_only"]),
        ]
    )
    path = omo_dir / "debt" / "action-packet" / "current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def _render_owner_routing_section(owner_packet: dict[str, object]) -> str:
    lines = [f"## Owner: {owner_packet['owner']}", ""]
    lines.append(
        "Summary: "
        f"{owner_packet['summary']['total_count']} items; "
        f"revalidate_now={owner_packet['summary']['lane_counts']['revalidate_now']}, "
        f"schedule_now={owner_packet['summary']['lane_counts']['schedule_now']}, "
        f"escalate_now={owner_packet['summary']['lane_counts']['escalate_now']}"
    )
    lines.append("")

    for lane_title, lane_name in [
        ("Revalidate Now", "revalidate_now"),
        ("Schedule Now", "schedule_now"),
        ("Escalate Now", "escalate_now"),
        ("Continue Mitigation", "continue_mitigation"),
        ("Watch Only", "watch_only"),
    ]:
        lane_entries = [
            entry
            for entry in owner_packet["entries"]
            if entry["primary_lane"] == lane_name
        ]
        if not lane_entries:
            continue
        lines.extend([f"### {lane_title}", ""])
        for entry in lane_entries:
            flags = ", ".join(entry["priority_flags"]) or "none"
            lines.append(
                f"- `{entry['id']}` — {entry['reason']} — flags: {flags} — `{entry['shell_command']}`"
            )
        lines.append("")
    return "\n".join(lines)


def write_owner_routing(omo_dir: Path, owner_routing: dict[str, object], _write_yaml) -> None:
    _write_yaml(omo_dir / "debt" / "owner-routing" / "current.yaml", owner_routing)
    markdown = "\n".join(
        [
            f"# Debt Owner Routing Packet\n\nGenerated at: {owner_routing['generated_at']}\n",
            f"Owners: {owner_routing['summary']['owner_count']}\n",
            f"Total routed items: {owner_routing['summary']['total_routed_items']}\n",
            (
                "Lane counts: "
                f"revalidate_now={owner_routing['summary']['lane_counts']['revalidate_now']}, "
                f"schedule_now={owner_routing['summary']['lane_counts']['schedule_now']}, "
                f"escalate_now={owner_routing['summary']['lane_counts']['escalate_now']}, "
                f"continue_mitigation={owner_routing['summary']['lane_counts']['continue_mitigation']}, "
                f"watch_only={owner_routing['summary']['lane_counts']['watch_only']}\n"
            ),
            *[
                _render_owner_routing_section(owner)
                for owner in owner_routing["owners"]
            ],
        ]
    )
    path = omo_dir / "debt" / "owner-routing" / "current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def _render_dispatch_owner_section(owner_packet: dict[str, object]) -> str:
    lines = [f"## Owner: {owner_packet['owner']}", ""]
    lines.append(f"Dispatched items: {owner_packet['item_count']}")
    lines.append("")
    lines.append("### Frozen Commands")
    lines.append("")
    if owner_packet["entries"]:
        for entry in owner_packet["entries"]:
            lines.append(f"- `{entry['id']}` — `{entry['command']}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_dispatch_packet(omo_dir: Path, dispatch_packet: dict[str, object], _write_yaml) -> None:
    markdown = "\n".join(
        [
            "# Debt Dispatch Packet\n",
            f"Dispatch timestamp: {dispatch_packet['dispatched_at']}\n",
            f"Owner count: {dispatch_packet['summary']['owner_count']}\n",
            f"Total dispatched items: {dispatch_packet['summary']['total_dispatched_items']}\n",
            *[
                _render_dispatch_owner_section(owner)
                for owner in dispatch_packet["owners"]
            ],
        ]
    )
    run_yaml_path = omo_dir.parent / dispatch_packet["latest_run_ref"]
    run_md_path = run_yaml_path.with_suffix(".md")
    if run_yaml_path.exists() or run_md_path.exists():
        raise FileExistsError(f"dispatch run already exists: {run_yaml_path}")

    _write_yaml(omo_dir / "debt" / "dispatch" / "current.yaml", dispatch_packet)
    current_md_path = omo_dir / "debt" / "dispatch" / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")
    _write_yaml(run_yaml_path, dispatch_packet)
    run_md_path.write_text(markdown, encoding="utf-8")


def write_campaign_packet(omo_dir: Path, campaign_packet: dict[str, object], _write_yaml) -> None:
    markdown = render_campaign_markdown(campaign_packet)
    run_dir = omo_dir / "debt" / "campaign" / "runs" / campaign_packet["run_stamp"]
    _write_yaml(run_dir / "current.yaml", campaign_packet)
    run_md_path = run_dir / "current.md"
    run_md_path.parent.mkdir(parents=True, exist_ok=True)
    run_md_path.write_text(markdown, encoding="utf-8")
    _write_yaml(omo_dir / "debt" / "campaign" / "current.yaml", campaign_packet)
    current_md_path = omo_dir / "debt" / "campaign" / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def write_reporting_packet(omo_dir: Path, reporting_packet: dict[str, object], _write_yaml) -> None:
    markdown = render_reporting_markdown(reporting_packet)
    run_dir = omo_dir / "debt" / "reporting" / "runs" / reporting_packet["run_stamp"]
    _write_yaml(run_dir / "current.yaml", reporting_packet)
    run_md_path = run_dir / "current.md"
    run_md_path.parent.mkdir(parents=True, exist_ok=True)
    run_md_path.write_text(markdown, encoding="utf-8")
    _write_yaml(omo_dir / "debt" / "reporting" / "current.yaml", reporting_packet)
    current_md_path = omo_dir / "debt" / "reporting" / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def write_reporting_history_packet(
    omo_dir: Path, history_packet: dict[str, object], _write_yaml
) -> None:
    history_dir = omo_dir / "debt" / "reporting" / "history"
    markdown = render_reporting_history_markdown(history_packet)
    _write_yaml(history_dir / "current.yaml", history_packet)
    current_md_path = history_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def write_reporting_diff_packet(omo_dir: Path, diff_packet: dict[str, object], _write_yaml) -> None:
    diff_dir = omo_dir / "debt" / "reporting" / "diff"
    markdown = render_reporting_diff_markdown(diff_packet)
    _write_yaml(diff_dir / "current.yaml", diff_packet)
    current_md_path = diff_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def write_reporting_trend_packet(
    omo_dir: Path, trend_packet: dict[str, object], _write_yaml
) -> None:
    trend_dir = omo_dir / "debt" / "reporting" / "trend"
    markdown = render_reporting_trend_markdown(trend_packet)
    _write_yaml(trend_dir / "current.yaml", trend_packet)
    current_md_path = trend_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")
