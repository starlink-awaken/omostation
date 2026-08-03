from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .omo_shared import load_yaml, load_yaml_required


def _load_yaml(path: Path) -> dict:
    return load_yaml(path)


def _load_yaml_required(path: Path) -> dict:
    return load_yaml_required(path)


def _parse_iso8601(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def evaluate_promotion_approval(
    root: Path,
    *,
    approval_ref: str | None,
    task_id: str,
    task_ref: str,
) -> dict[str, Any]:
    if not approval_ref:
        return {"approval_ready": False, "blocker": "approval_missing"}
    if not approval_ref.endswith(".yaml"):
        return {"approval_ready": False, "blocker": "approval_invalid"}

    approval_path = root / approval_ref
    try:
        approval = _load_yaml(approval_path)
    except (FileNotFoundError, OSError):
        return {"approval_ready": False, "blocker": "approval_invalid"}

    if approval.get("task_id") != task_id:
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("approval_status") != "granted":
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("approval_scope") != "task.promote_apply":
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("refs", {}).get("task_ref") != task_ref:
        return {"approval_ready": False, "blocker": "approval_invalid"}
    return {"approval_ready": True, "blocker": None}


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


def _analytics_task_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    next_action_order = {"approve": 0, "apply": 1, "check_readiness": 2, "none": 3}
    age_order = {"d3_plus": 0, "d1_to_d3": 1, "lt_1d": 2, None: 3}
    return (
        next_action_order.get(str(item["next_action"]), 99),
        age_order.get(item["task_age_bucket"], 99),
        str(item["task_id"]),
    )


def build_promotion_approval_analytics_packet(
    root: Path, *, omo_dir: str | Path = ".omo", now: str
) -> dict[str, Any]:
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
    tasks: list[dict[str, Any]] = []

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

    tasks.sort(key=_analytics_task_sort_key)

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


def _is_promotion_approval_artifact(path: Path) -> bool:
    return "-promotion-approval-" in path.name and path.suffix == ".yaml"


def _proposal_payload(root: Path, proposal_ref: Path) -> dict | None:
    proposal_path = root / proposal_ref
    if not proposal_path.exists():
        return None
    return _load_yaml(proposal_path)


def _proposal_status(root: Path, proposal_ref: Path) -> str:
    proposal = _proposal_payload(root, proposal_ref)
    if proposal is None:
        return "missing"
    return str(proposal.get("status", "missing"))


def _history_entry(root: Path, omo_ref: Path, approval_path: Path) -> dict[str, Any]:
    approval = _load_yaml(approval_path)
    required_fields = [
        ("approval_id", approval.get("approval_id")),
        ("task_id", approval.get("task_id")),
        ("requested_at", approval.get("requested_at")),
        ("approval_status", approval.get("approval_status")),
        ("refs.task_ref", approval.get("refs", {}).get("task_ref")),
        ("refs.readiness_ref", approval.get("refs", {}).get("readiness_ref")),
    ]
    for field_name, field_value in required_fields:
        if field_value is None:
            raise ValueError(f"missing required promotion approval field: {field_name}")

    proposal_id = f"{approval['approval_id']}-proposal"
    proposal_ref = (
        omo_ref / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml"
    )
    proposal = _proposal_payload(root, proposal_ref)
    return {
        "approval_id": approval["approval_id"],
        "approval_ref": str(omo_ref / "workers" / "runs" / approval_path.name),
        "task_id": approval["task_id"],
        "task_ref": approval["refs"]["task_ref"],
        "requested_at": approval["requested_at"],
        "approval_status": approval["approval_status"],
        "proposal_id": proposal_id,
        "proposal_ref": str(proposal_ref),
        "proposal_status": "missing"
        if proposal is None
        else str(proposal.get("status", "missing")),
        "approver": approval.get("approver"),
        "approved_at": approval.get("approved_at"),
        "applied_at": None if proposal is None else proposal.get("applied_at"),
        "readiness_ref": approval["refs"]["readiness_ref"],
    }


def build_promotion_approval_history(
    root: Path, omo_dir: str | Path = ".omo", now: str = "2026-06-03T00:15:00Z"
) -> dict[str, Any]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    entries = [
        _history_entry(root, omo_ref, path)
        for path in sorted(runs_dir.glob("*-promotion-approval-*.yaml"))
        if _is_promotion_approval_artifact(path)
    ]
    entries.sort(
        key=lambda item: (_parse_iso8601(item["requested_at"]), item["approval_id"]),
        reverse=True,
    )

    latest = entries[0] if entries else None
    prior = entries[1] if len(entries) > 1 else None
    yaml_packet = {
        "generated_at": now,
        "latest_approval_id": latest["approval_id"] if latest else None,
        "latest_approval_ref": latest["approval_ref"] if latest else None,
        "prior_approval_id": prior["approval_id"] if prior else None,
        "prior_approval_ref": prior["approval_ref"] if prior else None,
        "approval_count": len(entries),
        "requested_count": sum(
            1
            for entry in entries
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1
            for entry in entries
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "approved"
        ),
        "granted_count": sum(
            1 for entry in entries if entry["approval_status"] == "granted"
        ),
        "approvals": entries,
    }
    markdown_lines = [
        "# Promotion Approval History",
        "",
        f"Generated at: {now}",
        f"Latest approval: {yaml_packet['latest_approval_id'] or 'none'}",
        f"Prior approval: {yaml_packet['prior_approval_id'] or 'none'}",
        f"Approval count: {yaml_packet['approval_count']}",
    ]
    for entry in entries:
        markdown_lines.extend(
            [
                "",
                f"## Approval: {entry['approval_id']}",
                "",
                f"task_id={entry['task_id']}",
                f"approval_status={entry['approval_status']}",
                f"proposal_status={entry['proposal_status']}",
                f"task_ref={entry['task_ref']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}


_PROPOSAL_STATUS_ORDER = {"proposed": 0, "approved": 1, "verified": 2, "missing": 3}


def _ordered_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        tasks,
        key=lambda item: (
            0 if item["blockers"] else 1,
            _PROPOSAL_STATUS_ORDER.get(str(item["proposal_status"]), 99),
            str(item["task_id"]),
        ),
    )


def build_promotion_approval_status_packet(
    *, generated_at: str, tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    ordered = _ordered_tasks(tasks)
    return {
        "generated_at": generated_at,
        "approval_task_count": len(ordered),
        "requested_count": sum(
            1
            for entry in ordered
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1
            for entry in ordered
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "approved"
        ),
        "granted_count": sum(
            1 for entry in ordered if entry["approval_status"] == "granted"
        ),
        "tasks": ordered,
    }


def _operator_action(entry: dict[str, Any]) -> str:
    if entry["proposal_status"] == "proposed":
        return "run governance approve"
    if entry["proposal_status"] == "approved":
        return "run governance apply"
    return "approval blocker cleared; check readiness"


def render_promotion_approval_status_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Promotion Approval Status",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Approval tasks: {packet['approval_task_count']}",
        f"Requested: {packet['requested_count']}",
        f"Approved pending apply: {packet['approved_pending_apply_count']}",
        f"Granted: {packet['granted_count']}",
    ]
    for entry in packet["tasks"]:
        lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"proposal_status={entry['proposal_status']}",
                f"approval_status={entry['approval_status']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
                f"action={_operator_action(entry)}",
            ]
        )
    return "\n".join(lines) + "\n"
