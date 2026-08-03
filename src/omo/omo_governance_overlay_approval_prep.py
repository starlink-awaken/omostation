from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .omo_shared import (
    load_yaml as shared_load_yaml,
)
from .omo_shared import (
    load_yaml_required as shared_load_yaml_required,
)

_PREP_STATES = {"planned_approval_prep_needed", "planned_approval_prep_pending"}
_PREP_RESULTS = {"approval_requested", "approval_prep_needed", "approval_prep_pending"}


def _load_yaml_required(path: Path) -> dict:
    return shared_load_yaml_required(path)


def _load_optional_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    return shared_load_yaml(path)


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _status_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    action_order = {"request_approval": 0, "await_approval": 1}
    return (action_order.get(str(entry["action"]), 99), str(entry["task_id"]))


def _history_sort_key(entry: dict[str, Any]) -> tuple[datetime, str]:
    return (_parse_iso8601(str(entry["started_at"])), str(entry["event_id"]))


def _approval_ref_for_target(
    root: Path, omo_ref: Path, target: dict[str, Any]
) -> str | None:
    target_ref = str(target["target_ref"])
    if not target_ref.startswith(str(omo_ref / "tasks" / "planned")):
        return None
    task = _load_optional_yaml(root / target_ref)
    if not task:
        return None
    approval_ref = task.get("approval_ref")
    return str(approval_ref) if approval_ref else None


def build_governance_overlay_approval_prep_status(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    current = _load_yaml_required(
        root / omo_ref / "workers" / "governance-overlay" / "current.yaml"
    )
    tasks: list[dict[str, Any]] = []
    for target in current.get("active_target_states", []):
        if str(target.get("state")) not in _PREP_STATES:
            continue
        tasks.append(
            {
                "task_id": target["task_id"],
                "target_ref": target["target_ref"],
                "state": target["state"],
                "action": target["action"],
                "result": target["result"],
                "blockers": list(target.get("blockers", [])),
                "approval_ref": _approval_ref_for_target(root, omo_ref, target),
                "detail": target.get("detail"),
            }
        )
    tasks.sort(key=_status_sort_key)
    yaml_packet = {
        "generated_at": now,
        "overlay_generated_at": current.get("generated_at"),
        "current_milestone": current.get("current_milestone"),
        "next_action": current.get("next_action"),
        "prep_task_count": len(tasks),
        "request_now_count": sum(
            1 for entry in tasks if entry["action"] == "request_approval"
        ),
        "awaiting_approval_count": sum(
            1 for entry in tasks if entry["action"] == "await_approval"
        ),
        "tasks": tasks,
    }
    markdown_lines = [
        "# Governance Overlay Approval Prep Status",
        "",
        f"Generated at: {now}",
        f"Current milestone: {yaml_packet['current_milestone']}",
        f"Prep tasks: {yaml_packet['prep_task_count']}",
        f"Request now: {yaml_packet['request_now_count']}",
        f"Awaiting approval: {yaml_packet['awaiting_approval_count']}",
    ]
    for entry in tasks:
        markdown_lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"state={entry['state']}",
                f"action={entry['action']}",
                f"result={entry['result']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
                f"approval_ref={entry['approval_ref'] or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}


def build_governance_overlay_approval_prep_history(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    events: list[dict[str, Any]] = []
    for run_path in sorted(runs_dir.glob("governance-overlay-*.yaml")):
        run = _load_yaml_required(run_path)
        run_id = str(run["run_id"])
        for target in run.get("target_results", []):
            if (
                str(target.get("state")) not in _PREP_STATES
                and str(target.get("result")) not in _PREP_RESULTS
            ):
                continue
            task_id = str(target["task_id"])
            events.append(
                {
                    "event_id": f"{run_id}:{task_id}",
                    "run_id": run_id,
                    "run_ref": str(omo_ref / "workers" / "runs" / run_path.name),
                    "task_id": task_id,
                    "target_ref": target.get("target_ref"),
                    "state": target.get("state"),
                    "action": target.get("action"),
                    "result": target.get("result"),
                    "started_at": run.get("started_at"),
                    "completed_at": run.get("completed_at"),
                    "blockers": list(target.get("blockers", [])),
                    "approval_ref": target.get("approval_ref"),
                    "proposal_ref": target.get("proposal_ref"),
                }
            )
    events.sort(key=_history_sort_key, reverse=True)
    latest = events[0] if events else None
    prior = events[1] if len(events) > 1 else None
    yaml_packet = {
        "generated_at": now,
        "event_count": len(events),
        "latest_run_id": None if latest is None else latest["run_id"],
        "prior_run_id": None if prior is None else prior["run_id"],
        "events": events,
    }
    markdown_lines = [
        "# Governance Overlay Approval Prep History",
        "",
        f"Generated at: {now}",
        f"Event count: {yaml_packet['event_count']}",
        f"Latest run: {yaml_packet['latest_run_id'] or 'none'}",
        f"Prior run: {yaml_packet['prior_run_id'] or 'none'}",
    ]
    for entry in events:
        markdown_lines.extend(
            [
                "",
                f"## Event: {entry['event_id']}",
                "",
                f"state={entry['state']}",
                f"action={entry['action']}",
                f"result={entry['result']}",
                f"approval_ref={entry['approval_ref'] or 'none'}",
                f"proposal_ref={entry['proposal_ref'] or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}


def _attention(entry: dict[str, Any]) -> tuple[str, str]:
    age_bucket = str(entry.get("age_bucket") or "lt_1d")
    action = str(entry.get("action") or "")
    if age_bucket == "d3_plus":
        return ("escalate", "approval prep aging past 3 days")
    if age_bucket == "d1_to_d3" and action == "await_approval":
        return ("watch", "approval follow-up aging past 1 day")
    if age_bucket == "d1_to_d3":
        return ("watch", "approval request aging past 1 day")
    return ("fresh", "recent approval prep activity")


def _task_sort_key(entry: dict[str, Any]) -> tuple[int, int, str]:
    attention_order = {"escalate": 0, "watch": 1, "fresh": 2}
    age_order = {"d3_plus": 0, "d1_to_d3": 1, "lt_1d": 2}
    return (
        attention_order.get(str(entry["attention_level"]), 99),
        age_order.get(str(entry["age_bucket"]), 99),
        str(entry["task_id"]),
    )


def _age_bucket(now: datetime, started_at: str | None) -> str:
    if not started_at:
        return "lt_1d"
    age_seconds = (now - _parse_iso8601(started_at)).total_seconds()
    if age_seconds < 86400:
        return "lt_1d"
    if age_seconds < 3 * 86400:
        return "d1_to_d3"
    return "d3_plus"


def _age_bucket_ordered(entry: dict[str, Any]) -> tuple[int, int, str]:
    action_order = {"request_approval": 0, "await_approval": 1}
    age_order = {"d3_plus": 0, "d1_to_d3": 1, "lt_1d": 2}
    return (
        action_order.get(str(entry["action"]), 99),
        age_order.get(str(entry["age_bucket"]), 99),
        str(entry["task_id"]),
    )


def _events_by_task(history: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    events = history.get("events", [])
    if not isinstance(events, list):
        return grouped
    for event in events:
        grouped.setdefault(str(event["task_id"]), []).append(dict(event))
    return grouped


def _change_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    order = {"transitioned": 0, "entered": 1, "unchanged": 2}
    return (order.get(str(entry["change_kind"]), 99), str(entry["task_id"]))


def _point(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event["event_id"],
        "run_id": event["run_id"],
        "task_id": event["task_id"],
        "started_at": event["started_at"],
        "action": event.get("action"),
        "state": event.get("state"),
        "result": event.get("result"),
    }


def _interval(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    elapsed = _parse_iso8601(str(current["started_at"])) - _parse_iso8601(
        str(previous["started_at"])
    )
    return {
        "from_event_id": previous["event_id"],
        "to_event_id": current["event_id"],
        "elapsed_hours": round(elapsed.total_seconds() / 3600, 2),
    }


def build_governance_overlay_approval_prep_aging(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    analytics = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "analytics"
        / "current.yaml"
    )

    tasks: list[dict[str, Any]] = []
    attention_summary = {"fresh_count": 0, "watch_count": 0, "escalate_count": 0}

    for entry in analytics.get("tasks", []):
        attention_level, attention_reason = _attention(entry)
        task_packet = {
            "task_id": entry["task_id"],
            "state": entry.get("state"),
            "action": entry.get("action"),
            "age_bucket": entry.get("age_bucket"),
            "latest_started_at": entry.get("latest_started_at"),
            "blockers": list(entry.get("blockers", [])),
            "approval_ref": entry.get("approval_ref"),
            "attention_level": attention_level,
            "attention_reason": attention_reason,
        }
        tasks.append(task_packet)
        attention_summary[f"{attention_level}_count"] += 1

    tasks.sort(key=_task_sort_key)
    followup_task_ids = [
        str(entry["task_id"])
        for entry in tasks
        if entry["attention_level"] in {"watch", "escalate"}
    ]
    escalation_task_ids = [
        str(entry["task_id"])
        for entry in tasks
        if entry["attention_level"] == "escalate"
    ]

    yaml_packet = {
        "generated_at": now,
        "aging_status": "aging_available"
        if int(analytics.get("prep_task_count", 0))
        else "no_prep_tasks",
        "prep_task_count": int(analytics.get("prep_task_count", 0)),
        "attention_summary": attention_summary,
        "followup_task_ids": followup_task_ids,
        "escalation_task_ids": escalation_task_ids,
        "tasks": tasks,
    }

    markdown_lines = [
        "# Governance Overlay Approval Prep Aging",
        "",
        f"Generated at: {now}",
        f"Aging status: {yaml_packet['aging_status']}",
        f"Prep task count: {yaml_packet['prep_task_count']}",
        "",
        "## Escalation Candidates",
        "",
        *(
            ["none"]
            if not escalation_task_ids
            else [f"- {task_id}" for task_id in escalation_task_ids]
        ),
        "",
        "## Follow-up Queue",
        "",
        *(
            ["none"]
            if not followup_task_ids
            else [f"- {task_id}" for task_id in followup_task_ids]
        ),
    ]
    for entry in tasks:
        markdown_lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"attention_level={entry['attention_level']}",
                f"attention_reason={entry['attention_reason']}",
                f"age_bucket={entry['age_bucket']}",
                f"action={entry['action']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}


def build_governance_overlay_approval_prep_analytics(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    current = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "current.yaml"
    )
    history = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "history"
        / "current.yaml"
    )
    generated_at = _parse_iso8601(now)

    latest_event_by_task: dict[str, dict[str, Any]] = {}
    for event in history.get("events", []):
        task_id = str(event["task_id"])
        if task_id not in latest_event_by_task:
            latest_event_by_task[task_id] = dict(event)

    blocker_histogram: dict[str, int] = {}
    action_queues = {"request_now": [], "awaiting_approval": []}
    age_buckets = {"lt_1d": 0, "d1_to_d3": 0, "d3_plus": 0}
    tasks: list[dict[str, Any]] = []

    for entry in current.get("tasks", []):
        latest_event = latest_event_by_task.get(str(entry["task_id"]), {})
        latest_started_at = latest_event.get("started_at")
        age_bucket = _age_bucket(
            generated_at,
            str(latest_started_at) if latest_started_at is not None else None,
        )
        age_buckets[age_bucket] += 1
        blockers = list(entry.get("blockers", []))
        for blocker in blockers:
            blocker_histogram[blocker] = blocker_histogram.get(blocker, 0) + 1
        task_packet = {
            "task_id": entry["task_id"],
            "state": entry["state"],
            "action": entry["action"],
            "age_bucket": age_bucket,
            "latest_started_at": latest_event.get("started_at"),
            "blockers": blockers,
            "approval_ref": entry.get("approval_ref"),
        }
        tasks.append(task_packet)
        queue_entry = {
            "task_id": entry["task_id"],
            "age_bucket": age_bucket,
            "blockers": blockers,
        }
        if entry["action"] == "request_approval":
            action_queues["request_now"].append(queue_entry)
        elif entry["action"] == "await_approval":
            action_queues["awaiting_approval"].append(queue_entry)

    tasks.sort(key=_age_bucket_ordered)
    yaml_packet = {
        "generated_at": now,
        "prep_task_count": current.get("prep_task_count", 0),
        "history_event_count": history.get("event_count", 0),
        "request_now_count": current.get("request_now_count", 0),
        "awaiting_approval_count": current.get("awaiting_approval_count", 0),
        "blocker_histogram": blocker_histogram,
        "age_buckets": age_buckets,
        "action_queues": action_queues,
        "tasks": tasks,
    }
    markdown_lines = [
        "# Governance Overlay Approval Prep Analytics",
        "",
        f"Generated at: {now}",
        f"Prep tasks: {yaml_packet['prep_task_count']}",
        f"History events: {yaml_packet['history_event_count']}",
        f"Request now: {yaml_packet['request_now_count']}",
        f"Awaiting approval: {yaml_packet['awaiting_approval_count']}",
    ]
    for entry in tasks:
        blockers = entry.get("blockers", [])
        if not isinstance(blockers, list):
            blockers = []
        markdown_lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"action={entry['action']}",
                f"age_bucket={entry['age_bucket']}",
                f"blockers={','.join(str(blocker) for blocker in blockers) or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}


def build_governance_overlay_approval_prep_diff(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    current = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "current.yaml"
    )
    history = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "history"
        / "current.yaml"
    )

    task_events = _events_by_task(history)
    current_task_ids = {str(entry["task_id"]) for entry in current.get("tasks", [])}
    history_task_ids = set(task_events)

    task_changes: list[dict[str, Any]] = []
    new_current_task_ids: list[str] = []
    changed_current_task_ids: list[str] = []
    unchanged_current_task_ids: list[str] = []

    for entry in current.get("tasks", []):
        task_id = str(entry["task_id"])
        events = task_events.get(task_id, [])
        latest_event = events[0] if events else None
        previous_event = None
        if latest_event is not None:
            latest_matches_current = latest_event.get("state") == entry.get(
                "state"
            ) and latest_event.get("action") == entry.get("action")
            if latest_matches_current:
                previous_event = events[1] if len(events) > 1 else None
            else:
                previous_event = latest_event

        if previous_event is None:
            change_kind = "entered"
            new_current_task_ids.append(task_id)
        elif previous_event.get("state") != entry.get("state") or previous_event.get(
            "action"
        ) != entry.get("action"):
            change_kind = "transitioned"
            changed_current_task_ids.append(task_id)
        else:
            change_kind = "unchanged"
            unchanged_current_task_ids.append(task_id)

        task_changes.append(
            {
                "task_id": task_id,
                "change_kind": change_kind,
                "current_state": entry.get("state"),
                "current_action": entry.get("action"),
                "current_result": entry.get("result"),
                "current_approval_ref": entry.get("approval_ref"),
                "previous_state": None
                if previous_event is None
                else previous_event.get("state"),
                "previous_action": None
                if previous_event is None
                else previous_event.get("action"),
                "previous_result": None
                if previous_event is None
                else previous_event.get("result"),
                "previous_started_at": None
                if previous_event is None
                else previous_event.get("started_at"),
                "blockers": list(entry.get("blockers", [])),
            }
        )

    task_changes.sort(key=_change_sort_key)
    new_current_task_ids.sort()
    changed_current_task_ids.sort()
    unchanged_current_task_ids.sort()
    no_longer_current_task_ids = sorted(history_task_ids - current_task_ids)

    yaml_packet = {
        "generated_at": now,
        "diff_status": "diff_available"
        if current.get("prep_task_count", 0) or history.get("event_count", 0)
        else "empty_diff",
        "current_task_count": int(current.get("prep_task_count", 0)),
        "history_event_count": int(history.get("event_count", 0)),
        "new_current_task_ids": new_current_task_ids,
        "changed_current_task_ids": changed_current_task_ids,
        "unchanged_current_task_ids": unchanged_current_task_ids,
        "no_longer_current_task_ids": no_longer_current_task_ids,
        "task_changes": task_changes,
    }

    markdown_lines = [
        "# Governance Overlay Approval Prep Diff",
        "",
        f"Generated at: {now}",
        f"Diff status: {yaml_packet['diff_status']}",
        f"Current task count: {yaml_packet['current_task_count']}",
        f"History event count: {yaml_packet['history_event_count']}",
        "",
        "## Entered",
        "",
        *(
            ["none"]
            if not new_current_task_ids
            else [f"- {task_id}" for task_id in new_current_task_ids]
        ),
        "",
        "## Transitioned",
        "",
        *(
            ["none"]
            if not changed_current_task_ids
            else [f"- {task_id}" for task_id in changed_current_task_ids]
        ),
        "",
        "## Exited",
        "",
        *(
            ["none"]
            if not no_longer_current_task_ids
            else [f"- {task_id}" for task_id in no_longer_current_task_ids]
        ),
    ]
    for entry in task_changes:
        markdown_lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"change_kind={entry['change_kind']}",
                f"current_action={entry['current_action']}",
                f"previous_action={entry['previous_action'] or 'none'}",
                f"previous_started_at={entry['previous_started_at'] or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}


def build_governance_overlay_approval_prep_trend(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    analytics = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "analytics"
        / "current.yaml"
    )
    history = _load_yaml_required(
        root
        / omo_ref
        / "workers"
        / "governance-overlay"
        / "approval-prep"
        / "history"
        / "current.yaml"
    )

    events_desc = list(history.get("events", []))
    points = [_point(event) for event in reversed(events_desc)]
    intervals = [
        _interval(points[index], points[index + 1]) for index in range(len(points) - 1)
    ]
    action_histogram: dict[str, int] = {}
    task_ids_seen: list[str] = []
    for point in points:
        action = str(point.get("action") or "unknown")
        action_histogram[action] = action_histogram.get(action, 0) + 1
        task_id = str(point["task_id"])
        if task_id not in task_ids_seen:
            task_ids_seen.append(task_id)

    peak_backlog_estimate = max(
        int(analytics.get("prep_task_count", 0)), len(task_ids_seen)
    )
    current_backlog = int(analytics.get("prep_task_count", 0))
    burndown = {
        "current_backlog": current_backlog,
        "peak_backlog_estimate": peak_backlog_estimate,
        "resolved_estimate": peak_backlog_estimate - current_backlog,
        "net_change_from_peak": current_backlog - peak_backlog_estimate,
    }
    yaml_packet = {
        "generated_at": now,
        "trend_status": "trend_available"
        if len(points) >= 2
        else "insufficient_history",
        "window_event_count": len(points),
        "oldest_started_at": None if not points else points[0]["started_at"],
        "latest_started_at": None if not points else points[-1]["started_at"],
        "current_backlog": current_backlog,
        "history_event_count": int(history.get("event_count", 0)),
        "blocker_histogram": dict(analytics.get("blocker_histogram", {})),
        "action_histogram": action_histogram,
        "points": points,
        "intervals": intervals,
        "burndown": burndown,
    }
    markdown_lines = [
        "# Governance Overlay Approval Prep Trend",
        "",
        f"Generated at: {now}",
        f"Trend status: {yaml_packet['trend_status']}",
        f"Window event count: {yaml_packet['window_event_count']}",
        f"Oldest started at: {yaml_packet['oldest_started_at'] or 'none'}",
        f"Latest started at: {yaml_packet['latest_started_at'] or 'none'}",
        "",
        "## Burndown",
        "",
        f"current_backlog={burndown['current_backlog']}",
        f"peak_backlog_estimate={burndown['peak_backlog_estimate']}",
        f"resolved_estimate={burndown['resolved_estimate']}",
        f"net_change_from_peak={burndown['net_change_from_peak']}",
    ]
    for point in points:
        markdown_lines.extend(
            [
                "",
                f"## Task: {point['task_id']}",
                "",
                f"started_at={point['started_at']}",
                f"action={point['action']}",
                f"state={point['state']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
