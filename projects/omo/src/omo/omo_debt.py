#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .omo_debt_approval import (
    APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    approval_current_path,
    build_approval_record,
    dispatch_entry_requires_approval,
    find_dispatch_entry,
    approval_paths,
)
from .omo_debt_action_packet import build_action_packet
from .omo_debt_campaign import build_campaign_packet, render_campaign_markdown
from .omo_debt_dispatch import build_dispatch_packet
from .omo_debt_execution import (
    build_execution_record,
    execution_record_path,
    run_slug_from_ref,
)
from .omo_debt_metrics import compute_debt_metrics
from .omo_debt_owner_routing import build_owner_routing_packet
from .omo_debt_reporting import build_reporting_packet, render_reporting_markdown
from .omo_debt_reporting_diff import (
    build_reporting_diff_packet,
    render_reporting_diff_markdown,
)
from .omo_debt_reporting_history import (
    build_reporting_history_packet,
    render_reporting_history_markdown,
)
from .omo_debt_reporting_trend import (
    build_reporting_trend_packet,
    render_reporting_trend_markdown,
)
from .omo_debt_registry import DebtItem, load_debt_ledger
from .omo_debt_review_queue import build_review_queue
from .omo_debt_lifecycle import (
    append_history,
    register_item,
    append_registry_ref,
    schedule_item,
    update_item,
    classify_review_sections,
)

def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed



def write_dashboard(
    omo_dir: Path, metrics, review_queue: dict[str, object], now: str
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


def write_review_queue(omo_dir: Path, review_queue: dict[str, object]) -> None:
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


def write_action_packet(omo_dir: Path, action_packet: dict[str, object]) -> None:
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


def write_owner_routing(omo_dir: Path, owner_routing: dict[str, object]) -> None:
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


def write_dispatch_packet(omo_dir: Path, dispatch_packet: dict[str, object]) -> None:
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


def _matching_approval_exists(
    omo_dir: Path, item_id: str, dispatch_run_ref: str
) -> bool:
    approval_path = approval_current_path(omo_dir, item_id)
    if not approval_path.exists():
        return False
    approval_record = _load_yaml(approval_path)
    return (
        bool(approval_record)
        and approval_record.get("approval_scope") == APPROVAL_SCOPE_EXECUTE_REVALIDATE
        and approval_record.get("dispatch_run_ref") == dispatch_run_ref
    )


def _execution_record_ref(
    omo_dir: Path, dispatch_run_ref: str, item_id: str
) -> str | None:
    record_path = execution_record_path(omo_dir, dispatch_run_ref, item_id)
    if not record_path.exists():
        return None
    return f".omo/debt/dispatch/executions/{run_slug_from_ref(dispatch_run_ref)}/{item_id}.yaml"


def write_campaign_packet(omo_dir: Path, campaign_packet: dict[str, object]) -> None:
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


def write_reporting_packet(omo_dir: Path, reporting_packet: dict[str, object]) -> None:
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
    omo_dir: Path, history_packet: dict[str, object]
) -> None:
    history_dir = omo_dir / "debt" / "reporting" / "history"
    markdown = render_reporting_history_markdown(history_packet)
    _write_yaml(history_dir / "current.yaml", history_packet)
    current_md_path = history_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def write_reporting_diff_packet(omo_dir: Path, diff_packet: dict[str, object]) -> None:
    diff_dir = omo_dir / "debt" / "reporting" / "diff"
    markdown = render_reporting_diff_markdown(diff_packet)
    _write_yaml(diff_dir / "current.yaml", diff_packet)
    current_md_path = diff_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def write_reporting_trend_packet(
    omo_dir: Path, trend_packet: dict[str, object]
) -> None:
    trend_dir = omo_dir / "debt" / "reporting" / "trend"
    markdown = render_reporting_trend_markdown(trend_packet)
    _write_yaml(trend_dir / "current.yaml", trend_packet)
    current_md_path = trend_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def load_reporting_history_packet(omo_dir: Path) -> dict[str, object]:
    history_path = omo_dir / "debt" / "reporting" / "history" / "current.yaml"
    if not history_path.exists():
        raise FileNotFoundError(f"missing reporting history packet: {history_path}")
    history_packet = _load_yaml(history_path)
    if not history_packet:
        raise ValueError(f"empty reporting history packet: {history_path}")
    return history_packet


def _history_run_ref(
    history_packet: dict[str, object], run_stamp: str | None
) -> str | None:
    if run_stamp is None:
        return None
    for entry in history_packet["runs"]:
        if entry["run_stamp"] == run_stamp:
            return entry["dispatch_run_ref"]
    raise ValueError(f"missing history run entry for: {run_stamp}")


def _reporting_history_inputs(
    omo_dir: Path,
) -> tuple[tuple[dict[str, str], ...], dict[str, dict[str, object]]]:
    dispatch_runs_dir = omo_dir / "debt" / "dispatch" / "runs"
    run_paths = sorted(dispatch_runs_dir.glob("*.yaml"))
    if not run_paths:
        raise FileNotFoundError(f"no dispatch run artifacts found: {dispatch_runs_dir}")

    dispatch_runs: list[dict[str, str]] = []
    reporting_packets_by_run: dict[str, dict[str, object]] = {}
    for run_path in run_paths:
        run_stamp = run_path.stem
        dispatch_runs.append(
            {
                "run_stamp": run_stamp,
                "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_path.name}",
            }
        )
        reporting_path = (
            omo_dir / "debt" / "reporting" / "runs" / run_stamp / "current.yaml"
        )
        if not reporting_path.exists():
            continue
        reporting_packet = _load_yaml(reporting_path)
        if not reporting_packet:
            raise ValueError(f"empty reporting run artifact: {reporting_path}")
        if reporting_packet.get("run_stamp") != run_stamp:
            raise ValueError(f"reporting run stamp mismatch: {reporting_path}")
        reporting_packets_by_run[run_stamp] = reporting_packet
    return tuple(dispatch_runs), reporting_packets_by_run


def write_review_pack(
    omo_dir: Path,
    items: tuple[DebtItem, ...],
    metrics,
    review_queue: dict[str, object],
    now: str,
) -> None:
    sections = classify_review_sections(items)
    watchlist = list(metrics.watchlist_item_ids)
    gate = list(metrics.gate_item_ids)
    content = "\n".join(
        [
            f"# Debt Review Pack\n\nGenerated at: {now}\n",
            _render_section("Watchlist", watchlist),
            _render_section("Gate Debts", gate),
            _render_queue_section(
                "Due Now", review_queue["due_now"], "priority_reason"
            ),
            _render_queue_section(
                "Escalation Candidates",
                review_queue["escalation_candidates"],
                "escalation_reason",
            ),
            _render_queue_section(
                "Upcoming Window", review_queue["upcoming"], "priority_reason"
            ),
            _render_queue_section(
                "Unscheduled Debts", review_queue["unscheduled"], "priority_reason"
            ),
            _render_section("Newly Registered", sections["newly_registered"]),
            _render_section("Closed Debts", sections["closed"]),
            _render_section("Drifted Debts", sections["drifted"]),
            _render_section("Escalated Debts", sections["escalated"]),
            _render_section("Reopened Debts", sections["reopened"]),
        ]
    )
    review_path = omo_dir / "debt" / "reviews" / "current.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(content, encoding="utf-8")


def refresh_outputs(omo_dir: Path, now: str) -> None:
    ledger = load_debt_ledger(omo_dir)
    metrics = compute_debt_metrics(ledger.items, now=now, repo_root=omo_dir.parent)
    review_queue = build_review_queue(ledger.items, now=now, repo_root=omo_dir.parent)
    action_packet = build_action_packet(review_queue, now=now)
    owner_routing = build_owner_routing_packet(action_packet)
    write_dashboard(omo_dir, metrics, review_queue, now)
    write_review_queue(omo_dir, review_queue)
    write_review_pack(omo_dir, ledger.items, metrics, review_queue, now)
    write_action_packet(omo_dir, action_packet)
    write_owner_routing(omo_dir, owner_routing)


def dispatch_outputs(omo_dir: Path, now: str) -> None:
    owner_routing_path = omo_dir / "debt" / "owner-routing" / "current.yaml"
    if not owner_routing_path.exists():
        raise FileNotFoundError(f"missing owner routing packet: {owner_routing_path}")
    owner_routing = _load_yaml(owner_routing_path)
    if not owner_routing:
        raise ValueError(f"empty owner routing packet: {owner_routing_path}")
    write_dispatch_packet(
        omo_dir, build_dispatch_packet(owner_routing, dispatched_at=now)
    )


def load_dispatch_packet(omo_dir: Path) -> dict:
    dispatch_path = omo_dir / "debt" / "dispatch" / "current.yaml"
    if not dispatch_path.exists():
        raise FileNotFoundError(f"missing dispatch packet: {dispatch_path}")
    dispatch_packet = _load_yaml(dispatch_path)
    if not dispatch_packet:
        raise ValueError(f"empty dispatch packet: {dispatch_path}")
    return dispatch_packet


def load_dispatch_run(omo_dir: Path, dispatch_run_ref: str) -> tuple[Path, dict]:
    run_path = omo_dir.parent / dispatch_run_ref
    if not run_path.exists():
        raise FileNotFoundError(f"missing dispatch run artifact: {run_path}")
    run_packet = _load_yaml(run_path)
    if not run_packet:
        raise ValueError(f"empty dispatch run artifact: {run_path}")
    return run_path, run_packet


def build_selected_campaign_packet(
    omo_dir: Path, run_ref: str | None
) -> dict[str, object]:
    if run_ref:
        _, run_packet = load_dispatch_run(omo_dir, run_ref)
        dispatch_run_ref = run_ref
    else:
        dispatch_packet = load_dispatch_packet(omo_dir)
        dispatch_run_ref = dispatch_packet["latest_run_ref"]
        _, run_packet = load_dispatch_run(omo_dir, dispatch_run_ref)

    approval_lookup: dict[str, bool] = {}
    execution_lookup: dict[str, str] = {}
    for owner_packet in run_packet["owners"]:
        for entry in owner_packet["entries"]:
            item_id = entry["id"]
            approval_lookup[item_id] = _matching_approval_exists(
                omo_dir, item_id, dispatch_run_ref
            )
            execution_record_ref = _execution_record_ref(
                omo_dir, dispatch_run_ref, item_id
            )
            if execution_record_ref:
                execution_lookup[item_id] = execution_record_ref

    campaign_packet = build_campaign_packet(
        run_packet=run_packet,
        dispatch_run_ref=dispatch_run_ref,
        generated_at=_timestamp(),
        approval_lookup=approval_lookup,
        execution_lookup=execution_lookup,
    )
    return campaign_packet


def campaign_outputs(omo_dir: Path, run_ref: str | None) -> None:
    campaign_packet = build_selected_campaign_packet(omo_dir, run_ref)
    write_campaign_packet(omo_dir, campaign_packet)


def reporting_outputs(omo_dir: Path, run_ref: str | None) -> None:
    campaign_packet = build_selected_campaign_packet(omo_dir, run_ref)
    write_reporting_packet(omo_dir, build_reporting_packet(campaign_packet))


def reporting_history_outputs(omo_dir: Path) -> None:
    dispatch_runs, reporting_packets_by_run = _reporting_history_inputs(omo_dir)
    write_reporting_history_packet(
        omo_dir,
        build_reporting_history_packet(
            generated_at=_timestamp(),
            dispatch_runs=dispatch_runs,
            reporting_packets_by_run=reporting_packets_by_run,
        ),
    )


def reporting_diff_outputs(omo_dir: Path) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    latest_run_ref = _history_run_ref(
        history_packet, history_packet.get("latest_run_stamp")
    )
    if latest_run_ref is None:
        raise ValueError("reporting history is missing latest_run_stamp")
    prior_run_ref = _history_run_ref(
        history_packet, history_packet.get("prior_run_stamp")
    )
    latest_reporting = build_reporting_packet(
        build_selected_campaign_packet(omo_dir, latest_run_ref)
    )
    prior_reporting = (
        build_reporting_packet(build_selected_campaign_packet(omo_dir, prior_run_ref))
        if prior_run_ref
        else None
    )
    write_reporting_diff_packet(
        omo_dir,
        build_reporting_diff_packet(
            generated_at=_timestamp(),
            latest_packet=latest_reporting,
            prior_packet=prior_reporting,
        ),
    )


def _reporting_trend_owner_inputs(
    trend_packet: dict[str, object], omo_dir: Path
) -> dict[str, dict[str, object]]:
    packets: dict[str, dict[str, object]] = {}
    for entry in trend_packet["runs"]:
        reporting_ref = entry.get("reporting_ref")
        if reporting_ref is None:
            continue
        reporting_path = omo_dir.parent / str(reporting_ref)
        if not reporting_path.exists():
            raise FileNotFoundError(
                f"missing reporting artifact for owner trend: {reporting_path}"
            )
        reporting_packet = _load_yaml(reporting_path)
        if not reporting_packet:
            raise ValueError(
                f"empty reporting artifact for owner trend: {reporting_path}"
            )
        packets[str(entry["run_stamp"])] = reporting_packet
    return packets


def reporting_trend_outputs(
    omo_dir: Path,
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    if window_requested is not None and (
        from_run_stamp_requested is not None or to_run_stamp_requested is not None
    ):
        raise ValueError(
            "--last cannot be combined with --from-run-stamp or --to-run-stamp"
        )
    if (from_run_stamp_requested is None) != (to_run_stamp_requested is None):
        raise ValueError("range mode requires both from-run-stamp and to-run-stamp")
    trend_packet = build_reporting_trend_packet(
        generated_at=_timestamp(),
        history_packet=history_packet,
        window_requested=window_requested,
        from_run_stamp_requested=from_run_stamp_requested,
        to_run_stamp_requested=to_run_stamp_requested,
    )
    if trend_packet["trend_status"] == "insufficient_history":
        write_reporting_trend_packet(omo_dir, trend_packet)
        return
    reporting_packets_by_run = _reporting_trend_owner_inputs(trend_packet, omo_dir)
    write_reporting_trend_packet(
        omo_dir,
        build_reporting_trend_packet(
            generated_at=trend_packet["generated_at"],
            history_packet=history_packet,
            reporting_packets_by_run=reporting_packets_by_run,
            window_requested=window_requested,
            from_run_stamp_requested=from_run_stamp_requested,
            to_run_stamp_requested=to_run_stamp_requested,
        ),
    )


def require_dispatch_bound_revalidate(
    omo_dir: Path,
    item_id: str,
    dispatch_run_ref: str | None,
) -> str | None:
    dispatch_path = omo_dir / "debt" / "dispatch" / "current.yaml"
    if not dispatch_path.exists():
        if dispatch_run_ref:
            raise FileNotFoundError(f"missing dispatch packet: {dispatch_path}")
        return None

    dispatch_packet = load_dispatch_packet(omo_dir)
    entry = find_dispatch_entry(dispatch_packet, item_id)
    if not entry or entry.get("primary_lane") != "revalidate_now":
        if dispatch_run_ref:
            raise ValueError(f"item is not a dispatched revalidate entry: {item_id}")
        return None
    if not dispatch_run_ref:
        raise ValueError(
            f"missing --dispatch-run-ref for dispatched revalidate item: {item_id}"
        )
    if dispatch_run_ref != dispatch_packet["latest_run_ref"]:
        raise ValueError(
            f"dispatch run must match latest dispatch run: {dispatch_run_ref}"
        )

    _, run_packet = load_dispatch_run(omo_dir, dispatch_run_ref)
    run_entry = find_dispatch_entry(run_packet, item_id)
    if not run_entry or run_entry.get("primary_lane") != "revalidate_now":
        raise ValueError(
            f"dispatch run does not contain a revalidate entry for: {item_id}"
        )
    return dispatch_run_ref


def require_matching_revalidate_approval(
    omo_dir: Path, item_id: str, dispatch_run_ref: str | None
) -> None:
    dispatch_path = omo_dir / "debt" / "dispatch" / "current.yaml"
    if not dispatch_path.exists():
        return

    dispatch_packet = load_dispatch_packet(omo_dir)
    entry = find_dispatch_entry(dispatch_packet, item_id)
    if not dispatch_entry_requires_approval(entry):
        return
    if not dispatch_run_ref:
        raise ValueError(
            f"missing --dispatch-run-ref for approved dispatched item: {item_id}"
        )

    approval_path = approval_current_path(omo_dir, item_id)
    if not approval_path.exists():
        raise FileNotFoundError(f"missing approval record: {approval_path}")
    approval_record = _load_yaml(approval_path)
    if not approval_record:
        raise ValueError(f"empty approval record: {approval_path}")
    if approval_record.get("approval_scope") != APPROVAL_SCOPE_EXECUTE_REVALIDATE:
        raise ValueError(
            f"approval scope must be {APPROVAL_SCOPE_EXECUTE_REVALIDATE}: {approval_path}"
        )
    if approval_record.get("dispatch_run_ref") != dispatch_run_ref:
        raise ValueError(
            f"approval dispatch run mismatch: {approval_path} != {dispatch_run_ref}"
        )


def approve_item(
    omo_dir: Path,
    item_id: str,
    approved_by: str,
    approval_scope: str,
    approved_at: str,
) -> None:
    _parse_iso8601(approved_at)
    dispatch_packet = load_dispatch_packet(omo_dir)
    entry = find_dispatch_entry(dispatch_packet, item_id)
    if not dispatch_entry_requires_approval(entry):
        raise ValueError(
            f"item is not a gate-level dispatched revalidate item: {item_id}"
        )

    current_path, record_path = approval_paths(omo_dir, item_id, approved_at)
    if record_path.exists():
        raise FileExistsError(f"approval record already exists: {record_path}")

    approval_record = build_approval_record(
        item_id=item_id,
        approved_by=approved_by,
        approved_at=approved_at,
        dispatch_run_ref=dispatch_packet["latest_run_ref"],
        approval_scope=approval_scope,
    )
    _write_yaml(record_path, approval_record)
    _write_yaml(current_path, approval_record)


def main() -> int:
    parser = argparse.ArgumentParser(prog="omo-debt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--omo-dir", default=".omo")
    register_parser.add_argument("--id", required=True)
    register_parser.add_argument("--title", required=True)
    register_parser.add_argument("--dimension", required=True)
    register_parser.add_argument("--subdimension", required=True)
    register_parser.add_argument("--severity", required=True)
    register_parser.add_argument("--owner", required=True)
    register_parser.add_argument("--actor", default="", help="Who performed this action (default: empty)")
    register_parser.add_argument("--x1-policy-ref", default="", help="X1 governance policy reference ID")
    register_parser.add_argument("--x2-freshness", default="", help="X2 freshness timestamp (ISO 8601)")
    register_parser.add_argument("--x3-tier", default="", help="X3 value tier (Axiom/Principle/Theory/Framework/Knowledge/Skill/Tool)")

    schedule_parser = subparsers.add_parser("schedule")
    schedule_parser.add_argument("--omo-dir", default=".omo")
    schedule_parser.add_argument("--id", required=True)
    schedule_parser.add_argument("--next-review-at", required=True)

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("--omo-dir", default=".omo")
    refresh_parser.add_argument("--now", required=True)

    dispatch_parser = subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("--omo-dir", default=".omo")
    dispatch_parser.add_argument("--now", required=True)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--omo-dir", default=".omo")
    approve_parser.add_argument("--id", required=True)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--scope", required=True)
    approve_parser.add_argument("--approved-at", required=True)

    campaign_parser = subparsers.add_parser("campaign")
    campaign_parser.add_argument("--omo-dir", default=".omo")
    campaign_parser.add_argument("--run-ref")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--omo-dir", default=".omo")
    report_parser.add_argument("--run-ref")

    report_history_parser = subparsers.add_parser("report-history")
    report_history_parser.add_argument("--omo-dir", default=".omo")

    report_diff_parser = subparsers.add_parser("report-diff")
    report_diff_parser.add_argument("--omo-dir", default=".omo")

    report_trend_parser = subparsers.add_parser("report-trend")
    report_trend_parser.add_argument("--omo-dir", default=".omo")
    report_trend_parser.add_argument("--last", type=_positive_int)
    report_trend_parser.add_argument("--from-run-stamp")
    report_trend_parser.add_argument("--to-run-stamp")

    reclassify_parser = subparsers.add_parser("reclassify")
    reclassify_parser.add_argument("--omo-dir", default=".omo")
    reclassify_parser.add_argument("--id", required=True)
    reclassify_parser.add_argument("--dimension", required=True)
    reclassify_parser.add_argument("--subdimension", required=True)

    escalate_parser = subparsers.add_parser("escalate")
    escalate_parser.add_argument("--omo-dir", default=".omo")
    escalate_parser.add_argument("--id", required=True)
    escalate_parser.add_argument("--gate-level", required=True)

    revalidate_parser = subparsers.add_parser("revalidate")
    revalidate_parser.add_argument("--omo-dir", default=".omo")
    revalidate_parser.add_argument("--id", required=True)
    revalidate_parser.add_argument("--reviewed-at", required=True)
    revalidate_parser.add_argument("--dispatch-run-ref")

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--omo-dir", default=".omo")
    close_parser.add_argument("--id", required=True)
    close_parser.add_argument("--actor", default="", help="Who performed this action")

    reopen_parser = subparsers.add_parser("reopen")
    reopen_parser.add_argument("--omo-dir", default=".omo")
    reopen_parser.add_argument("--id", required=True)
    reopen_parser.add_argument("--actor", default="", help="Who performed this action")

    args = parser.parse_args()
    omo_dir = Path(args.omo_dir)

    if args.command == "register":
        payload = register_item(args)
        item_ref = f".omo/debt/items/{args.id}.yaml"
        item_path = omo_dir / "debt" / "items" / f"{args.id}.yaml"
        _write_yaml(item_path, payload)
        append_registry_ref(omo_dir, item_ref)
        print(f"registered {args.id}")
        return 0

    if args.command == "schedule":
        schedule_item(omo_dir, args.id, args.next_review_at)
        print(f"scheduled {args.id}")
        return 0

    if args.command == "refresh":
        refresh_outputs(omo_dir, args.now)
        print("refreshed debt outputs")
        return 0

    if args.command == "dispatch":
        dispatch_outputs(omo_dir, args.now)
        print("dispatched debt owner routing")
        return 0

    if args.command == "approve":
        approve_item(omo_dir, args.id, args.approved_by, args.scope, args.approved_at)
        print(f"approved {args.id}")
        return 0

    if args.command == "campaign":
        campaign_outputs(omo_dir, args.run_ref)
        print("generated debt campaign packet")
        return 0

    if args.command == "report":
        reporting_outputs(omo_dir, args.run_ref)
        print("generated debt reporting packet")
        return 0

    if args.command == "report-history":
        reporting_history_outputs(omo_dir)
        print("generated debt reporting history packet")
        return 0

    if args.command == "report-diff":
        reporting_diff_outputs(omo_dir)
        print("generated debt reporting diff packet")
        return 0

    if args.command == "report-trend":
        reporting_trend_outputs(
            omo_dir,
            window_requested=args.last,
            from_run_stamp_requested=args.from_run_stamp,
            to_run_stamp_requested=args.to_run_stamp,
        )
        print("generated debt reporting trend packet")
        return 0

    if args.command == "reclassify":
        item_path, payload = update_item(omo_dir, args.id)
        payload["dimension"] = args.dimension
        payload["subdimension"] = args.subdimension
        append_history(
            payload,
            "reclassify",
            f"Reclassified to {args.dimension}/{args.subdimension}.",
        )
        _write_yaml(item_path, payload)
        print(f"reclassified {args.id}")
        return 0

    if args.command == "escalate":
        item_path, payload = update_item(omo_dir, args.id)
        payload["gate_level"] = args.gate_level
        append_history(payload, "escalate", f"Escalated to {args.gate_level}.")
        _write_yaml(item_path, payload)
        print(f"escalated {args.id}")
        return 0

    if args.command == "revalidate":
        bound_run_ref = require_dispatch_bound_revalidate(
            omo_dir, args.id, args.dispatch_run_ref
        )
        require_matching_revalidate_approval(omo_dir, args.id, bound_run_ref)
        item_path, payload = update_item(omo_dir, args.id)
        payload["last_reviewed_at"] = args.reviewed_at
        append_history(payload, "revalidate", f"Reviewed at {args.reviewed_at}.")
        _write_yaml(item_path, payload)
        if bound_run_ref:
            record_path = execution_record_path(omo_dir, bound_run_ref, args.id)
            if record_path.exists():
                raise FileExistsError(f"execution record already exists: {record_path}")
            _write_yaml(
                record_path,
                build_execution_record(
                    item_id=args.id,
                    dispatch_run_ref=bound_run_ref,
                    reviewed_at=args.reviewed_at,
                ),
            )
        print(f"revalidated {args.id}")
        return 0

    if args.command == "close":
        item_path, payload = update_item(omo_dir, args.id)
        payload["lifecycle_state"] = "closed"
        payload["gate_level"] = "none"
        append_history(
            payload,
            "close",
            "Closed debt item.",
            actor=getattr(args, "actor", ""),
        )
        _write_yaml(item_path, payload)
        print(f"closed {args.id}")
        return 0

    if args.command == "reopen":
        item_path, payload = update_item(omo_dir, args.id)
        payload["lifecycle_state"] = "identified"
        append_history(
            payload,
            "reopen",
            "Reopened debt item.",
            actor=getattr(args, "actor", ""),
        )
        _write_yaml(item_path, payload)
        print(f"reopened {args.id}")
        return 0

    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
