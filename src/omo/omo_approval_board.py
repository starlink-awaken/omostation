from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


from .omo_shared import load_yaml
from .omo_io import write_text_atomic


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_tasks(workspace_root: Path) -> list[dict[str, Any]]:
    task_roots = (
        ("planned", workspace_root / ".omo" / "tasks" / "planned"),
        ("remediation", workspace_root / ".omo" / "tasks" / "remediation"),
    )
    entries: list[dict[str, Any]] = []
    for root_name, task_dir in task_roots:
        for path in sorted(task_dir.glob("OPC-P6-SELF-EVOLUTION-*.yaml")):
            payload = load_yaml(path)
            entries.append(
                {
                    "task_id": payload.get("id", path.stem),
                    "task_ref": str(path.relative_to(workspace_root)),
                    "task_root": root_name,
                    "status": payload.get("status", "planned"),
                    "approval_required": bool(
                        payload.get(
                            "approval_required",
                            payload.get("human_approval_required", False),
                        )
                    ),
                    "approval_state": payload.get("approval_state", "awaiting_human"),
                    "latest_week": payload.get("latest_week"),
                    "loop_history_ref": payload.get("loop_history_ref"),
                    "created_at": payload.get("created_at"),
                    "title": payload.get("title"),
                    "review_note": payload.get("review_note"),
                }
            )
    return entries


def _load_approval_queue_index(workspace_root: Path) -> dict[str, dict[str, Any]]:
    queue_path = (
        workspace_root
        / ".omo"
        / "workers"
        / "promotion"
        / "approval-queue"
        / "current.yaml"
    )
    if not queue_path.exists():
        return {}
    try:
        payload = load_yaml(queue_path)
    except Exception:
        return {}
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        if isinstance(task_id, str) and task_id:
            index[task_id] = item
    return index


def _board_task_entry(
    base: dict[str, Any], queue_entry: dict[str, Any] | None
) -> dict[str, Any]:
    queue_entry = queue_entry or {}
    blockers = queue_entry.get("blockers")
    if not isinstance(blockers, list):
        blockers = []

    if base.get("task_root") == "remediation":
        return {
            **base,
            "approval_status": queue_entry.get("approval_status")
            or base.get("approval_state")
            or "granted",
            "proposal_status": queue_entry.get("proposal_status"),
            "eligible": False,
            "blockers": blockers,
            "next_action": "execute_review_lane",
        }

    return {
        **base,
        "approval_status": queue_entry.get("approval_status"),
        "proposal_status": queue_entry.get("proposal_status"),
        "eligible": queue_entry.get("eligible"),
        "blockers": blockers,
        "next_action": queue_entry.get("next_action", "await_human_review"),
    }


def _queue_summary(tasks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "awaiting_human_count": sum(
            1 for item in tasks if item.get("approval_state") == "awaiting_human"
        ),
        "approval_pending_count": sum(
            1
            for item in tasks
            if item.get("task_root") == "planned"
            and item.get("approval_status") not in {"granted", "verified"}
        ),
        "approval_granted_blocked_count": sum(
            1
            for item in tasks
            if item.get("task_root") == "planned"
            and item.get("approval_status") == "granted"
            and not item.get("eligible")
        ),
        "approval_ready_count": sum(
            1 for item in tasks if item.get("next_action") == "promote_apply"
        ),
        "task_policy_blocked_count": sum(
            1 for item in tasks if "task_policy_blocked" in item.get("blockers", [])
        ),
        "phase_blocked_count": sum(
            1 for item in tasks if "phase_mismatch" in item.get("blockers", [])
        ),
        "remediation_count": sum(
            1 for item in tasks if item.get("task_root") == "remediation"
        ),
        "review_lane_count": sum(1 for item in tasks if item.get("status") == "review"),
    }


def build_approval_board(workspace_root: Path) -> dict[str, Any]:
    queue_index = _load_approval_queue_index(workspace_root)
    tasks = [
        _board_task_entry(item, queue_index.get(str(item["task_id"])))
        for item in _load_tasks(workspace_root)
    ]
    loop_history_path = (
        workspace_root / ".omo" / "_control" / "evolution" / "loop" / "history.json"
    )
    latest_week_from_loop: str | None = None
    if loop_history_path.exists():
        try:
            payload = load_yaml(loop_history_path)
            latest_week_from_loop = (
                payload.get("summary", {}).get("latest_week")
                if isinstance(payload, dict)
                else None
            )
        except Exception:
            latest_week_from_loop = None

    latest_week_task = next(
        (item["latest_week"] for item in reversed(tasks) if item.get("latest_week")),
        None,
    )
    queue_summary = _queue_summary(tasks)
    return {
        "generated_at": _now_iso(),
        "tasks": tasks,
        "summary": {
            "task_count": len(tasks),
            "approval_required_count": sum(
                1 for item in tasks if item["approval_required"]
            ),
            **queue_summary,
            "latest_week": latest_week_from_loop or latest_week_task,
            "latest_week_source": (
                "loop_history"
                if latest_week_from_loop
                else ("self_evolve_task" if latest_week_task else None)
            ),
            "loop_history_ref": str(loop_history_path.relative_to(workspace_root)),
            "approval_queue_ref": ".omo/workers/promotion/approval-queue/current.yaml",
        },
    }


def write_approval_board(
    workspace_root: Path, board: dict[str, Any]
) -> tuple[Path, Path]:
    out_dir = workspace_root / ".omo" / "_control" / "evolution" / "approval-board"
    json_path = out_dir / "current.json"
    md_path = out_dir / "current.md"
    write_text_atomic(json_path, json.dumps(board, ensure_ascii=False, indent=2) + "\n")

    summary = board["summary"]
    lines = [
        "# OPC P6 approval board",
        "",
        f"Generated: {board['generated_at']}",
        "",
        f"- task_count: {summary['task_count']}",
        f"- awaiting_human_count: {summary['awaiting_human_count']}",
        f"- approval_pending_count: {summary['approval_pending_count']}",
        f"- approval_granted_blocked_count: {summary['approval_granted_blocked_count']}",
        f"- approval_ready_count: {summary['approval_ready_count']}",
        f"- task_policy_blocked_count: {summary['task_policy_blocked_count']}",
        f"- phase_blocked_count: {summary['phase_blocked_count']}",
        f"- remediation_count: {summary['remediation_count']}",
        f"- review_lane_count: {summary['review_lane_count']}",
        f"- approval_required_count: {summary['approval_required_count']}",
        f"- latest_week: {summary['latest_week']}",
        f"- latest_week_source: {summary.get('latest_week_source', 'self_evolve_task')}",
        "",
        "| Task | Root | Status | Approval | Queue Status | Blockers | Next Action | Latest Week | Ref |",
        "|------|------|--------|----------|--------------|----------|-------------|-------------|-----|",
    ]
    for item in board["tasks"]:
        approval_label = item.get("approval_status") or item.get("approval_state")
        blockers = ", ".join(item.get("blockers", [])) or "-"
        queue_status = (
            "ready"
            if item.get("next_action") == "promote_apply"
            else ("blocked" if blockers != "-" else "pending")
        )
        lines.append(
            f"| {item['task_id']} | {item.get('task_root') or '-'} | {item['status']} | {approval_label} | {queue_status} | {blockers} | {item.get('next_action') or '-'} | {item.get('latest_week') or '-'} | `{item['task_ref']}` |"
        )
    write_text_atomic(md_path, "\n".join(lines) + "\n")
    return json_path, md_path
