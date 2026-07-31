"""Cockpit tasks API — compute/sandbox queue endpoints (compute, compute-control, sandbox, generation). Split from api_tasks.py."""

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


@router.post("/api/cockpit/compute/queue")
async def queue_compute_action(request: Request):
    """Register a physical compute-node action for human-approved execution."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Compute queue request must be an object")
    operation = str(body.get("operation") or "").strip().lower()
    node_id = str(body.get("node_id") or "").strip()
    if operation != "wakeup":
        raise HTTPException(status_code=400, detail="Unsupported compute operation")
    if not node_id or not re.fullmatch(r"[A-Za-z0-9_.:-]+", node_id):
        raise HTTPException(status_code=422, detail="node_id is required and must be safe")

    task_id = f"cockpit-compute-wakeup-{sha256(node_id.encode()).hexdigest()[:16]}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(status_code=409, detail=f"Compute task already exists in {existing_group}: {task_id}")
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    task_data = {
        "id": task_id,
        "title": f"算力节点唤醒：{node_id}",
        "description": f"人工确认后向算力节点 {node_id} 发送 Wake-on-LAN Magic Packet。",
        "status": "pending",
        "task_type": "operations",
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
        "source_docs": ["projects/aetherforge", "projects/cockpit/src/cockpit/web/api_compute.py"],
        "entry_gate": ["确认节点身份和离线状态", "确认网络唤醒风险"],
        "evidence_required": ["节点状态快照", "唤醒命令输出", "唤醒后端口/健康检查", "closeout"],
        "deliverables": [f"节点 {node_id} 恢复可观测状态"],
        "test_plan": ["审批后发送唤醒包，并回写节点运行和健康探针结果。"],
        "tags": ["cockpit-compute", "wakeup", "high-risk", node_id],
        "priority": "high",
        "metadata": {
            "compute_operation": operation,
            "node_id": node_id,
            "command": f"python3 -m aetherforge.cli mesh wakeup {node_id}",
            "cockpit_only": True,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-compute",
            source_ref=f"cockpit:compute:{operation}:{task_id}",
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
        "node_id": node_id,
        "executes": False,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/compute/control/queue")
async def queue_compute_control(request: Request):
    """Register budget or circuit-breaker changes for human-approved execution."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Compute control request must be an object")
    operation = str(body.get("operation") or "").strip().lower()
    if operation not in {"circuit_break", "budget"}:
        raise HTTPException(status_code=400, detail="Unsupported compute control operation")

    if operation == "circuit_break":
        broken = body.get("broken")
        if not isinstance(broken, bool):
            raise HTTPException(status_code=422, detail="broken must be a boolean")
        target = "enabled" if broken else "disabled"
        title = f"算力熔断：{target}"
        description = f"人工确认后将混合云算力熔断器切换为 {target}。"
        command = f"POST /api/omos/circuit-break broken={str(broken).lower()}"
        tags = ["cockpit-compute", "circuit-break", target]
        metadata = {"broken": broken}
    else:
        budget = body.get("budget")
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 50 <= budget <= 1000:
            raise HTTPException(status_code=422, detail="budget must be a number between 50 and 1000")
        target = f"${budget:g}"
        title = f"算力日预算：{target}"
        description = f"人工确认后将混合云算力单日预算安全线更新为 {target}。"
        command = f"POST /api/omos/budget budget={budget:g}"
        tags = ["cockpit-compute", "budget"]
        metadata = {"budget": budget}

    task_id = f"cockpit-compute-control-{operation}-{sha256(str(metadata).encode()).hexdigest()[:16]}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Compute control task already exists in {existing_group}: {task_id}"
        )
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

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
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L3",
        "allowed_operation_level": "L3",
        "human_approval_required": True,
        "source_docs": ["projects/cockpit/src/cockpit/web/api_omos.py"],
        "entry_gate": ["确认当前算力状态和变更目标", "确认对业务路由或成本的影响"],
        "evidence_required": ["变更前状态快照", "配置写入结果", "变更后状态探针", "closeout"],
        "deliverables": [description],
        "test_plan": ["审批后执行控制变更，并回读算力状态确认结果。"],
        "tags": tags,
        "priority": "high",
        "metadata": {
            "compute_operation": operation,
            **metadata,
            "command": command,
            "cockpit_only": True,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-compute",
            source_ref=f"cockpit:compute-control:{operation}:{task_id}",
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
        "operation": operation,
        "executes": False,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/sandbox/queue")
async def queue_sandbox_result(request: Request):
    """Persist a sandbox result as a planned follow-up task without executing it."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Sandbox queue request must be an object")
    code = str(body.get("code") or "").strip()
    output = str(body.get("output") or "").strip()
    if not code:
        raise HTTPException(status_code=422, detail="code is required")
    if not output:
        raise HTTPException(status_code=422, detail="output is required")
    if len(code) > 20000 or len(output) > 20000:
        raise HTTPException(status_code=413, detail="Sandbox code and output must be no longer than 20000 characters")

    result_digest = sha256(f"{code}\n---\n{output}".encode()).hexdigest()[:16]
    task_id = f"cockpit-sandbox-result-{result_digest}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Sandbox result task already exists in {existing_group}: {task_id}"
        )
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    title = str(body.get("title") or "沙箱实验结果收口").strip()[:160]
    task_data = {
        "id": task_id,
        "title": title,
        "description": "将隔离沙箱实验结果带回日志、引擎或正式任务，并补齐可复现和 closeout 证据。",
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
        "source_docs": ["projects/cockpit/src/cockpit/web/api_sandbox.py"],
        "entry_gate": ["确认沙箱输出不包含敏感信息", "确认后续去向是日志、引擎或正式任务之一"],
        "evidence_required": ["沙箱代码或可复现片段", "沙箱输出摘要", "后续承接记录", "closeout"],
        "deliverables": ["完成沙箱实验结果的正式承接"],
        "test_plan": ["复核结果摘要，补充后续页面或执行链路的验证证据。"],
        "tags": ["cockpit-sandbox", "verification", result_digest],
        "priority": "medium",
        "metadata": {
            "sandbox_result_digest": result_digest,
            "code_excerpt": code[:2000],
            "output_excerpt": output[:4000],
            "cockpit_only": True,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-sandbox",
            source_ref=f"cockpit:sandbox:result:{task_id}",
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
        "result_digest": result_digest,
        "executes": False,
        "source": "omo_ingress",
    }


@router.post("/api/cockpit/compute/generation/queue")
async def queue_compute_generation_result(request: Request):
    """Persist local generation output as a verifiable follow-up task."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Generation queue request must be an object")
    prompt = str(body.get("prompt") or "").strip()
    model = str(body.get("model") or "coder").strip()
    content = str(body.get("content") or "").strip()
    if not prompt or not content:
        raise HTTPException(status_code=422, detail="prompt and content are required")
    if len(prompt) > 20000 or len(content) > 20000:
        raise HTTPException(status_code=413, detail="prompt and content must be no longer than 20000 characters")

    result_digest = sha256(f"{model}\n{prompt}\n---\n{content}".encode()).hexdigest()[:16]
    task_id = f"cockpit-compute-generation-{result_digest}"
    existing_group = _task_group(task_id)
    if existing_group in {"active", "done"}:
        raise HTTPException(
            status_code=409, detail=f"Generation result task already exists in {existing_group}: {task_id}"
        )
    if existing_group == "planned":
        return {"id": task_id, "status": "pending", "created": False, "executes": False, "source": "omo_ingress"}

    task_data = {
        "id": task_id,
        "title": f"本地生成结果验收：{model}",
        "description": "复核本地算力生成结果，将内容带回沙箱、研究或正式执行链，并补齐 closeout 证据。",
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
        "source_docs": ["projects/cockpit/src/cockpit/web/api_compute.py"],
        "entry_gate": ["确认模型和提示词上下文", "确认生成内容不含敏感信息"],
        "evidence_required": ["提示词和模型", "生成结果摘要", "沙箱或研究验收记录", "closeout"],
        "deliverables": ["完成本地生成内容的复核与后续承接"],
        "test_plan": ["在沙箱或研究面复核生成内容，并记录验收结论。"],
        "tags": ["cockpit-compute", "generation", "verification", result_digest],
        "priority": "medium",
        "metadata": {
            "compute_operation": "generation_result",
            "model": model,
            "prompt_excerpt": prompt[:4000],
            "content_excerpt": content[:6000],
            "result_digest": result_digest,
            "cockpit_only": True,
            "controlled_execution": False,
        },
    }
    try:
        from omo.omo_ingress_task_lifecycle import create_planned_task

        created = create_planned_task(
            WORKSPACE_DIR / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-compute",
            source_ref=f"cockpit:compute:generation-result:{task_id}",
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
        "result_digest": result_digest,
        "executes": False,
        "source": "omo_ingress",
    }
