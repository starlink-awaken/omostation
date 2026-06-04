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


def _point(event: dict[str, object]) -> dict[str, object]:
    return {
        "event_id": event["event_id"],
        "run_id": event["run_id"],
        "task_id": event["task_id"],
        "started_at": event["started_at"],
        "action": event.get("action"),
        "state": event.get("state"),
        "result": event.get("result"),
    }


def _interval(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    elapsed = _parse_iso8601(str(current["started_at"])) - _parse_iso8601(str(previous["started_at"]))
    return {
        "from_event_id": previous["event_id"],
        "to_event_id": current["event_id"],
        "elapsed_hours": round(elapsed.total_seconds() / 3600, 2),
    }


def build_governance_overlay_approval_prep_trend(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    analytics = _load_yaml_required(root / omo_ref / "workers" / "governance-overlay" / "approval-prep" / "analytics" / "current.yaml")
    history = _load_yaml_required(root / omo_ref / "workers" / "governance-overlay" / "approval-prep" / "history" / "current.yaml")

    events_desc = list(history.get("events", []))
    points = [_point(event) for event in reversed(events_desc)]
    intervals = [_interval(points[index], points[index + 1]) for index in range(len(points) - 1)]
    action_histogram: dict[str, int] = {}
    task_ids_seen: list[str] = []
    for point in points:
        action = str(point.get("action") or "unknown")
        action_histogram[action] = action_histogram.get(action, 0) + 1
        task_id = str(point["task_id"])
        if task_id not in task_ids_seen:
            task_ids_seen.append(task_id)

    peak_backlog_estimate = max(int(analytics.get("prep_task_count", 0)), len(task_ids_seen))
    current_backlog = int(analytics.get("prep_task_count", 0))
    burndown = {
        "current_backlog": current_backlog,
        "peak_backlog_estimate": peak_backlog_estimate,
        "resolved_estimate": peak_backlog_estimate - current_backlog,
        "net_change_from_peak": current_backlog - peak_backlog_estimate,
    }
    yaml_packet = {
        "generated_at": now,
        "trend_status": "trend_available" if len(points) >= 2 else "insufficient_history",
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
