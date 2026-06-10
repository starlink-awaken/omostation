from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

_PREP_STATES = {"planned_approval_prep_needed", "planned_approval_prep_pending"}
_PREP_RESULTS = {"approval_requested", "approval_prep_needed", "approval_prep_pending"}


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_optional_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _status_sort_key(entry: dict[str, object]) -> tuple[int, str]:
    action_order = {"request_approval": 0, "await_approval": 1}
    return (action_order.get(str(entry["action"]), 99), str(entry["task_id"]))


def _history_sort_key(entry: dict[str, object]) -> tuple[datetime, str]:
    return (_parse_iso8601(str(entry["started_at"])), str(entry["event_id"]))


def _approval_ref_for_target(
    root: Path, omo_ref: Path, target: dict[str, object]
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
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    current = _load_yaml_required(
        root / omo_ref / "workers" / "governance-overlay" / "current.yaml"
    )
    tasks: list[dict[str, object]] = []
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
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    events: list[dict[str, object]] = []
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
