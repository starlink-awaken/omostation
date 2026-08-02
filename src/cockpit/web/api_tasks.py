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
import subprocess
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from cockpit.web import api_tasks_data as _task_data
from cockpit.web.api_tasks_common import (
    _COVERAGE_DRAFT_GETTERS,
    _current_controlled_command,
    _sync_task_workspace,
    _transition_task,
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


@router.post("/api/tasks/{task_id}/request-workflow")
async def request_task_workflow(task_id: str, request: Request):
    """Record a governed Workflow Mesh request without admitting or launching it."""
    group = _task_group(task_id)
    if group != "planned":
        raise HTTPException(status_code=409, detail="Only planned tasks can request a workflow")
    payload = _load_persisted_task(task_id, group)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Workflow request must be a JSON object") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Workflow request must be a JSON object")

    workflow_name = str(body.get("workflow_name") or "").strip()
    scene_binding = body.get("scene_binding")
    evidence_plan = body.get("evidence_plan")
    if not workflow_name or not isinstance(scene_binding, dict) or not isinstance(evidence_plan, list):
        raise HTTPException(
            status_code=422,
            detail="workflow_name, scene_binding, and evidence_plan are required",
        )
    try:
        from omo.workflow_promotion import request_workflow_from_task

        result = request_workflow_from_task(
            WORKSPACE_DIR,
            task_id=task_id,
            workflow_name=workflow_name,
            workflow_version=str(body.get("workflow_version") or "v1"),
            scene_binding=scene_binding,
            evidence_plan=evidence_plan,
            operation_level=body.get("operation_level"),
            actor=str(body.get("actor_ref") or "cockpit-task-center"),
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO workflow promotion is unavailable") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "source": "omo.workflow_promotion",
        **result,
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


@router.post("/api/tasks")
async def create_manual_task(request: Request):
    """Create a governed planned task from an operator's current finding."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Task request must be an object")

    title = str(body.get("title") or "").strip()
    description = str(body.get("description") or "").strip()
    priority = str(body.get("priority") or "medium").strip().lower()
    risk_level = str(body.get("risk_level") or "L1").strip().upper()
    evidence_required = body.get("evidence_required") or []
    knowledge_refs = body.get("knowledge_refs") or []
    if not title or len(title) > 200:
        raise HTTPException(status_code=422, detail="title is required and must be at most 200 characters")
    if not description or len(description) > 4000:
        raise HTTPException(status_code=422, detail="description is required and must be at most 4000 characters")
    if priority not in {"low", "medium", "high", "critical"}:
        raise HTTPException(status_code=422, detail="priority must be low, medium, high, or critical")
    if risk_level not in {"L0", "L1", "L2", "L3"}:
        raise HTTPException(status_code=422, detail="risk_level must be L0, L1, L2, or L3")
    if not isinstance(evidence_required, list) or not all(
        isinstance(item, str) and item.strip() for item in evidence_required
    ):
        raise HTTPException(status_code=422, detail="evidence_required must be a list[str]")
    if not isinstance(knowledge_refs, list) or len(knowledge_refs) > 20 or not all(
        isinstance(item, str) and item.strip() for item in knowledge_refs
    ):
        raise HTTPException(status_code=422, detail="knowledge_refs must be a list[str] with at most 20 items")
    knowledge_refs = [item.strip() for item in knowledge_refs]

    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    fingerprint = sha256(f"{title}\n{description}".encode()).hexdigest()[:10]
    task_id = f"cockpit-manual-{now}-{fingerprint}"
    approval_required = risk_level in {"L2", "L3"}
    task_data = {
        "id": task_id,
        "title": title,
        "description": description,
        "status": "pending",
        "task_type": "governance",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": knowledge_refs,
        "handoff_refs": [],
        "risk_level": risk_level,
        "allowed_operation_level": risk_level,
        "human_approval_required": approval_required,
        "source_docs": ["cockpit:operator:manual-task"],
        "entry_gate": ["确认任务范围与风险级别"],
        "evidence_required": [item.strip() for item in evidence_required] or ["任务处理结果", "相关验证或运行证据"],
        "deliverables": [description],
        "test_plan": ["按任务描述完成处理，并回写结果与证据。"],
        "priority": priority,
        "tags": ["cockpit-manual", "operator-created"],
        "metadata": {
            "created_via": "cockpit-task-center",
            "created_at": datetime.now(UTC).isoformat(),
            "operator_finding": True,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-task-center",
            source_ref=f"cockpit:manual-task:{task_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "title": created.get("title", title),
        "status": "pending",
        "risk_level": risk_level,
        "human_approval_required": approval_required,
        "source": "omo_ingress",
        "knowledge_refs": created.get("knowledge_refs", knowledge_refs),
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


@router.post("/api/tasks/{task_id}/complete-from-execution")
async def complete_task_from_execution(task_id: str):
    """Archive a successful controlled task with its generated execution artifacts."""
    group = _task_group(task_id)
    if group != "active":
        raise HTTPException(status_code=409, detail="Only active tasks can be completed from execution evidence")
    payload = _load_persisted_task(task_id, group)
    metadata = payload.get("metadata") or {}
    if metadata.get("controlled_execution") is not True:
        raise HTTPException(status_code=409, detail="Task has no controlled execution evidence")
    audit = metadata.get("execution_audit") or {}
    if audit.get("exit_code") != 0:
        raise HTTPException(status_code=409, detail="Task execution did not succeed")
    execution_ref = next(
        (ref for ref in payload.get("handoff_refs") or [] if isinstance(ref, str) and "/task-center/execution/" in ref),
        None,
    )
    log_ref = audit.get("log_ref")
    evidence_paths = [ref for ref in (execution_ref, log_ref) if isinstance(ref, str) and ref]
    if len(evidence_paths) != 2:
        raise HTTPException(status_code=409, detail="Successful execution is missing execution_ref or log_ref")
    validated = _validate_evidence_paths(evidence_paths)
    result = _transition_task(task_id, "complete", evidence_paths=validated)
    return {**result, "evidence_paths": validated, "source": "omo_controlled_execution_closeout"}


@router.post("/api/tasks/{task_id}/workflow-closeout")
async def closeout_task_workflow(task_id: str, request: Request):
    """Run the governed agent-workflow closeout and attach its run record to the task."""
    group = _task_group(task_id)
    if group not in {"active", "done", "archived/done"}:
        raise HTTPException(status_code=409, detail="Task must have an active or done execution before closeout")
    payload = _load_persisted_task(task_id, group)
    metadata = payload.get("metadata") or {}
    audit = metadata.get("execution_audit") or {}
    if metadata.get("controlled_execution") is not True or audit.get("exit_code") != 0:
        raise HTTPException(
            status_code=409, detail="A successful controlled execution is required before workflow closeout"
        )

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Workflow closeout request must be an object")
    run_id = str(body.get("run_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        raise HTTPException(
            status_code=422, detail="run_id must contain only letters, numbers, dots, underscores, or hyphens"
        )
    evidence = body.get("evidence") or []
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item.strip() for item in evidence):
        raise HTTPException(status_code=422, detail="evidence must be a list[str]")

    command = ["uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py", "closeout", run_id, "--json"]
    for item in evidence:
        command.extend(["--evidence", item.strip()])
    try:
        result = subprocess.run(
            command,
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"workflow closeout timed out: {exc}") from exc

    closeout_path = WORKSPACE_DIR / ".omo" / "_delivery" / "agent-workflows" / "runs" / f"{run_id}.yaml"
    closeout_ref = str(closeout_path.relative_to(WORKSPACE_DIR)) if closeout_path.is_file() else None
    if result.returncode == 0 and not closeout_ref:
        raise HTTPException(status_code=409, detail="workflow closeout succeeded but its run record was not found")
    if result.returncode == 0 and closeout_ref:
        try:
            from omo.omo_ingress_task_lifecycle import record_task_execution

            record_task_execution(
                WORKSPACE_DIR / ".omo",
                task_id=task_id,
                actor="cockpit-task-center",
                command=str(audit.get("command") or metadata.get("command") or "controlled execution"),
                exit_code=0,
                log_ref=str(audit.get("log_ref") or "runtime/omo/cockpit-workflow-closeout.log"),
                closeout_ref=closeout_ref,
                source_ref=f"cockpit:task:workflow-closeout:{task_id}:{run_id}",
            )
        except (ImportError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail=f"workflow closed but task evidence was not recorded: {exc}"
            ) from exc

    return {
        "id": task_id,
        "run_id": run_id,
        "status": "closed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "closeout_ref": closeout_ref,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-12000:],
        "source": "agent_workflow_closeout",
    }


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """拒绝不存在于 OMO canonical lifecycle 的伪取消状态。"""
    return _transition_task(task_id, "cancel")


# --- register split-out endpoint modules (side-effect: attach routes to shared router) ---
from cockpit.web import (
    api_tasks_queues_compute,
    api_tasks_queues_integration,
    api_tasks_queues_project,
)
