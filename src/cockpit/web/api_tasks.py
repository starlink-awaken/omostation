"""Tasks API endpoints.

提供任务管理功能。

Routes:
    GET    /api/tasks              → 任务列表
    GET    /api/tasks/:id          → 任务详情
    POST   /api/tasks/:id/pause    → 暂停任务
    POST   /api/tasks/:id/resume   → 恢复任务
    POST   /api/tasks/:id/cancel   → 取消任务
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request

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
    _transition_task,
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

router = APIRouter()


@router.post("/api/tasks/{task_id}/request-approval")
async def request_task_approval(task_id: str):
    """Create the OMO task-specific promotion approval request."""
    group = _task_group(task_id)
    if group != "planned":
        raise HTTPException(status_code=409, detail="Only planned tasks can request promotion approval")

    payload = _load_persisted_task(task_id, group)
    if not payload.get("human_approval_required"):
        raise HTTPException(status_code=409, detail="Task does not require human approval")

    approval_ref = payload.get("approval_ref")
    if isinstance(approval_ref, str) and approval_ref:
        return {
            "id": task_id,
            "status": _approval_state(payload),
            "approval_ref": approval_ref,
            "proposal_id": _approval_proposal_id(approval_ref),
            "created": False,
            "source": "omo_ingress",
        }

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    from omo.omo_governance import propose_truth_mutation
    from omo.omo_ingress_task_lifecycle import request_task_promotion_approval
    from omo.omo_promotion_request import (
        build_promotion_approval_proposal,
        build_promotion_approval_request,
        promotion_approval_ref,
    )

    approval_ref = promotion_approval_ref(task_id, now)
    task_ref = f".omo/tasks/planned/{task_id}.yaml"
    approval_record = build_promotion_approval_request(
        task_id=task_id,
        task_ref=task_ref,
        requested_operation_level=str(payload.get("allowed_operation_level") or payload.get("risk_level") or "L0"),
        requested_at=now,
        approval_ref=approval_ref,
    )
    proposal = build_promotion_approval_proposal(
        task_id=task_id,
        requested_by="cockpit-task-center",
        approval_ref=approval_ref,
    )
    try:
        proposal_record = propose_truth_mutation(WORKSPACE_DIR, proposal, now=now)
        updated = request_task_promotion_approval(
            WORKSPACE_DIR / ".omo",
            task_id=task_id,
            actor="cockpit-task-center",
            approval_ref=approval_ref,
            approval_record=approval_record,
            proposal_ref=f".omo/_truth/task-center/proposals/{proposal_record['id']}.yaml",
            source_ref=f"cockpit:task:request-approval:{task_id}",
            now=now,
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO approval broker is unavailable") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": _approval_state(updated),
        "approval_ref": approval_ref,
        "proposal_id": proposal_record["id"],
        "created": True,
        "source": "omo_ingress",
    }


@router.post("/api/tasks/{task_id}/approve")
async def approve_task(task_id: str):
    """Grant and apply the OMO promotion approval for a planned task."""
    group = _task_group(task_id)
    if group != "planned":
        raise HTTPException(status_code=409, detail="Only planned tasks can be approved")

    payload = _load_persisted_task(task_id, group)
    if not payload.get("human_approval_required"):
        raise HTTPException(status_code=409, detail="Task does not require human approval")
    approval_ref = payload.get("approval_ref")
    if not isinstance(approval_ref, str) or not approval_ref:
        raise HTTPException(status_code=409, detail="Approval request must be created first")
    if _approval_state(payload) == "granted":
        return {
            "id": task_id,
            "status": "granted",
            "approval_ref": approval_ref,
            "proposal_id": _approval_proposal_id(approval_ref),
            "created": False,
            "source": "omo_governance",
        }

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    from omo.omo_governance import apply_truth_mutation, approve_truth_mutation

    proposal_id = _approval_proposal_id(approval_ref)
    try:
        approve_truth_mutation(WORKSPACE_DIR, proposal_id, approver="cockpit-task-center", now=now)
        applied = apply_truth_mutation(WORKSPACE_DIR, proposal_id, now=now)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if applied.get("status") != "verified":
        raise HTTPException(status_code=409, detail="OMO approval was not verified")
    return {
        "id": task_id,
        "status": "granted",
        "approval_ref": approval_ref,
        "proposal_id": proposal_id,
        "created": True,
        "source": "omo_governance",
    }


@router.post("/api/tasks/{task_id}/dispatch")
async def dispatch_task_endpoint(task_id: str):
    """Create an OMO worker dispatch without launching an external process."""
    group = _task_group(task_id)
    if group != "active":
        raise HTTPException(status_code=409, detail="Only active tasks can be dispatched")

    payload = _load_persisted_task(task_id, group)
    if payload.get("human_approval_required") and _approval_state(payload) != "granted":
        raise HTTPException(status_code=409, detail="Task approval must be granted before dispatch")
    if payload.get("dispatch_id") and payload.get("run_ref"):
        return {
            "id": task_id,
            "status": payload.get("status", "in_progress"),
            "dispatch_id": payload["dispatch_id"],
            "run_ref": payload["run_ref"],
            "created": False,
            "launched": False,
            "source": "omo_worker_dispatch",
        }

    try:
        import yaml
        from omo.omo_worker_core import _default_enabled_worker_id, _dispatch_allowed_write_paths
        from omo.omo_worker_dispatch import dispatch_task

        registry_path = WORKSPACE_DIR / ".omo" / "_truth" / "registry" / "workers.yaml"
        documents = list(yaml.safe_load_all(registry_path.read_text(encoding="utf-8")))
        registry = next(
            (document for document in documents if isinstance(document, dict) and document.get("workers")),
            {},
        )
        worker_id = _default_enabled_worker_id(registry)
        result = dispatch_task(
            WORKSPACE_DIR,
            task_id,
            worker_id,
            _dispatch_allowed_write_paths(payload),
            launch=False,
            transport="cli_prompt",
            prior_evidence=list(payload.get("evidence_required") or []),
            prompt_addendum=["Cockpit created this dispatch; launch remains an explicit worker-side action."],
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO worker dispatch is unavailable") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "in_progress",
        "dispatch_id": result["dispatch_id"],
        "run_ref": result["dispatch_path"],
        "created": True,
        "launched": False,
        "source": "omo_worker_dispatch",
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

    try:
        from omo.omo_ingress_task_lifecycle import execute_controlled_task

        result = execute_controlled_task(
            WORKSPACE_DIR / ".omo",
            task_id=task_id,
            actor="cockpit-task-center",
            source_ref=f"cockpit:task:execute:{task_id}",
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


@router.get("/api/tasks")
async def get_tasks(
    status: str | None = Query(None, description="任务状态过滤"),
    limit: int = Query(100, description="返回数量限制"),
    sort: str = Query("updated", description="排序方式"),
    include_playbook_drafts: bool = Query(False, description="包含 SystemMap 操作清单任务草稿"),
    include_project_portfolio_drafts: bool = Query(False, description="包含 SystemMap 项目组合任务草稿"),
    include_verification_ready_drafts: bool = Query(False, description="包含 SystemMap 验证补证草稿"),
    include_domain_app_drafts: bool = Query(False, description="包含 SystemMap 领域应用任务草稿"),
    include_capability_gap_drafts: bool = Query(False, description="包含 SystemMap 能力缺口任务草稿"),
    include_page_maturity_drafts: bool = Query(False, description="包含 Cockpit 页面能力补齐任务草稿"),
):
    """获取任务列表。"""
    tasks = get_tasks_from_omo()
    if include_playbook_drafts:
        tasks.extend(get_playbook_task_drafts())
    if include_project_portfolio_drafts:
        tasks.extend(get_project_portfolio_task_drafts())
    if include_verification_ready_drafts:
        tasks.extend(get_verification_ready_task_drafts())
    if include_domain_app_drafts:
        tasks.extend(get_domain_app_task_drafts())
    if include_capability_gap_drafts:
        tasks.extend(get_capability_gap_task_drafts())
    if include_page_maturity_drafts:
        tasks.extend(get_page_maturity_task_drafts())

    # 过滤
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    # 排序
    if sort == "updated":
        tasks.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    elif sort == "created":
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # 限制数量
    tasks = tasks[:limit]

    return {
        "items": tasks,
        "total": len(tasks),
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
        "executes": False,
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
            "command": command.get("value"),
            "risk": risk,
            "cockpit_only": True,
            "controlled_execution": False,
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
            "controlled_execution": False,
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
        "executes": False,
    }


@router.get("/api/tasks/{task_id}/execution")
async def get_task_execution(task_id: str):
    """Return the worker artifact posture for a persisted OMO task."""
    group = _task_group(task_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Task not found in OMO queues")
    payload = _load_persisted_task(task_id, group)
    return {
        "task_id": task_id,
        "execution": _execution_snapshot(payload),
        "source": "omo-worker-artifacts",
    }


@router.post("/api/tasks/{task_id}/execution-report")
async def record_task_execution_report(task_id: str, request: Request):
    """Persist a command execution result through the OMO ingress broker."""
    group = _task_group(task_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Task not found in OMO queues")
    payload = _load_persisted_task(task_id, group)
    metadata = payload.get("metadata") or {}
    command = str(metadata.get("command") or "").strip()
    if not command or metadata.get("cockpit_only") is not True:
        raise HTTPException(
            status_code=409, detail="Only Cockpit project or domain action tasks accept execution reports"
        )

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Execution report must be an object")
    exit_code = body.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise HTTPException(status_code=422, detail="exit_code must be an integer")
    log_ref = str(body.get("log_ref") or "").strip()
    log_file = _workspace_file_ref(log_ref)
    if not log_file["valid"] or not log_file["exists"]:
        raise HTTPException(status_code=422, detail="log_ref must point to an existing workspace file")
    closeout_ref = str(body.get("closeout_ref") or "").strip()
    if closeout_ref:
        closeout_file = _workspace_file_ref(closeout_ref)
        if not closeout_file["valid"] or not closeout_file["exists"]:
            raise HTTPException(status_code=422, detail="closeout_ref must point to an existing workspace file")

    try:
        from omo.omo_ingress_task_lifecycle import record_task_execution

        artifact = record_task_execution(
            WORKSPACE_DIR / ".omo",
            task_id=task_id,
            actor="cockpit-task-center",
            command=command,
            exit_code=exit_code,
            log_ref=log_ref,
            closeout_ref=closeout_ref,
            source_ref=f"cockpit:task:execution-report:{task_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": task_id,
        "status": "recorded",
        "exit_code": exit_code,
        "execution_ref": artifact.get("execution_ref"),
        "log_ref": log_ref,
        "closeout_ref": closeout_ref or None,
        "source": "omo_ingress",
    }


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情。"""
    tasks = get_tasks_from_omo()
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@router.get("/api/tasks/{task_id}/history")
async def get_task_history(task_id: str):
    """Return OMO ingress history for a persisted task."""
    group = _task_group(task_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Task not found in OMO queues")
    return {
        "task_id": task_id,
        "items": _task_history(task_id, group),
        "source": "omo-ingress",
    }


@router.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """通过 OMO ingress 将 active 任务退回 planned。"""
    return _transition_task(task_id, "pause")


@router.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """通过 OMO ingress 将 planned 任务提升到 active。"""
    return _transition_task(task_id, "resume")


@router.post("/api/tasks/{task_id}/complete")
async def complete_task_endpoint(task_id: str, request: Request):
    """通过 OMO ingress 将 active/planned 任务归档到 done。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    evidence_paths = _validate_evidence_paths((body or {}).get("evidence_paths")) if isinstance(body, dict) else []
    return _transition_task(task_id, "complete", evidence_paths=evidence_paths or None)


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """拒绝不存在于 OMO canonical lifecycle 的伪取消状态。"""
    return _transition_task(task_id, "cancel")
