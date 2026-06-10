from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _events_by_task(history: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for event in history.get("events", []):
        grouped.setdefault(str(event["task_id"]), []).append(dict(event))
    return grouped


def _change_sort_key(entry: dict[str, object]) -> tuple[int, str]:
    order = {"transitioned": 0, "entered": 1, "unchanged": 2}
    return (order.get(str(entry["change_kind"]), 99), str(entry["task_id"]))


def build_governance_overlay_approval_prep_diff(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, object]:
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

    task_changes: list[dict[str, object]] = []
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
