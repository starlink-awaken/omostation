from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_bucket(now: datetime, started_at: str | None) -> str:
    if not started_at:
        return "lt_1d"
    age_seconds = (now - _parse_iso8601(started_at)).total_seconds()
    if age_seconds < 86400:
        return "lt_1d"
    if age_seconds < 3 * 86400:
        return "d1_to_d3"
    return "d3_plus"


def _task_sort_key(entry: dict[str, object]) -> tuple[int, int, str]:
    action_order = {"request_approval": 0, "await_approval": 1}
    age_order = {"d3_plus": 0, "d1_to_d3": 1, "lt_1d": 2}
    return (
        action_order.get(str(entry["action"]), 99),
        age_order.get(str(entry["age_bucket"]), 99),
        str(entry["task_id"]),
    )


def build_governance_overlay_approval_prep_analytics(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    current = _load_yaml_required(root / omo_ref / "workers" / "governance-overlay" / "approval-prep" / "current.yaml")
    history = _load_yaml_required(root / omo_ref / "workers" / "governance-overlay" / "approval-prep" / "history" / "current.yaml")
    generated_at = _parse_iso8601(now)

    latest_event_by_task: dict[str, dict[str, object]] = {}
    for event in history.get("events", []):
        task_id = str(event["task_id"])
        if task_id not in latest_event_by_task:
            latest_event_by_task[task_id] = dict(event)

    blocker_histogram: dict[str, int] = {}
    action_queues = {"request_now": [], "awaiting_approval": []}
    age_buckets = {"lt_1d": 0, "d1_to_d3": 0, "d3_plus": 0}
    tasks: list[dict[str, object]] = []

    for entry in current.get("tasks", []):
        latest_event = latest_event_by_task.get(str(entry["task_id"]), {})
        age_bucket = _age_bucket(generated_at, latest_event.get("started_at"))
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

    tasks.sort(key=_task_sort_key)
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
        markdown_lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"action={entry['action']}",
                f"age_bucket={entry['age_bucket']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
