from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _attention(entry: dict[str, object]) -> tuple[str, str]:
    age_bucket = str(entry.get("age_bucket") or "lt_1d")
    action = str(entry.get("action") or "")
    if age_bucket == "d3_plus":
        return ("escalate", "approval prep aging past 3 days")
    if age_bucket == "d1_to_d3" and action == "await_approval":
        return ("watch", "approval follow-up aging past 1 day")
    if age_bucket == "d1_to_d3":
        return ("watch", "approval request aging past 1 day")
    return ("fresh", "recent approval prep activity")


def _task_sort_key(entry: dict[str, object]) -> tuple[int, int, str]:
    attention_order = {"escalate": 0, "watch": 1, "fresh": 2}
    age_order = {"d3_plus": 0, "d1_to_d3": 1, "lt_1d": 2}
    return (
        attention_order.get(str(entry["attention_level"]), 99),
        age_order.get(str(entry["age_bucket"]), 99),
        str(entry["task_id"]),
    )


def build_governance_overlay_approval_prep_aging(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    analytics = _load_yaml_required(root / omo_ref / "workers" / "governance-overlay" / "approval-prep" / "analytics" / "current.yaml")

    tasks: list[dict[str, object]] = []
    attention_summary = {"fresh_count": 0, "watch_count": 0, "escalate_count": 0}
    followup_task_ids: list[str] = []
    escalation_task_ids: list[str] = []

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
        if attention_level in {"watch", "escalate"}:
            followup_task_ids.append(str(entry["task_id"]))
        if attention_level == "escalate":
            escalation_task_ids.append(str(entry["task_id"]))

    tasks.sort(key=_task_sort_key)
    followup_task_ids = [entry["task_id"] for entry in tasks if entry["attention_level"] in {"watch", "escalate"}]
    escalation_task_ids = [entry["task_id"] for entry in tasks if entry["attention_level"] == "escalate"]

    yaml_packet = {
        "generated_at": now,
        "aging_status": "aging_available" if int(analytics.get("prep_task_count", 0)) else "no_prep_tasks",
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
        *(["none"] if not escalation_task_ids else [f"- {task_id}" for task_id in escalation_task_ids]),
        "",
        "## Follow-up Queue",
        "",
        *(["none"] if not followup_task_ids else [f"- {task_id}" for task_id in followup_task_ids]),
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
