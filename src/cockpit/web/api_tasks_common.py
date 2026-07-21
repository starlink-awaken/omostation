"""Cockpit tasks API — shared router, dependencies and helpers.

Split out of api_tasks.py so endpoint groups can live in sibling modules while sharing one APIRouter (god-module SRP split).
"""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from cockpit.web import api_tasks_data as _task_data
from cockpit.web.api_tasks_data import (
    WORKSPACE_DIR,
    _approval_proposal_id,
    _approval_state,
    _draft_to_planned_task,
    _execution_snapshot,
    _get_task_draft,
    _load_persisted_task,
    _task_group,
    _task_history,
    _validate_evidence_paths,
    _workspace_file_ref,
    build_domain_apps,
    build_system_map,
    get_capability_gap_task_drafts,
    get_domain_app_task_drafts,
    get_page_maturity_task_drafts,
    get_playbook_task_drafts,
    get_project_portfolio_task_drafts,
    get_tasks_from_omo,
    get_verification_ready_task_drafts,
)
from cockpit.web.api_tasks_data import (
    _transition_task as _data_transition_task,
)


async def _sync_task_workspace() -> None:
    """Keep the route module and data layer on one workspace root."""
    _task_data.WORKSPACE_DIR = WORKSPACE_DIR


router = APIRouter(dependencies=[Depends(_sync_task_workspace)])


def _transition_task(task_id: str, action: str, evidence_paths: list[str] | None = None) -> dict:
    """Pass route-layer resolvers into the shared OMO transition primitive."""
    return _data_transition_task(
        task_id,
        action,
        evidence_paths=evidence_paths,
        task_group_fn=_task_group,
        load_persisted_task_fn=_load_persisted_task,
        approval_state_fn=_approval_state,
    )


def _current_controlled_command(metadata: dict) -> str | None:
    """Resolve a current SystemMap command so retries do not run stale task text."""
    if metadata.get("action_id") != "copy-verify-command":
        return None
    project_id = metadata.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        return None
    project = next(
        (item for item in build_system_map().get("projects", []) if item.get("id") == project_id),
        None,
    )
    if not isinstance(project, dict):
        return None
    command_id = metadata.get("command_id")
    if isinstance(command_id, str) and command_id:
        current = next(
            (item for item in project.get("triage_commands") or [] if item.get("id") == command_id),
            None,
        )
    else:
        current = next((item for item in project.get("actions") or [] if item.get("id") == "copy-verify-command"), None)
    value = current.get("value") if isinstance(current, dict) else None
    return value if isinstance(value, str) and value.strip() else None


_COVERAGE_DRAFT_GETTERS = {
    "project_portfolio": get_project_portfolio_task_drafts,
    "verification_ready": get_verification_ready_task_drafts,
    "domain_apps": get_domain_app_task_drafts,
    "capability_gaps": get_capability_gap_task_drafts,
    "page_maturity": get_page_maturity_task_drafts,
    "playbooks": get_playbook_task_drafts,
}


@router.post("/api/tasks/drafts/{draft_id}/promote")
async def promote_task_draft(draft_id: str):
    """将 SystemMap 只读草稿经 OMO ingress 转为 planned 任务。"""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", draft_id):
        raise HTTPException(status_code=400, detail="Invalid draft id")

    draft = _get_task_draft(draft_id)
    if draft is None or draft.get("read_only") is not True:
        raise HTTPException(status_code=404, detail="SystemMap task draft not found")

    task_data = _draft_to_planned_task(draft)
    task_id = task_data["id"]
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Promoted task already exists in {existing_group}: {task_id}")

    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-task-center",
            source_ref=f"cockpit:draft:{draft_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": existing_group != "planned",
        "draft_id": draft_id,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
    }


@router.post("/api/tasks/{task_id}/execute")
async def execute_task_endpoint(task_id: str):
    """Run an explicitly allowlisted low-risk verification through OMO."""
    group = _task_group(task_id)
    if group != "active":
        raise HTTPException(status_code=409, detail="Only active tasks can be controlled-executed")
    payload = _load_persisted_task(task_id, group)
    if payload.get("human_approval_required") and _approval_state(payload) != "granted":
        raise HTTPException(status_code=409, detail="Task approval must be granted before execution")
    metadata = payload.get("metadata") or {}
    if metadata.get("controlled_execution") is not True:
        raise HTTPException(status_code=409, detail="Task is not eligible for controlled execution")
    default_timeout = 900 if metadata.get("action_id") == "copy-verify-command" else 120
    timeout_seconds = metadata.get("timeout_seconds", default_timeout)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
        timeout_seconds = default_timeout

    try:
        from omo.omo_ingress_task_lifecycle import execute_controlled_task

        execute_kwargs: dict[str, object] = {
            "task_id": task_id,
            "actor": "cockpit-task-center",
            "timeout_seconds": timeout_seconds,
            "source_ref": f"cockpit:task:execute:{task_id}",
        }
        current_command = _current_controlled_command(metadata)
        if current_command:
            execute_kwargs["command_override"] = current_command
        result = execute_controlled_task(
            WORKSPACE_DIR / ".omo",
            **execute_kwargs,
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO controlled execution is unavailable") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": task_id,
        "status": "recorded",
        "exit_code": result["exit_code"],
        "log_ref": result["log_ref"],
        "execution_ref": result.get("execution_ref"),
        "timed_out": result.get("timed_out", False),
        "source": "omo_controlled_execution",
    }
