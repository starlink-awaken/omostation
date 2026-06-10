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


def _age_bucket(now: datetime, requested_at: str, approval_status: str) -> str | None:
    if approval_status != "requested":
        return None
    age_seconds = (now - _parse_iso8601(requested_at)).total_seconds()
    if age_seconds < 86400:
        return "lt_1d"
    if age_seconds < 3 * 86400:
        return "d1_to_d3"
    return "d3_plus"


def _next_action(approval_status: str, proposal_status: str) -> str:
    if approval_status == "requested" and proposal_status == "proposed":
        return "approve"
    if approval_status == "requested" and proposal_status == "approved":
        return "apply"
    if approval_status == "granted":
        return "check_readiness"
    return "none"


def _task_sort_key(item: dict[str, object]) -> tuple[int, int, str]:
    next_action_order = {"approve": 0, "apply": 1, "check_readiness": 2, "none": 3}
    age_order = {"d3_plus": 0, "d1_to_d3": 1, "lt_1d": 2, None: 3}
    return (
        next_action_order.get(str(item["next_action"]), 99),
        age_order.get(item["task_age_bucket"], 99),
        str(item["task_id"]),
    )


def build_promotion_approval_analytics_packet(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, object]:
    omo = Path(omo_dir)
    current = _load_yaml_required(
        root / omo / "workers" / "promotion" / "approvals" / "current.yaml"
    )
    history = _load_yaml_required(
        root / omo / "workers" / "promotion" / "approvals" / "history" / "current.yaml"
    )
    _load_yaml_required(root / omo / "workers" / "promotion" / "readiness.yaml")
    generated_at = _parse_iso8601(now)

    history_by_task = {
        entry["task_id"]: entry for entry in history.get("approvals", [])
    }
    proposal_status_histogram = {
        "proposed": 0,
        "approved": 0,
        "verified": 0,
        "missing": 0,
        "invalid": 0,
    }
    action_queues = {"approve_now": [], "apply_now": [], "check_readiness": []}
    approval_age_buckets = {"lt_1d": 0, "d1_to_d3": 0, "d3_plus": 0}
    blocker_histogram: dict[str, int] = {}
    tasks: list[dict[str, object]] = []

    for entry in current.get("tasks", []):
        history_entry = history_by_task.get(entry["task_id"], {})
        requested_at = str(history_entry.get("requested_at", now))
        proposal_status = str(entry.get("proposal_status", "invalid"))
        if proposal_status not in proposal_status_histogram:
            proposal_status = "invalid"
        proposal_status_histogram[proposal_status] += 1

        age_bucket = _age_bucket(
            generated_at, requested_at, str(entry["approval_status"])
        )
        if age_bucket is not None:
            approval_age_buckets[age_bucket] += 1

        blockers = list(entry.get("blockers", []))
        next_action = _next_action(str(entry["approval_status"]), proposal_status)
        task_packet = {
            "task_id": entry["task_id"],
            "approval_id": entry["approval_id"],
            "approval_status": entry["approval_status"],
            "proposal_status": proposal_status,
            "requested_at": requested_at,
            "task_age_bucket": age_bucket,
            "eligible": entry.get("eligible", False),
            "blockers": blockers,
            "next_action": next_action,
        }
        tasks.append(task_packet)

        for blocker in blockers:
            blocker_histogram[blocker] = blocker_histogram.get(blocker, 0) + 1

        queue_entry = {
            "task_id": entry["task_id"],
            "approval_id": entry["approval_id"],
            "proposal_id": entry["proposal_id"],
            "blockers": blockers,
        }
        if next_action == "approve":
            action_queues["approve_now"].append(queue_entry)
        elif next_action == "apply":
            action_queues["apply_now"].append(queue_entry)
        elif next_action == "check_readiness":
            action_queues["check_readiness"].append(queue_entry)

    tasks.sort(key=_task_sort_key)

    yaml_packet = {
        "generated_at": now,
        "approval_task_count": current.get("approval_task_count", 0),
        "history_approval_count": history.get("approval_count", 0),
        "requested_count": current.get("requested_count", 0),
        "approved_pending_apply_count": current.get("approved_pending_apply_count", 0),
        "granted_count": current.get("granted_count", 0),
        "missing_proposal_count": proposal_status_histogram["missing"],
        "eligible_after_approval_count": sum(
            1
            for entry in tasks
            if entry["next_action"] == "check_readiness" and entry["eligible"]
        ),
        "blocked_after_approval_count": sum(
            1
            for entry in tasks
            if entry["next_action"] == "check_readiness" and not entry["eligible"]
        ),
        "action_queues": action_queues,
        "blocker_histogram": blocker_histogram,
        "proposal_status_histogram": proposal_status_histogram,
        "approval_age_buckets": approval_age_buckets,
        "tasks": tasks,
    }
    markdown_lines = [
        "# Promotion Approval Analytics",
        "",
        f"Generated at: {now}",
        f"Approval tasks: {yaml_packet['approval_task_count']}",
        f"History approvals: {yaml_packet['history_approval_count']}",
        f"Approve now: {len(action_queues['approve_now'])}",
        f"Apply now: {len(action_queues['apply_now'])}",
        f"Check readiness: {len(action_queues['check_readiness'])}",
    ]
    for item in tasks:
        markdown_lines.extend(
            [
                "",
                f"## Task: {item['task_id']}",
                "",
                f"next_action={item['next_action']}",
                f"proposal_status={item['proposal_status']}",
                f"approval_status={item['approval_status']}",
                f"age_bucket={item['task_age_bucket'] or 'n/a'}",
                f"blockers={','.join(item['blockers']) or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
