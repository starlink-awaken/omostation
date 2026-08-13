#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .omo_ingress import archive_done_task, create_audit_report, yield_task_to_planned
from .omo_io import write_text_atomic
from .omo_redaction import redact_sensitive_text
from .omo_task_schema import validate_task_file
from .omo_worker_core import (
    _append_unique,
    _build_launch_argv,
    _find_task_file,
    _find_task_file_safe,
    _load_yaml,
    _omo_path,
    _require_admitted_worker,
    _require_worker_policy,
    _timestamp_slug,
    _utc_now,
    _write_yaml,
)


def _bridge_dispatch_to_mesh(
    root: Path,
    omo: Path,
    *,
    dispatch_id: str,
    task_id: str,
    worker_id: str,
    workflow_packet: dict[str, Any] | None,
    now: str,
) -> None:
    """Emit Workflow Mesh events for a worker dispatch.

    When a workflow_packet is provided (Mesh-aware path), emit StepDispatched
    using the packet's admission context. When no packet (legacy path), create
    a minimal admission grant and emit the full chain so the dispatch is
    visible in Mesh.
    """
    try:
        from .workflow_mesh import WorkflowMeshStore, new_workflow_event

        store = WorkflowMeshStore(omo)

        if workflow_packet:
            run_id = str(workflow_packet.get("workflow_run_id", dispatch_id))
            trace_id = str(workflow_packet.get("trace_id", run_id))
            grant = workflow_packet.get("admission", {})
            admission_id = str(grant.get("admission_id", ""))
            step_run_ids = grant.get("step_run_ids", [f"{run_id}:execute"])
            step_run_id = str(step_run_ids[0]) if step_run_ids else f"{run_id}:execute"

            store.append(
                new_workflow_event(
                    "StepDispatched",
                    run_id,
                    trace_id=trace_id,
                    producer="omo.omo_worker_dispatch",
                    idempotency_key=f"{run_id}:step-dispatched:{dispatch_id}",
                    payload={
                        "dispatch_id": dispatch_id,
                        "worker_id": worker_id,
                        "step_run_id": step_run_id,
                        "step_name": "execute",
                        "admission_id": admission_id,
                    },
                )
            )
        else:
            run_id = f"dispatch-{dispatch_id}"
            trace_id = run_id
            step_run_id = f"{run_id}:execute"
            admission_id = f"legacy-{uuid4().hex[:12]}"
            issued_at = now
            expires_at = (
                datetime.fromisoformat(now) + timedelta(seconds=1200)
            ).isoformat()

            grant = {
                "admission_id": admission_id,
                "status": "admitted",
                "workflow_run_id": run_id,
                "trace_id": trace_id,
                "backend": "legacy-dispatch",
                "step_run_ids": [step_run_id],
                "capabilities": [],
                "policy_digest": hashlib.sha256(
                    json.dumps(
                        {"task_id": task_id, "worker_id": worker_id},
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
                "issued_at": issued_at,
                "expires_at": expires_at,
            }
            grant["proof"] = hashlib.sha256(
                json.dumps(grant, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

            store.append(
                new_workflow_event(
                    "WorkflowRequested",
                    run_id,
                    trace_id=trace_id,
                    producer="omo.omo_worker_dispatch",
                    idempotency_key=f"{run_id}:requested",
                    payload={
                        "task_id": task_id,
                        "backend": "legacy-dispatch",
                        "required_capabilities": [],
                    },
                )
            )
            store.append(
                new_workflow_event(
                    "WorkflowAdmitted",
                    run_id,
                    trace_id=trace_id,
                    producer="omo.omo_worker_dispatch",
                    idempotency_key=f"{run_id}:admitted",
                    payload={"admission": grant, **grant, "task_id": task_id},
                )
            )
            store.append(
                new_workflow_event(
                    "StepDispatched",
                    run_id,
                    trace_id=trace_id,
                    producer="omo.omo_worker_dispatch",
                    idempotency_key=f"{run_id}:step-dispatched:{dispatch_id}",
                    payload={
                        "dispatch_id": dispatch_id,
                        "worker_id": worker_id,
                        "step_run_id": step_run_id,
                        "step_name": "execute",
                        "admission_id": admission_id,
                    },
                )
            )
    except Exception:
        pass


def dispatch_task(
    root: Path,
    task_id: str,
    worker_id: str,
    allowed_write_paths: list[str],
    launch: bool = False,
    transport: str = "cli_prompt",
    prior_evidence: list[str] | None = None,
    prompt_addendum: list[str] | None = None,
    workflow_packet: dict[str, Any] | None = None,
    now: str | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, str]:
    omo = _omo_path(root, omo_dir)
    omo_ref = Path(omo_dir)
    task_file = _find_task_file(omo / "tasks" / "active", task_id)
    validation_errors = validate_task_file(task_file)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))
    task = _load_yaml(task_file)
    registry = _load_yaml(omo / "_truth" / "registry" / "workers.yaml")
    # Admission is a hard precondition.  Validate before deriving a dispatch
    # id or creating any run/envelope/task/Mesh state so rejection is side-effect free.
    worker = _require_admitted_worker(registry, worker_id, transport)
    _require_worker_policy(
        registry,
        worker,
        task,
        allowed_write_paths=allowed_write_paths,
        workflow_packet=workflow_packet,
    )

    dispatch_now = now or _utc_now()
    dispatch_id = f"{task_id.lower()}-{worker_id}-{_timestamp_slug(dispatch_now)}"
    run_dir = omo / "workers" / "runs"

    # OMO v4.0 Task Gate: Anti-Entropy Mechanism
    debt_dispatch_file = omo / "debt" / "dispatch" / "current.yaml"
    if debt_dispatch_file.exists():
        debt_state = _load_yaml(debt_dispatch_file)
        if debt_state.get("priority") == "P0" and task.get("task_type") != "tech_debt":
            raise ValueError(
                "Task Gate Blocked: Technical debt is P0. You must dispatch a tech_debt task before any new feature tasks."
            )

    # OMO v4.0 Micro-DAG: Workflow Dependency Check
    depends_on = task.get("depends_on", [])
    if depends_on:
        for dep_id in depends_on:
            # Check if dependency is still planned or active
            if _find_task_file_safe(
                omo / "tasks" / "planned", dep_id
            ) or _find_task_file_safe(omo / "tasks" / "active", dep_id):
                raise ValueError(
                    f"Task Gate Blocked: Dependency '{dep_id}' is not yet completed."
                )

    dispatch_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-dispatch.yaml"
    envelope_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-envelope.yaml"
    prompt_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-prompt.md"
    checkpoint_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-checkpoint.md"
    reclaim_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-reclaim.md"
    review_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-review.md"
    stdout_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-stdout.log"
    persisted_launch_argv = _build_launch_argv(
        registry,
        worker_id,
        transport,
        f"<prompt:{prompt_path}>",
        workspace_root=root,
        redact_workspace_root=True,
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    source_docs = task.get("source_docs", [])
    deliverables = task.get("deliverables", [])
    allowed_paths = list(allowed_write_paths)
    write_scope = worker.get("write_scope")
    no_worker_writes = (
        isinstance(write_scope, dict) and write_scope.get("mode") == "none"
    )
    write_constraints = (
        [
            "- No repository writes are permitted.",
            "- Return the result on stdout or the governed evidence channel.",
        ]
        if no_worker_writes
        else [
            *(f"- You may write to `{path}`" for path in allowed_paths),
            f"- You may write to `{task_file.relative_to(root)}`",
            f"- You may write to `{review_path}`",
        ]
    )
    deliverable_constraints = (
        [
            *(f"- Expected result reference: `{path}`" for path in deliverables),
            "- The coordinator owns materialization of result references.",
        ]
        if no_worker_writes
        else [
            *(f"- Required deliverable: `{path}`" for path in deliverables),
            "- Updating only the review note is not sufficient when required deliverables are listed.",
        ]
    )
    deliverables_heading = (
        "## Expected output references"
        if no_worker_writes
        else "## Required deliverables"
    )
    recovery_lines = list(prompt_addendum or [])
    prompt = "\n".join(
        [
            "# Worker Prompt Contract",
            "",
            f"WORKER_ID: `{worker_id}`",
            f"TASK_ID: `{task_id}`",
            f"TRANSPORT: `{transport}`",
            "READ_BUDGET: `5`",
            "",
            "## Mission",
            "",
            task.get("title", task_id),
            "",
            "## Task SSOT",
            "",
            f"- Task YAML: `{task_file.relative_to(root)}`",
            *(f"- Source doc: `{doc}`" for doc in source_docs),
            "",
            "## Constraints",
            "",
            *write_constraints,
            "- Do not modify global state files.",
            "- Do not mark the task `done`.",
            *(
                "- Workflow Mesh admission: `"
                + str(workflow_packet.get("admission", {}).get("admission_id"))
                + "`"
                for _ in [0]
                if workflow_packet
            ),
            "",
            deliverables_heading,
            "",
            *deliverable_constraints,
            *recovery_lines,
        ]
    )
    write_text_atomic(root / prompt_path, prompt + "\n")
    write_text_atomic(
        root / checkpoint_path,
        "# Checkpoint Note\n\n## Last completed step\n\nTBD\n\n## Changed files\n\n- None yet\n",
    )
    write_text_atomic(
        root / reclaim_path,
        "# Reclaim Note\n\n## Reclaim reason\n\nTBD\n\n## Required successor context\n\n- Review the checkpoint note first.\n",
    )
    write_text_atomic(
        root / review_path,
        "# Review Note\n\n## Summary of work done\n\nTBD\n",
    )

    envelope = {
        "version": 1,
        "task_id": task_id,
        "worker_id": worker_id,
        "transport_mode": transport,
        "run_ref": str(dispatch_path),
        "knowledge_refs": source_docs,
        "handoff_refs": [
            str(prompt_path),
            str(checkpoint_path),
            str(review_path),
            str(reclaim_path),
        ],
        "objective": task.get("title", task_id),
        "task_yaml": str(task_file.relative_to(root)),
        "inputs": {
            "source_docs": source_docs,
            "required_context": [str(task_file.relative_to(root))],
            "prior_evidence": list(prior_evidence or []),
            "workflow_mesh": workflow_packet or {},
        },
        "outputs": {
            "required_deliverables": deliverables,
        },
        "scope": {
            "allowed_write_paths": allowed_paths,
            "forbidden_write_paths": [
                ".omo/state/system.yaml",
                ".omo/goals/current.yaml",
                "convergence.yaml",
            ],
            "non_goals": ["Do not modify global state files"],
        },
        "execution_policy": {
            "read_budget": 5,
            "heartbeat_interval_seconds": 300,
            "warning_after_seconds": 900,
            "lease_expired_after_seconds": 1200,
            "reclaim_after_seconds": 1800,
            "checkpoint_required": True,
            "require_partial_output_when_stuck": True,
        },
        "gates": {
            "allowed_operation_level": task.get("allowed_operation_level", "L0"),
            "may_prepare_levels": [],
            "human_approval_required_for": [],
            "approval_ref": task.get("approval_ref"),
            "sensitive_capabilities_blocked": True,
            "workflow_mesh_admission_required": bool(workflow_packet),
        },
        "knowledge_contract": {
            "output_summary_required": True,
            "changed_files_required": True,
            "evidence_required": True,
            "unresolved_risks_required": True,
            "next_handoff_required": True,
        },
        "review": {
            "closeout_owner": "coordinator",
            "worker_may_set_review": True,
            "worker_may_set_done": False,
            "worker_may_set_blocked": False,
        },
    }
    _write_yaml(root / envelope_path, envelope)

    launch_command = " ".join(
        shlex.quote(argument) for argument in persisted_launch_argv
    )
    dispatch = {
        "version": 1,
        "dispatch_id": dispatch_id,
        "task_id": task_id,
        "worker_id": worker_id,
        "transport_mode": transport,
        "run_ref": str(dispatch_path),
        "dispatch_state": "dispatched",
        "coordinator": "copilot-cli",
        "launched_at": dispatch_now,
        "lease": {
            "heartbeat_interval_seconds": 300,
            "warning_after_seconds": 900,
            "lease_expired_after_seconds": 1200,
            "reclaim_after_seconds": 1800,
            "last_checkpoint_at": None,
            "last_material_write_at": None,
        },
        "inputs": {
            "task_yaml": str(task_file.relative_to(root)),
            "envelope_file": str(envelope_path),
            "prompt_file": str(prompt_path),
            "source_docs": source_docs,
        },
        "execution": {
            "launch_command": launch_command,
            "approval_ref": task.get("approval_ref"),
            "session_ref": None,
            "log_ref": str(stdout_path),
            "checkpoint_refs": [str(checkpoint_path)],
            "workflow_mesh": workflow_packet or {},
        },
        "handoff": {
            "output_summary_ref": str(review_path),
            "evidence_paths": [],
            "unresolved_risks": [],
            "next_handoff": None,
        },
        "reclaim": {
            "required": False,
            "reason": None,
            "reclaimed_at": None,
            "successor_worker_id": None,
            "successor_dispatch_id": None,
            "note_ref": str(reclaim_path),
        },
    }
    _write_yaml(root / dispatch_path, dispatch)

    task["status"] = "in_progress"
    task["assigned_to"] = worker_id
    task["dispatch_id"] = dispatch_id
    task["run_ref"] = str(dispatch_path)
    task["review_ref"] = str(review_path)
    task["started_at"] = task.get("started_at") or dispatch_now
    task["knowledge_refs"] = _append_unique(task.get("knowledge_refs", []), source_docs)
    task["handoff_refs"] = _append_unique(
        task.get("handoff_refs", []),
        [str(envelope_path), str(prompt_path), str(checkpoint_path)],
    )
    _write_yaml(task_file, task)

    _bridge_dispatch_to_mesh(
        root,
        omo,
        dispatch_id=dispatch_id,
        task_id=task_id,
        worker_id=worker_id,
        workflow_packet=workflow_packet,
        now=dispatch_now,
    )

    if launch:
        prompt_text = (root / prompt_path).read_text(encoding="utf-8")
        argv = _build_launch_argv(
            registry,
            worker_id,
            transport,
            prompt_text,
            workspace_root=root,
        )
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        log_content = redact_sensitive_text(
            (result.stdout or "") + (result.stderr or "")
        )
        write_text_atomic(root / stdout_path, log_content)
        if result.returncode != 0:
            raise RuntimeError(
                "worker launch failed: "
                f"worker_id={worker_id} returncode={result.returncode} log={stdout_path}"
            )

        # Phase 28 Step 3: Tri-Plane Bus - Broadcast event to Agora EventBus
        def push_log_to_agora(dispatch_id: str, content: str):
            """Push log synchronization event to Agora via internal Event Bus."""
            try:
                import json
                import os
                import urllib.request

                req = urllib.request.Request(
                    "http://127.0.0.1:7430/api/events",
                    data=json.dumps(
                        {
                            "type": "omo:log_sync",
                            "source": "omo_worker",
                            "payload": {"dispatch_id": dispatch_id, "content": content},
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                req.add_header("Content-Type", "application/json")

                jwt_secret = os.environ.get("AGORA_JWT_SECRET")
                api_key = os.environ.get("AGORA_API_KEY")
                if jwt_secret:
                    import time

                    import jwt

                    token = jwt.encode(
                        {"role": "system_daemon", "exp": time.time() + 3600},
                        jwt_secret,
                        algorithm="HS256",
                    )
                    req.add_header("Authorization", f"Bearer {token}")
                elif api_key:
                    req.add_header("X-API-Key", api_key)

                # Bypass proxy for 127.0.0.1
                proxy_handler = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy_handler)
                opener.open(req, timeout=3.0)
            except Exception as e:  # defensive fallback
                print(f"⚠️ Failed to broadcast log via Tri-Plane Bus: {e}")

        push_log_to_agora(dispatch_id, log_content)
        print(f"✅ Sync'ed {dispatch_id} log via Tri-Plane Bus")

        dispatch["dispatch_state"] = "active"
        dispatch["lease"]["last_material_write_at"] = _utc_now()
        _write_yaml(root / dispatch_path, dispatch)

    return {
        "dispatch_id": dispatch_id,
        "dispatch_path": str(dispatch_path),
        "envelope_path": str(envelope_path),
        "prompt_path": str(prompt_path),
        "checkpoint_path": str(checkpoint_path),
        "reclaim_path": str(reclaim_path),
        "review_path": str(review_path),
    }


def reclaim_task(
    root: Path,
    task_id: str,
    successor_worker_id: str,
    allowed_write_paths: list[str],
    reason: str,
    launch: bool = False,
    transport: str = "cli_prompt",
    omo_dir: str | Path = ".omo",
) -> dict[str, str]:
    active_dir = _omo_path(root, omo_dir) / "tasks" / "active"
    task_file = _find_task_file(active_dir, task_id)
    task = _load_yaml(task_file)
    run_ref = task.get("run_ref")
    if not run_ref:
        raise ValueError(f"Task has no active run to reclaim: {task_id}")

    prior_dispatch_path = root / run_ref
    prior_dispatch = _load_yaml(prior_dispatch_path)
    checkpoint_refs = list(
        prior_dispatch.get("execution", {}).get("checkpoint_refs", [])
    )
    reclaim_ref = prior_dispatch.get("reclaim", {}).get("note_ref")
    reclaim_note_path = root / reclaim_ref if reclaim_ref else None

    if reclaim_note_path is not None:
        write_text_atomic(
            reclaim_note_path,
            "\n".join(
                [
                    "# Reclaim Note",
                    "",
                    "## Reclaim reason",
                    "",
                    reason,
                    "",
                    "## Required successor context",
                    "",
                    *(f"- Review checkpoint: `{ref}`" for ref in checkpoint_refs),
                    *(
                        f"- Review reclaim note: `{reclaim_ref}`"
                        for _ in [0]
                        if reclaim_ref
                    ),
                    "",
                    "## Successor worker",
                    "",
                    successor_worker_id,
                    "",
                ]
            )
            + "\n",
        )

    prior_dispatch["dispatch_state"] = "reclaimed"
    prior_dispatch["reclaim"]["required"] = True
    prior_dispatch["reclaim"]["reason"] = reason
    prior_dispatch["reclaim"]["reclaimed_at"] = _utc_now()
    prior_dispatch["reclaim"]["successor_worker_id"] = successor_worker_id
    _write_yaml(prior_dispatch_path, prior_dispatch)

    prior_evidence = checkpoint_refs + ([reclaim_ref] if reclaim_ref else [])
    prompt_addendum = [
        "",
        "## Recovery context",
        "",
        f"- Reclaim reason: {reason}",
        *(f"- Resume from checkpoint: `{ref}`" for ref in checkpoint_refs),
        *(f"- Review reclaim handoff: `{reclaim_ref}`" for _ in [0] if reclaim_ref),
        "- Continue from the recorded checkpoint instead of restarting the task.",
    ]
    successor = dispatch_task(
        root,
        task_id=task_id,
        worker_id=successor_worker_id,
        allowed_write_paths=allowed_write_paths,
        launch=launch,
        transport=transport,
        prior_evidence=prior_evidence,
        prompt_addendum=prompt_addendum,
        omo_dir=omo_dir,
    )

    prior_dispatch = _load_yaml(prior_dispatch_path)
    prior_dispatch["reclaim"]["successor_dispatch_id"] = successor["dispatch_id"]
    _write_yaml(prior_dispatch_path, prior_dispatch)
    return successor


def yield_task(
    root: Path, task_id: str, reason: str, omo_dir: str | Path = ".omo"
) -> int:
    """[C2G v2] Agent Autonomous Yielding Mechanism"""
    omo_path = _omo_path(root, omo_dir)
    active_dir = omo_path / "tasks" / "active"
    task_file = _find_task_file(active_dir, task_id)
    if not task_file:
        raise ValueError(f"Task {task_id} not found in active tasks.")

    task = _load_yaml(task_file)
    run_ref = task.get("run_ref")
    if run_ref:
        dispatch_path = root / run_ref
        if dispatch_path.exists():
            dispatch = _load_yaml(dispatch_path)
            dispatch["dispatch_state"] = "yielded"
            dispatch["reclaim"] = dispatch.get("reclaim", {})
            dispatch["reclaim"]["required"] = True
            dispatch["reclaim"]["reason"] = f"Yielded to ideation: {reason}"
            _write_yaml(dispatch_path, dispatch)

    yield_task_to_planned(
        omo_path,
        task_id=task_id,
        actor="projects/omo/src/omo/omo_worker_dispatch.py:yield_task",
        reason=reason,
        source_ref=f"omo:worker-dispatch:yield:{task_id}",
    )
    print(f"✅ 战术撤退成功: 任务 {task_id} 已退回沙箱 (candidate)。原因: {reason}")
    return 0


def _worker_gc(
    root: Path, dry_run: bool = False, retain: int = 50, omo_dir: str | Path = ".omo"
) -> int:
    """清理旧的 worker dispatch 运行文件。

    Args:
        root: Workspace 根目录
        dry_run: 仅列出拟删除文件，不实际删除
        retain: 保留的最新 dispatch 数目

    Returns:
        0 表示成功，1 表示有错误
    """
    runs_dir = _omo_path(root, omo_dir) / "workers" / "runs"
    if not runs_dir.exists():
        print("No runs directory found at", runs_dir)
        return 0

    # 收集所有 dispatch 文件，按 dispatch_id 中的 timestamp 分组
    dispatch_files: dict[str, list[Path]] = {}
    for f in runs_dir.iterdir():
        if f.is_file():
            # dispatch_id 通常为 dispatch-{task_id}-{timestamp} 格式
            name = f.stem
            # 去掉可能的后缀变体（如 -prompt, -envelope, -review 等后缀）
            name.split(".")[0]
            # 尝试提取 dispatch_id（第一个词和最后一个时间戳之间）
            # 格式举例: dispatch-TASK-1-20260530T161437 → 提取 dispatch-TASK-1-20260530T161437
            # 或者带后缀: dispatch-TASK-1-20260530T161437-prompt → 也属于同一组
            # 简单做法：按文件名前缀（去掉最后一个 - 后缀）分组
            parts = name.rsplit("-", 1)
            if len(parts) > 1 and parts[1] in (
                "prompt",
                "envelope",
                "review",
                "dispatch",
            ):
                group_key = parts[0]
            else:
                group_key = name
            dispatch_files.setdefault(group_key, []).append(f)

    # 按组键名排序（时间戳在键名末尾，排序即按时间）
    sorted_groups = sorted(dispatch_files.keys())

    if len(sorted_groups) <= retain:
        print(
            f"Total dispatch runs: {len(sorted_groups)} (≤ retain={retain}, nothing to clean)"
        )
        return 0

    to_delete = sorted_groups[:-retain]
    total_files = 0
    for group_key in to_delete:
        files = dispatch_files[group_key]
        total_files += len(files)
        if dry_run:
            print(
                f"[DRY-RUN] Would delete {len(files)} file(s) for dispatch {group_key}:"
            )
            for f in files:
                print(f"  {f}")
        else:
            for f in files:
                f.unlink()
            print(f"Deleted {len(files)} file(s) for dispatch {group_key}")

    print(
        f"GC complete: retained {retain} dispatch runs, "
        f"cleaned {len(to_delete)} old runs ({total_files} files)"
    )

    if not dry_run:
        _fast_track_compaction(root, omo_dir=omo_dir)

    return 0


def _fast_track_compaction(root: Path, omo_dir: str | Path = ".omo"):
    """[C2G v2] Fast-Track 碎片聚变机制
    收集 done 目录下的 FAST-* 任务，聚变成 Markdown 报告，并将原始 yaml 归档。
    """
    omo_path = _omo_path(root, omo_dir)
    done_dir = omo_path / "tasks" / "done"
    audit_dir = omo_path / "_knowledge" / "audits"

    if not done_dir.exists():
        return

    fast_tasks = list(done_dir.glob("FAST-*.yaml"))
    if len(fast_tasks) < 5:
        # 数量不够，暂不聚变
        return

    audit_dir.mkdir(parents=True, exist_ok=True)

    compaction_time = _timestamp_slug(_utc_now())
    report_name = f"Fast-Track-Compaction-{compaction_time}"

    report_lines = [
        f"# 微小价值交付聚变报告 ({compaction_time})",
        "",
        "| Task ID | 标题 | 锚点 | 归档时间 |",
        "|---|---|---|---|",
    ]

    for task_file in fast_tasks:
        try:
            task = _load_yaml(task_file)
            title = task.get("title", "Unknown")
            context_uri = task.get("context_uri", "N/A")
            report_lines.append(
                f"| {task_file.stem} | {title} | `{context_uri}` | {_utc_now()} |"
            )

            archive_done_task(
                omo_path,
                task_id=task_file.stem,
                actor="projects/omo/src/omo/omo_worker_dispatch.py:_fast_track_compaction",
                source_ref=f"omo:worker-dispatch:fast-track-compaction:{task_file.stem}",
            )
        except Exception as e:  # defensive fallback
            print(f"Failed to compact {task_file}: {e}")

    if len(report_lines) > 4:
        create_audit_report(
            omo_path,
            filename=report_name,
            title=f"微小价值交付聚变报告 ({compaction_time})",
            content="\n".join(report_lines[2:]),
            actor="projects/omo/src/omo/omo_worker_dispatch.py:_fast_track_compaction",
            source_ref="omo:worker-dispatch:fast-track-compaction",
        )
        print(
            f"✅ Fast-Track 微观碎片已聚变: 归档了 {len(fast_tasks)} 个任务，生成报告 {report_name}.md"
        )
