"""Cockpit tasks API — project/triage/debt/domain-app queue endpoints. Split from api_tasks.py."""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from cockpit.web import api_tasks_data as _task_data
from cockpit.web.api_system_map_catalog import (
    COCKPIT_PAGES,
    PAGE_OPERATOR_ACTION_METADATA,
    PAGE_OPERATOR_ACTIONS,
)
from cockpit.web.api_tasks_common import (
    _COVERAGE_DRAFT_GETTERS,
    _current_controlled_command,
    _sync_task_workspace,
    _transition_task,
    execute_task_endpoint,
    router,
)
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


@router.post("/api/cockpit/pages/{page_id}/actions/{action_id}/queue")
async def queue_page_operator_action(page_id: str, action_id: str):
    """承接页面目录动作为受控计划任务；Cockpit 不直接执行页面动作。"""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", page_id) or not re.fullmatch(r"[A-Za-z0-9_.-]+", action_id):
        raise HTTPException(status_code=400, detail="Invalid page or action id")

    page = next((item for item in COCKPIT_PAGES if item.get("id") == page_id), None)
    if page is None:
        raise HTTPException(status_code=404, detail="Cockpit page not found")
    if action_id not in PAGE_OPERATOR_ACTIONS.get(page_id, ()):
        raise HTTPException(status_code=404, detail="Page operator action not found")

    action_metadata = {
        "label": action_id,
        "kind": "queue",
        "risk": "medium",
        "description": "进入任务中心承接该页面动作。",
        **PAGE_OPERATOR_ACTION_METADATA.get(action_id, {}),
    }

    task_id = f"cockpit-page-action-{page_id}-{action_id}"
    existing_group = _task_group(task_id)
    title = f"页面动作：{page.get('title') or page_id} · {action_metadata['label']}"
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Page action task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {
            "id": task_id,
            "status": "pending",
            "created": False,
            "title": title,
            "action": action_id,
            "action_label": action_metadata["label"],
            "action_kind": action_metadata["kind"],
            "action_risk": action_metadata["risk"],
            "executes": False,
            "source": "omo_ingress",
        }

    task_data = {
        "id": task_id,
        "title": title,
        "description": f"进入 Cockpit 页面 {page_id}，核对并承接受控动作 {action_metadata['label']}。{action_metadata['description']}",
        "status": "pending",
        "task_type": "page_operator_action",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "source_docs": ["projects/cockpit/src/cockpit/web/api_system_map_catalog.py"],
        "entry_gate": [f"确认页面 {page_id} 当前运行状态", f"确认动作 {action_metadata['label']} 的真实执行边界"],
        "evidence_required": ["动作执行结果或阻塞原因", "相关页面/接口回执", "任务 closeout"],
        "deliverables": [f"完成页面 {page_id} 的动作 {action_metadata['label']} 承接并记录证据。"],
        "test_plan": ["在对应 Cockpit 页面核对动作入口，再按页面安全门执行或转交。"],
        "tags": ["cockpit-page-action", page_id, action_id, action_metadata["kind"], action_metadata["risk"]],
        "priority": "medium",
        "metadata": {
            "page_id": page_id,
            "operator_action": action_id,
            "operator_action_label": action_metadata["label"],
            "operator_action_kind": action_metadata["kind"],
            "operator_action_risk": action_metadata["risk"],
            "operator_action_description": action_metadata["description"],
            "created_via": "cockpit-system-map",
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-page-action",
            source_ref=f"cockpit:page-action:{page_id}:{action_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "title": created.get("title", title),
        "action": action_id,
        "action_label": action_metadata["label"],
        "action_kind": action_metadata["kind"],
        "action_risk": action_metadata["risk"],
        "executes": False,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/projects/{project_id}/actions/{action_id}/queue")
async def queue_project_action(project_id: str, action_id: str):
    """登记一个项目命令为 OMO planned task; never execute it in Cockpit."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", project_id) or not re.fullmatch(r"[A-Za-z0-9_.-]+", action_id):
        raise HTTPException(status_code=400, detail="Invalid project or action id")

    project = next((item for item in build_system_map().get("projects", []) if item.get("id") == project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found in SystemMap")
    action = next((item for item in project.get("actions") or [] if item.get("id") == action_id), None)
    if action is None:
        raise HTTPException(status_code=404, detail="Project action not found")
    if action.get("kind") != "copy_command" or not action.get("enabled"):
        raise HTTPException(status_code=409, detail="Only enabled project commands can be queued")

    task_id = f"cockpit-action-{project_id}-{action_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Project action task already exists in {existing_group}: {task_id}"
        )

    risk = str(action.get("risk") or "low")
    task_data = {
        "id": task_id,
        "title": f"项目动作：{project.get('name') or project_id} · {action.get('label') or action_id}",
        "description": f"登记并由人工确认执行：{action.get('value', '')}",
        "status": "pending",
        "task_type": "operations",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L2" if risk in {"medium", "high", "critical"} else "L1",
        "allowed_operation_level": "L2" if risk in {"medium", "high", "critical"} else "L1",
        "human_approval_required": risk in {"medium", "high", "critical"},
        "source_docs": [
            str(ref.get("target") or ref.get("path") or ref.get("label"))
            for ref in project.get("source_refs") or []
            if isinstance(ref, dict) and (ref.get("target") or ref.get("path") or ref.get("label"))
        ]
        or [f"cockpit:SystemMap:project:{project_id}"],
        "entry_gate": ["确认项目动作和风险"],
        "evidence_required": ["command exit code", "execution log", "agent-workflow closeout"],
        "deliverables": [str(action.get("value", ""))],
        "test_plan": [str(action.get("guard") or "人工确认后执行登记命令，并回写退出码与日志。")],
        "tags": ["cockpit-project-action", project_id, action_id, risk],
        "priority": "high" if risk in {"medium", "high", "critical"} else "medium",
        "metadata": {
            "project_id": project_id,
            "action_id": action_id,
            "command": action.get("value"),
            "risk": risk,
            "cockpit_only": True,
            "controlled_execution": action_id == "copy-verify-command",
            "controlled_process": action_id == "copy-start-command",
            "timeout_seconds": 900 if action_id == "copy-verify-command" else None,
        },
    }

    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-system-map",
            source_ref=f"cockpit:project-action:{project_id}:{action_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": existing_group != "planned",
        "project_id": project_id,
        "action_id": action_id,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
        "executes": action_id in {"copy-verify-command", "copy-start-command"},
    }


@router.post("/api/cockpit/roadmap/{roadmap_id}/queue")
async def queue_page_roadmap_item(roadmap_id: str):
    """将页面路线项承接为 OMO planned task，打通架构发现到执行追踪。"""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", roadmap_id):
        raise HTTPException(status_code=400, detail="Invalid roadmap id")

    roadmap_item = next(
        (item for item in build_system_map().get("roadmap", {}).get("items", []) if item.get("id") == roadmap_id),
        None,
    )
    if not isinstance(roadmap_item, dict):
        raise HTTPException(status_code=404, detail="Roadmap item not found")

    page_id = str(roadmap_item.get("cockpit_page") or "SystemMap")
    task_id = f"cockpit-roadmap-{roadmap_id}"
    existing_group = _task_group(task_id)
    title = str(roadmap_item.get("title") or roadmap_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Roadmap task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {
            "id": task_id,
            "status": "pending",
            "created": False,
            "title": title,
            "roadmap_id": roadmap_id,
            "page_id": page_id,
            "source": "omo_ingress",
        }

    problem = str(roadmap_item.get("problem") or "完成页面路线项定义的问题收口。")
    actions = [str(item) for item in roadmap_item.get("actions") or [] if str(item).strip()]
    acceptance = [str(item) for item in roadmap_item.get("acceptance") or [] if str(item).strip()]
    source_refs = [
        str(ref.get("target") or ref.get("path") or ref.get("label"))
        for ref in roadmap_item.get("source_refs") or []
        if isinstance(ref, dict) and (ref.get("target") or ref.get("path") or ref.get("label"))
    ] or ["projects/cockpit/src/cockpit/web/api_system_map.py"]
    task_data = {
        "id": task_id,
        "title": title,
        "description": problem,
        "status": "pending",
        "task_type": "page_roadmap",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "source_docs": source_refs,
        "entry_gate": [f"确认页面 {page_id} 的路线项边界"],
        "evidence_required": [*acceptance, "任务 closeout"],
        "deliverables": actions or [f"完成页面 {page_id} 的路线项 {title}。"],
        "test_plan": acceptance or ["在 SystemMap 核对页面对象、动作和验收证据。"],
        "tags": ["cockpit-page-roadmap", page_id, roadmap_id, str(roadmap_item.get("priority") or "P1")],
        "priority": "high" if roadmap_item.get("priority") == "P0" else "medium",
        "metadata": {
            "page_id": page_id,
            "roadmap_id": roadmap_id,
            "roadmap_title": title,
            "roadmap_status": roadmap_item.get("status") or "planned",
            "created_via": "cockpit-system-map",
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-page-roadmap",
            source_ref=f"cockpit:page-roadmap:{page_id}:{roadmap_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "title": created.get("title", title),
        "roadmap_id": roadmap_id,
        "page_id": page_id,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/projects/{project_id}/triage/{command_id}/queue")
async def queue_project_triage_command(project_id: str, command_id: str):
    """登记系统地图排查命令为 OMO planned task; never execute it in Cockpit."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", project_id) or not re.fullmatch(r"[A-Za-z0-9_.-]+", command_id):
        raise HTTPException(status_code=400, detail="Invalid project or triage command id")

    project = next((item for item in build_system_map().get("projects", []) if item.get("id") == project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found in SystemMap")
    command = next((item for item in project.get("triage_commands") or [] if item.get("id") == command_id), None)
    if command is None:
        raise HTTPException(status_code=404, detail="Project triage command not found")
    if command.get("kind") != "copy_command" or not command.get("enabled"):
        raise HTTPException(status_code=409, detail="Only enabled triage commands can be queued")

    task_id = f"cockpit-triage-{project_id}-{command_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Project triage task already exists in {existing_group}: {task_id}"
        )

    risk = str(command.get("risk") or "low")
    probe_match = re.search(r"for port in ([^;]+);", str(command.get("value") or ""))
    probe_ports = [int(value) for value in (probe_match.group(1).split() if probe_match else []) if value.isdigit()]
    controlled_runtime_probe = command_id == "runtime-check-ports" and bool(probe_ports)
    controlled_verification = command_id == "verification-rerun" and str(command.get("value") or "").startswith('cd "')
    task_data = {
        "id": task_id,
        "title": f"项目排查：{project.get('name') or project_id} · {command.get('label') or command_id}",
        "description": str(command.get("reason") or "登记系统地图排查命令，并由人工确认执行。"),
        "status": "pending",
        "task_type": "operations",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L2" if risk in {"medium", "high", "critical"} else "L1",
        "allowed_operation_level": "L2" if risk in {"medium", "high", "critical"} else "L1",
        "human_approval_required": risk in {"medium", "high", "critical"},
        "source_docs": [f"cockpit:SystemMap:triage:{project_id}:{command_id}"],
        "entry_gate": ["确认项目排查命令和风险"],
        "evidence_required": ["command exit code", "execution log", "agent-workflow closeout"],
        "deliverables": [str(command.get("value") or "")],
        "test_plan": [str(command.get("guard") or "人工确认后执行登记命令，并回写退出码与日志。")],
        "tags": ["cockpit-project-triage", project_id, command_id, risk],
        "priority": "high" if risk in {"medium", "high", "critical"} else "medium",
        "metadata": {
            "project_id": project_id,
            "command_id": command_id,
            "action_id": (
                "copy-verify-command"
                if controlled_verification
                else "runtime-check-ports"
                if controlled_runtime_probe
                else None
            ),
            "command": command.get("value"),
            "probe_ports": probe_ports,
            "risk": risk,
            "cockpit_only": True,
            "controlled_execution": controlled_verification or controlled_runtime_probe,
            "timeout_seconds": 900 if controlled_verification else 120 if controlled_runtime_probe else None,
        },
    }

    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-system-map",
            source_ref=f"cockpit:project-triage:{project_id}:{command_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": existing_group != "planned",
        "project_id": project_id,
        "command_id": command_id,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
        "executes": False,
    }


@router.post("/api/cockpit/triage/queue")
async def queue_verification_triage(request: Request):
    """批量登记验证或运行排查命令为 planned tasks; never execute in Cockpit."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Triage queue request must be an object")

    category = str(body.get("category") or "verification")
    requested_command_id = body.get("command_id")
    project_ids = body.get("project_ids")
    if category not in {"verification", "runtime"}:
        raise HTTPException(status_code=400, detail="Only verification or runtime triage can be queued in bulk")
    if requested_command_id is not None and not isinstance(requested_command_id, str):
        raise HTTPException(status_code=422, detail="command_id must be a string")
    if requested_command_id is not None and not re.fullmatch(r"[A-Za-z0-9_.-]+", requested_command_id):
        raise HTTPException(status_code=400, detail="Invalid triage command id")
    if project_ids is not None and (
        not isinstance(project_ids, list) or not all(isinstance(item, str) for item in project_ids)
    ):
        raise HTTPException(status_code=422, detail="project_ids must be a list[str]")

    command_ids = (
        [requested_command_id]
        if requested_command_id
        else ["verification-rerun"]
        if category == "verification"
        else ["runtime-check-ports", "runtime-find-registry"]
    )
    allowed_projects = set(project_ids or [])
    candidates = []
    for project in build_system_map().get("projects", []):
        project_id = project.get("id")
        if not isinstance(project_id, str) or (allowed_projects and project_id not in allowed_projects):
            continue
        command = next(
            (
                item
                for candidate_command_id in command_ids
                for item in project.get("triage_commands") or []
                if item.get("category") == category and item.get("id") == candidate_command_id and item.get("enabled")
            ),
            None,
        )
        if command:
            candidates.append((project_id, command["id"]))

    queued = []
    skipped = []
    errors = []
    for project_id, candidate_command_id in candidates:
        try:
            queued.append(await queue_project_triage_command(project_id, candidate_command_id))
        except HTTPException as exc:
            item = {"project_id": project_id, "command_id": candidate_command_id, "detail": str(exc.detail)}
            if exc.status_code == 409:
                skipped.append(item)
            else:
                errors.append(item)

    return {
        "category": category,
        "command_id": requested_command_id,
        "command_ids": command_ids,
        "requested_projects": sorted(allowed_projects),
        "candidates": len(candidates),
        "queued": queued,
        "skipped": skipped,
        "errors": errors,
        "executes": False,
        "summary": {
            "queued": len(queued),
            "skipped": len(skipped),
            "errors": len(errors),
        },
    }


@router.post("/api/cockpit/triage/execute")
async def execute_verification_triage(request: Request):
    """Execute approved controlled triage tasks and return per-project evidence."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Triage execution request must be an object")

    category = str(body.get("category") or "verification")
    if category not in {"verification", "runtime"}:
        raise HTTPException(status_code=400, detail="Only verification or runtime triage can be executed")
    raw_limit = body.get("limit", 8)
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or not 1 <= raw_limit <= 8:
        raise HTTPException(status_code=422, detail="limit must be an integer between 1 and 8")
    project_ids = body.get("project_ids")
    if project_ids is not None and (
        not isinstance(project_ids, list) or not all(isinstance(item, str) for item in project_ids)
    ):
        raise HTTPException(status_code=422, detail="project_ids must be a list[str]")

    allowed_projects = set(project_ids or [])
    candidates: list[dict[str, str]] = []
    for project in build_system_map().get("projects", []):
        project_id = project.get("id")
        if not isinstance(project_id, str) or (allowed_projects and project_id not in allowed_projects):
            continue
        command = next(
            (
                item
                for item in project.get("triage_commands") or []
                if item.get("category") == category
                and item.get("enabled")
                and (
                    item.get("id") == "verification-rerun"
                    if category == "verification"
                    else item.get("id") == "runtime-check-ports"
                )
            ),
            None,
        )
        task_id = ((command or {}).get("task") or {}).get("task_id") if isinstance(command, dict) else None
        command_value = command.get("value") if isinstance(command, dict) else None
        if not isinstance(task_id, str) or not isinstance(command_value, str) or _task_group(task_id) != "active":
            continue
        try:
            task_data = _load_persisted_task(task_id, "active")
        except HTTPException:
            continue
        metadata = task_data.get("metadata") or {}
        audit = metadata.get("execution_audit") or {}
        if metadata.get("controlled_execution") is not True or audit.get("exit_code") == 0:
            continue
        if category == "runtime" and _approval_state(task_data) != "granted":
            continue
        candidates.append({"project_id": project_id, "task_id": task_id, "command": command_value})

    selected = candidates[:raw_limit]
    if not selected:
        return {
            "category": category,
            "executed": [],
            "skipped": [],
            "errors": [],
            "summary": {"candidates": len(candidates), "selected": 0, "succeeded": 0, "failed": 0},
            "source": "omo_controlled_execution",
        }

    from omo.omo_ingress_task_lifecycle import execute_controlled_task

    executed: list[dict] = []
    errors: list[dict] = []
    for candidate in selected:
        try:
            result = execute_controlled_task(
                WORKSPACE_DIR / ".omo",
                task_id=candidate["task_id"],
                actor="cockpit-system-map-batch",
                timeout_seconds=900 if category == "verification" else 120,
                source_ref=f"cockpit:triage:execute:{candidate['task_id']}",
                command_override=candidate["command"],
            )
        except (OSError, ValueError, TimeoutError) as exc:
            errors.append({"project_id": candidate["project_id"], "task_id": candidate["task_id"], "detail": str(exc)})
        else:
            executed.append({"project_id": candidate["project_id"], "task_id": candidate["task_id"], **result})

    succeeded = sum(1 for item in executed if item.get("exit_code") == 0)
    return {
        "category": category,
        "executed": executed,
        "skipped": candidates[raw_limit:],
        "errors": errors,
        "summary": {
            "candidates": len(candidates),
            "selected": len(selected),
            "succeeded": succeeded,
            "failed": len(executed) - succeeded + len(errors),
        },
        "source": "omo_controlled_execution",
    }


@router.post("/api/cockpit/debt/{debt_id}/queue")
async def queue_debt_task(debt_id: str):
    """将技术债务账本中的一项正式承接为 OMO planned 任务。"""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", debt_id):
        raise HTTPException(status_code=400, detail="Invalid debt id")

    from cockpit.dashboard.helpers import load_debt

    item = next((candidate for candidate in load_debt().get("items", []) if candidate.get("id") == debt_id), None)
    if not isinstance(item, dict):
        raise HTTPException(status_code=404, detail="Debt item not found")

    task_id = f"cockpit-debt-{debt_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Debt task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "source": "omo_ingress"}

    severity = str(item.get("severity") or "P2").upper()
    priority = {"P0": "critical", "P1": "high", "P2": "medium"}.get(severity, "low")
    risk_level = "L2" if severity in {"P0", "P1"} else "L1"
    title = str(item.get("title") or debt_id).strip()
    dimension = str(item.get("dimension") or "unknown").strip()
    owner = str(item.get("owner") or "unassigned").strip()
    evidence_refs = item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else []
    source_docs = [str(ref) for ref in evidence_refs if str(ref).strip()] or [f"cockpit:debt:{debt_id}"]
    task_data = {
        "id": task_id,
        "title": f"治理技术债务：{title}",
        "description": f"处理 {dimension} 维度技术债务“{title}”，确认影响范围、责任人和关闭证据。当前 owner：{owner}。",
        "status": "pending",
        "task_type": "governance",
        "assigned_to": owner if owner != "unassigned" else None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": risk_level,
        "allowed_operation_level": risk_level,
        "human_approval_required": risk_level in {"L2", "L3"},
        "source_docs": source_docs,
        "entry_gate": ["确认债务范围、影响面和责任人"],
        "evidence_required": ["债务处理结果", "验证或治理证据", "closeout 记录"],
        "deliverables": [f"完成技术债务 {debt_id} 的治理处理并回写结果。"],
        "test_plan": ["按处理方案完成验证，并将结果与证据回写到任务 closeout。"],
        "priority": priority,
        "tags": ["cockpit-debt", debt_id, dimension, severity],
        "metadata": {
            "created_via": "cockpit-debt-ledger",
            "debt_id": debt_id,
            "dimension": dimension,
            "owner": owner,
            "severity": severity,
            "source_ref": f"cockpit:debt:{debt_id}",
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-task-center",
            source_ref=f"cockpit:debt:{debt_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "title": created.get("title", task_data["title"]),
        "status": "pending",
        "created": True,
        "risk_level": risk_level,
        "human_approval_required": task_data["human_approval_required"],
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/domain-apps/{app_id}/actions/{action_id}/queue")
async def queue_domain_app_action(app_id: str, action_id: str):
    """登记领域应用命令为 OMO planned task; never execute it in Cockpit."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", app_id) or not re.fullmatch(r"[A-Za-z0-9_.-]+", action_id):
        raise HTTPException(status_code=400, detail="Invalid domain app or action id")

    app = next((item for item in build_domain_apps().get("items", []) if item.get("id") == app_id), None)
    if app is None:
        raise HTTPException(status_code=404, detail="Domain app not found")
    action = next((item for item in app.get("actions") or [] if item.get("id") == action_id), None)
    if action is None:
        raise HTTPException(status_code=404, detail="Domain app action not found")
    if action.get("kind") != "copy_command" or not action.get("enabled"):
        raise HTTPException(status_code=409, detail="Only enabled domain app commands can be queued")

    task_id = f"cockpit-domain-app-{app_id}-{action_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Domain app action task already exists in {existing_group}: {task_id}"
        )

    risk = str(action.get("risk") or "low")
    task_data = {
        "id": task_id,
        "title": f"领域应用动作：{app.get('name') or app_id} · {action.get('label') or action_id}",
        "description": f"登记并由人工确认执行：{action.get('value', '')}",
        "status": "pending",
        "task_type": "operations",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L2" if risk in {"medium", "high", "critical"} else "L1",
        "allowed_operation_level": "L2" if risk in {"medium", "high", "critical"} else "L1",
        "human_approval_required": risk in {"medium", "high", "critical"},
        "source_docs": [
            str(path.get("path"))
            for path in (app.get("paths") or {}).values()
            if isinstance(path, dict) and path.get("path")
        ]
        or [f"cockpit:DomainApps:app:{app_id}"],
        "entry_gate": ["确认领域应用动作、边界和风险"],
        "evidence_required": ["command exit code", "execution log", "domain app audit", "agent-workflow closeout"],
        "deliverables": [str(action.get("value", ""))],
        "test_plan": [str(action.get("guard") or "人工确认后执行登记命令，并回写退出码、领域审计和 closeout。")],
        "tags": ["cockpit-domain-app-action", app_id, action_id, risk],
        "priority": "high" if risk in {"medium", "high", "critical"} else "medium",
        "metadata": {
            "domain_app_id": app_id,
            "action_id": action_id,
            "command": action.get("value"),
            "risk": risk,
            "cockpit_only": True,
            "controlled_execution": action_id == "copy-verify",
            "timeout_seconds": 900 if action_id == "copy-verify" else None,
        },
    }

    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-domain-apps",
            source_ref=f"cockpit:domain-app-action:{app_id}:{action_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": existing_group != "planned",
        "app_id": app_id,
        "action_id": action_id,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
        "executes": action_id == "copy-verify",
    }


@router.post("/api/cockpit/domain-apps/{app_id}/verify")
async def execute_domain_app_verification(app_id: str):
    """Promote and run the explicitly allowlisted domain-app verification action."""
    queued = await queue_domain_app_action(app_id, "copy-verify")
    task_id = str(queued["id"])
    try:
        promoted = _transition_task(task_id, "resume")
        executed = await execute_task_endpoint(task_id)
    except HTTPException:
        raise
    return {
        **queued,
        **promoted,
        **executed,
        "source": "omo_domain_app_controlled_verification",
    }
