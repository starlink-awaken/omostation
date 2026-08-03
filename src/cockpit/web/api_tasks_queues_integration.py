"""Cockpit tasks API — integration/workflow queue endpoints (coverage, ecos, metaos, proposals, alerts, research, engine, governance). Split from api_tasks.py."""

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
    promote_task_draft,
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


@router.post("/api/cockpit/coverage/queue")
async def queue_coverage_drafts(request: Request):
    """Batch-promote read-only coverage drafts into OMO planned tasks."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Coverage queue request must be an object")

    category = str(body.get("category") or "all")
    if category != "all" and category not in _COVERAGE_DRAFT_GETTERS:
        raise HTTPException(status_code=400, detail=f"Unsupported coverage category: {category}")

    raw_limit = body.get("limit", 40)
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or not 1 <= raw_limit <= 100:
        raise HTTPException(status_code=422, detail="limit must be an integer between 1 and 100")

    categories = list(_COVERAGE_DRAFT_GETTERS) if category == "all" else [category]
    drafts: list[dict] = []
    for name in categories:
        drafts.extend(_COVERAGE_DRAFT_GETTERS[name](limit=raw_limit))

    queued: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    # `limit` is applied per coverage dimension so an early category cannot
    # starve later dimensions when the caller asks for `all`.
    for draft in drafts:
        draft_id = str(draft.get("id") or "")
        if not draft_id:
            errors.append({"id": None, "detail": "Draft has no id"})
            continue
        try:
            result = await promote_task_draft(draft_id)
        except HTTPException as exc:
            if exc.status_code == 409:
                skipped.append({"id": draft_id, "detail": exc.detail})
            else:
                errors.append({"id": draft_id, "detail": exc.detail})
        except (OSError, ValueError) as exc:
            errors.append({"id": draft_id, "detail": str(exc)})
        else:
            if result.get("created"):
                queued.append(result)
            else:
                skipped.append({"id": draft_id, "detail": "Task already exists in planned queue"})

    return {
        "category": category,
        "queued": queued,
        "skipped": skipped,
        "errors": errors,
        "summary": {
            "queued": len(queued),
            "skipped": len(skipped),
            "errors": len(errors),
            "considered": len(drafts),
        },
        "executes": False,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/ecos/workflows/{workflow_name}/queue")
async def queue_ecos_workflow_verification(workflow_name: str, mode: str = Query("test")):
    """将 eCOS 工作流验证或 dry-run 结果承接为 OMO planned 任务。"""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", workflow_name):
        raise HTTPException(status_code=400, detail="Invalid workflow name")
    if mode not in {"test", "dry_run"}:
        raise HTTPException(status_code=400, detail="mode must be test or dry_run")

    task_id = f"cockpit-ecos-workflow-{workflow_name}-{mode}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Workflow verification task already exists in {existing_group}: {task_id}"
        )
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    task_data = {
        "id": task_id,
        "title": f"验收 eCOS 工作流：{workflow_name} ({mode})",
        "description": f"完成 eCOS 工作流 {workflow_name} 的 {mode} 验证，核对定义、约束、节点输出和运行证据。",
        "status": "pending",
        "task_type": "verification",
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
        "source_docs": [f"cockpit:ecos-workflow:{workflow_name}"],
        "entry_gate": ["确认工作流定义和验证模式"],
        "evidence_required": ["约束校验结果", "节点或 dry-run 输出", "工作流 closeout 记录"],
        "deliverables": [f"完成工作流 {workflow_name} 的 {mode} 验证并回写证据。"],
        "test_plan": ["执行对应验证模式，核对结果与历史运行日志，并记录异常节点。"],
        "priority": "medium",
        "tags": ["cockpit-ecos", "workflow-verification", workflow_name, mode],
        "metadata": {
            "created_via": "cockpit-ecos-workflow",
            "workflow_name": workflow_name,
            "mode": mode,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-ecos-workflow",
            source_ref=f"cockpit:ecos-workflow:{workflow_name}:{mode}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "executes": False,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/metaos/workflows/{workflow_id}/queue")
async def queue_metaos_workflow_followup(workflow_id: str, request: Request):
    """将 MetaOS 运行记录承接为可追踪的 OMO follow-up 任务。"""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", workflow_id):
        raise HTTPException(status_code=400, detail="Invalid workflow id")

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Workflow handoff request must be an object")
    workflow_status = str(body.get("status") or "unknown").strip()
    task_description = str(body.get("task") or workflow_id).strip()
    task_id = f"cockpit-metaos-workflow-{workflow_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Workflow follow-up already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    task_data = {
        "id": task_id,
        "title": f"跟进 MetaOS 工作流：{workflow_id}",
        "description": f"跟进 MetaOS 工作流 {workflow_id}（当前状态：{workflow_status}），核对节点输出、异常原因和最终 closeout。目标：{task_description}",
        "status": "pending",
        "task_type": "verification",
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
        "source_docs": [f"cockpit:metaos-workflow:{workflow_id}"],
        "entry_gate": ["确认工作流详情和当前节点状态"],
        "evidence_required": ["节点状态与输出", "异常或授权处理记录", "workflow closeout"],
        "deliverables": [f"完成 MetaOS 工作流 {workflow_id} 的跟进和证据收口。"],
        "test_plan": ["复核工作流详情、节点输出和授权状态，记录下一步及最终结论。"],
        "priority": "high" if workflow_status in {"failed", "awaiting_approval", "blocked"} else "medium",
        "tags": ["cockpit-metaos", "workflow-followup", workflow_id, workflow_status],
        "metadata": {
            "created_via": "cockpit-metaos-workflow",
            "workflow_id": workflow_id,
            "workflow_status": workflow_status,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-metaos-workflow",
            source_ref=f"cockpit:metaos-workflow:{workflow_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "executes": False,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/proposals/{proposal_id}/queue")
async def queue_hitl_proposal_task(proposal_id: str):
    """将 C2G HITL 提案承接为任务，供审批、执行和复盘共用同一条证据链。"""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", proposal_id):
        raise HTTPException(status_code=400, detail="Invalid proposal id")

    from cockpit.adapters.omo import list_hitl_proposals  # pyright: ignore[reportAttributeAccessIssue]

    proposal = next(
        (item for item in list_hitl_proposals(WORKSPACE_DIR / ".omo") if item.get("id") == proposal_id),
        None,
    )
    if not isinstance(proposal, dict):
        raise HTTPException(status_code=404, detail="Proposal not found")

    task_id = f"cockpit-proposal-{proposal_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Proposal task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    proposal_type = str(proposal.get("type") or "governance").strip()
    debt_id = str(proposal.get("debt_id") or "unknown").strip()
    task_data = {
        "id": task_id,
        "title": f"处理 C2G 提案：{proposal_type} · {debt_id}",
        "description": str(proposal.get("description") or f"围绕技术债务 {debt_id} 评估并处理提案 {proposal_type}。"),
        "status": "pending",
        "task_type": "governance",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": proposal_id,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L3",
        "allowed_operation_level": "L3",
        "human_approval_required": True,
        "source_docs": [f"cockpit:proposal:{proposal_id}"],
        "entry_gate": ["确认提案目标、作用域和影响债务", "确认审批人与执行边界"],
        "evidence_required": ["提案审批结果", "实际变更或拒绝原因", "验证结果", "proposal closeout"],
        "deliverables": [f"完成提案 {proposal_id} 的审批决策、执行/拒绝记录和证据收口。"],
        "test_plan": ["审批前复核影响面，审批后记录执行结果或拒绝原因，并回写 closeout。"],
        "priority": "high",
        "tags": ["cockpit-proposal", "hitl", proposal_type, debt_id],
        "metadata": {
            "created_via": "cockpit-c2g-proposal",
            "proposal_id": proposal_id,
            "proposal_type": proposal_type,
            "debt_id": debt_id,
            "target_model": proposal.get("target_model"),
            "scope": proposal.get("scope"),
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-c2g-proposal",
            source_ref=f"cockpit:proposal:{proposal_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "executes": False,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/alerts/{alert_id}/queue")
async def queue_alert_task(alert_id: str):
    """将告警承接为带来源和验收证据的 OMO planned 任务。"""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", alert_id):
        raise HTTPException(status_code=400, detail="Invalid alert id")

    from cockpit.web.api_alerts import generate_alerts_from_l4_data

    alert = next((item for item in generate_alerts_from_l4_data() if item.get("id") == alert_id), None)
    if not isinstance(alert, dict):
        raise HTTPException(status_code=404, detail="Alert not found")

    task_id = f"cockpit-alert-{alert_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Alert task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    level = str(alert.get("level") or "warning").lower()
    risk_level = "L2" if level in {"critical", "error"} else "L1"
    priority = "critical" if level == "critical" else "high" if level == "error" else "medium"
    message = str(alert.get("message") or alert_id)
    source = str(alert.get("source") or "unknown")
    description = str(alert.get("description") or "补齐告警原因和恢复证据。")
    task_data = {
        "id": task_id,
        "title": f"处理告警：{message}",
        "description": f"处理来自 {source} 的 {level} 告警“{message}”，确认根因、影响范围和恢复状态。{description}",
        "status": "pending",
        "task_type": "operations",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": risk_level,
        "allowed_operation_level": risk_level,
        "human_approval_required": risk_level in {"L2", "L3"},
        "source_docs": [f"cockpit:alert:{alert_id}"],
        "entry_gate": ["确认告警来源、级别和影响范围"],
        "evidence_required": ["日志或性能证据", "根因与处理结果", "告警恢复状态", "alert closeout"],
        "deliverables": [f"完成告警 {alert_id} 的处理、验证和 closeout。"],
        "test_plan": ["回看告警对应时间点的日志/性能数据，完成处理后确认告警状态恢复。"],
        "priority": priority,
        "tags": ["cockpit-alert", source, level, alert_id],
        "metadata": {
            "created_via": "cockpit-alert-center",
            "alert_id": alert_id,
            "alert_level": level,
            "alert_source": source,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-alert-center",
            source_ref=f"cockpit:alert:{alert_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "executes": False,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/research/{research_id}/queue")
async def queue_research_followup_task(research_id: int):
    """将研究对象的追问和下一步动作承接为 OMO planned 任务。"""
    if research_id < 1:
        raise HTTPException(status_code=400, detail="Invalid research id")

    from cockpit.storage import get_data_access

    access = get_data_access()
    research = access.get_research(research_id)
    if not isinstance(research, dict):
        raise HTTPException(status_code=404, detail="Research object not found")

    task_id = f"cockpit-research-{research_id}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Research task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    topic = str(research.get("topic") or f"研究对象 #{research_id}").strip()
    summary = str(research.get("summary") or "").strip()
    _fu = research.get("follow_ups")
    follow_ups = _fu if isinstance(_fu, list) else []
    questions = [str(item.get("question") or item) for item in follow_ups[:5] if isinstance(item, dict) or item]
    task_data = {
        "id": task_id,
        "title": f"落地研究后续：{topic}",
        "description": f"围绕研究对象“{topic}”推进下一步动作，复核研究结论、追问和证据，再形成可执行结论。{summary}",
        "status": "pending",
        "task_type": "research",
        "assigned_to": research.get("agent") or None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [f"research:{research_id}"],
        "handoff_refs": [],
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "source_docs": [f"cockpit:research:{research_id}"],
        "entry_gate": ["确认研究对象、结论范围和下一步问题"],
        "evidence_required": ["研究正文或摘要", "追问处理结果", "验证/发布证据", "research closeout"],
        "deliverables": [f"完成研究对象 {research_id} 的后续处理并回写结论和证据。"],
        "test_plan": ["逐项处理研究追问，核对来源和结论，必要时补充研究或发布结果。"],
        "priority": "high" if questions else "medium",
        "tags": ["cockpit-research", "follow-up", str(research_id)],
        "metadata": {
            "created_via": "cockpit-research-hub",
            "research_id": research_id,
            "topic": topic,
            "follow_up_questions": questions,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-research-hub",
            source_ref=f"cockpit:research:{research_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "executes": False,
        "title": created.get("title", task_data["title"]),
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/engine/queue")
async def queue_engine_execution(request: Request):
    """Register an engine or pipeline request as an OMO planned task."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Engine queue request must be an object")

    engine = str(body.get("engine") or "metaos").strip().lower()
    task = str(body.get("task") or body.get("goal") or "").strip()
    pipeline = str(body.get("pipeline") or "").strip()
    planning_result = body.get("plan")
    if engine not in {"metaos", "pipeline"}:
        raise HTTPException(status_code=400, detail="engine must be metaos or pipeline")
    if not task:
        raise HTTPException(status_code=422, detail="task is required")
    if engine == "pipeline" and not pipeline:
        raise HTTPException(status_code=422, detail="pipeline is required for pipeline execution")
    if planning_result is not None and not isinstance(planning_result, (dict, list, str)):
        raise HTTPException(status_code=422, detail="plan must be an object, list, or string")

    fingerprint = sha256(f"{engine}:{pipeline}:{task}".encode()).hexdigest()[:16]
    task_id = f"cockpit-engine-{fingerprint}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Engine task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {
            "id": task_id,
            "status": "pending",
            "created": False,
            "engine": engine,
            "pipeline": pipeline or None,
            "executes": False,
            "source": "omo_ingress",
        }

    title = f"引擎任务：{pipeline}" if engine == "pipeline" else "MetaOS 任务规划"
    description = f"{pipeline} · {task}" if pipeline else task
    task_data = {
        "id": task_id,
        "title": title,
        "description": description,
        "status": "pending",
        "task_type": "orchestration",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L2",
        "allowed_operation_level": "L2",
        "human_approval_required": True,
        "source_docs": ["cockpit:EnginesView"],
        "entry_gate": ["确认引擎、管线和目标"],
        "evidence_required": ["规划结果", "执行日志", "工作流 closeout"],
        "deliverables": [description],
        "test_plan": ["审批后由 OMO worker 派发，并回写节点状态和执行证据。"],
        "tags": ["cockpit-engine", engine, pipeline or "metaos"],
        "priority": "high",
        "metadata": {
            "engine": engine,
            "pipeline": pipeline or None,
            "task": task,
            "planning_result": planning_result,
            "cockpit_only": True,
            "controlled_execution": False,
        },
    }

    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-engine",
            source_ref=f"cockpit:engine:{engine}:{task_id}",
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
        "engine": engine,
        "pipeline": pipeline or None,
        "executes": False,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/governance/queue")
async def queue_governance_action(request: Request):
    """Register a high-risk governance mutation for human-approved execution."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Governance queue request must be an object")
    action = str(body.get("action") or "").strip().lower()
    if action != "fix-drift":
        raise HTTPException(status_code=400, detail="Unsupported governance action")

    task_id = "cockpit-governance-fix-drift"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Governance task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {
            "id": task_id,
            "status": "pending",
            "created": False,
            "action": action,
            "executes": False,
            "source": "omo_ingress",
        }

    task_data = {
        "id": task_id,
        "title": "治理修复：校正 SSOT 漂移",
        "description": "人工确认后运行 SSOT Guardian 自动修复，并审阅全部变更再固化。",
        "status": "pending",
        "task_type": "governance",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L3",
        "allowed_operation_level": "L3",
        "human_approval_required": True,
        "source_docs": ["bin/ssot/ssot-guardian.py", ".omo/standards/agent-mutation-protocol.md"],
        "entry_gate": ["确认漂移范围", "确认自动修复不会覆盖并发改动"],
        "evidence_required": ["修复前后 diff", "guardian 输出", "人工复核记录", "closeout"],
        "deliverables": ["SSOT 漂移修复结果和复核证据"],
        "test_plan": ["审批后执行 guardian，逐项审阅变更，再回写治理 closeout。"],
        "tags": ["cockpit-governance", "fix-drift", "high-risk"],
        "priority": "high",
        "metadata": {
            "governance_action": action,
            "command": "python3 bin/ssot/ssot-guardian.py --auto-fix",
            "cockpit_only": True,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-governance",
            source_ref=f"cockpit:governance:{action}:{task_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO task ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": task_id,
        "status": "pending",
        "created": True,
        "title": created.get("title", task_data["title"]),
        "action": action,
        "executes": False,
        "source": "omo_ingress",
    }
