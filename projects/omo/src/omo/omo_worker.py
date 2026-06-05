#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .omo_admission import evaluate_worker_envelope, request_conditional_approval
from .omo_governance import propose_truth_mutation
from .omo_contract_request import (
    build_contract_proposal,
    build_contract_request,
    contract_request_ref,
)
from .omo_io import write_text_atomic, write_yaml_atomic
from .omo_handoff_index import write_handoff_index
from .omo_metrics import write_worker_utilization_summary
from .omo_promotion_approval import evaluate_promotion_approval
from .omo_promotion_history import build_promotion_history
from .omo_promotion_request import (
    build_promotion_approval_proposal,
    build_promotion_approval_request,
    promotion_approval_ref,
)
from .omo_promotion_approval_status import (
    build_promotion_approval_status_packet,
    render_promotion_approval_status_markdown,
)
from .omo_promotion_approval_history import build_promotion_approval_history
from .omo_promotion_approval_analytics import build_promotion_approval_analytics_packet
from .omo_governance_overlay import build_governance_overlay_status
from .omo_governance_overlay_approval_prep import (
    build_governance_overlay_approval_prep_history,
    build_governance_overlay_approval_prep_status,
)
from .omo_governance_overlay_approval_prep_aging import (
    build_governance_overlay_approval_prep_aging,
)
from .omo_governance_overlay_approval_prep_analytics import (
    build_governance_overlay_approval_prep_analytics,
)
from .omo_governance_overlay_approval_prep_diff import (
    build_governance_overlay_approval_prep_diff,
)
from .omo_governance_overlay_approval_prep_trend import (
    build_governance_overlay_approval_prep_trend,
)
from .omo_governance_overlay_loop import plan_governance_overlay_cycle
from .omo_governance_overlay_targets import evaluate_governance_overlay_planned_target
from .omo_promotion_readiness import (
    build_promotion_readiness_packet,
    render_promotion_readiness_markdown,
)
from .omo_rules import evaluate_rule_bundle
from .omo_rollout import accept_rollout_envelope, evaluate_rollout_envelope
from .omo_redaction import redact_sensitive_text
from .omo_task_schema import (
    validate_active_tasks,
    validate_planned_tasks,
    validate_task_file,
)


def _timestamp_slug(now: str | None = None) -> str:
    if now:
        return now.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: dict) -> None:
    write_yaml_atomic(path, data)


def _find_task_file(active_dir: Path, task_id: str) -> Path:
    for task_file in active_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in active/: {task_id}")


def _find_planned_task_file(planned_dir: Path, task_id: str) -> Path:
    for task_file in planned_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in planned/: {task_id}")


def _find_task_file_safe(search_dir: Path, task_id: str) -> Path | None:
    if not search_dir.exists():
        return None
    for task_file in search_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    return None


def _find_dispatch_file(runs_dir: Path, dispatch_id: str) -> Path:
    path = runs_dir / f"{dispatch_id}-dispatch.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Dispatch not found: {dispatch_id}")
    return path


def _worker_command(registry: dict, worker_id: str, transport: str) -> str:
    for worker in registry.get("workers", []):
        if worker.get("id") == worker_id:
            return worker["transports"][transport]["command"]
    raise KeyError(f"Worker not registered: {worker_id}")


def _default_enabled_worker_id(registry: dict) -> str:
    default_role = registry.get("default_worker_role")
    for worker in registry.get("workers", []):
        if worker.get("enabled", True) and (
            default_role is None or worker.get("role") == default_role
        ):
            return str(worker["id"])
    for worker in registry.get("workers", []):
        if worker.get("enabled", True):
            return str(worker["id"])
    raise ValueError("no enabled worker is registered")


def _dispatch_allowed_write_paths(task: dict) -> list[str]:
    paths: list[str] = []
    for deliverable in task.get("deliverables", []):
        path = str(deliverable)
        if path.endswith("/"):
            candidate = path
        else:
            candidate = str(Path(path).parent)
            if candidate == ".":
                candidate = path
            elif not candidate.endswith("/"):
                candidate = f"{candidate}/"
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _launch_worker_from_prompt(
    root: Path,
    registry: dict,
    worker_id: str,
    transport: str,
    prompt_path: Path,
    stdout_path: Path,
) -> str:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    argv = _build_launch_argv(registry, worker_id, transport, prompt_text)
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    output = redact_sensitive_text((result.stdout or "") + (result.stderr or ""))
    write_text_atomic(stdout_path, output)
    return output


def _launch_existing_dispatch(
    root: Path, dispatch_path: Path, *, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    dispatch = _load_yaml(dispatch_path)
    registry = _load_yaml(
        _omo_path(root, omo_dir) / "_truth" / "registry" / "workers.yaml"
    )
    prompt_ref = (
        dispatch.get("inputs", {}).get("prompt_file")
        or dispatch["execution"]["prompt_file"]
    )
    prompt_path = root / str(prompt_ref)
    stdout_path = root / dispatch["execution"]["log_ref"]
    _launch_worker_from_prompt(
        root,
        registry,
        str(dispatch["worker_id"]),
        str(dispatch["transport_mode"]),
        prompt_path,
        stdout_path,
    )
    dispatch["dispatch_state"] = "active"
    dispatch.setdefault("lease", {})
    dispatch["lease"]["last_material_write_at"] = _utc_now()
    _write_yaml(dispatch_path, dispatch)
    return dispatch


def _append_unique(items: list[str], values: list[str]) -> list[str]:
    result = list(items)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _omo_path(root: Path, omo_dir: str | Path = ".omo") -> Path:
    return root / Path(omo_dir)


def collect_worker_status(
    root: Path, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    active_dir = _omo_path(root, omo_dir) / "tasks" / "active"
    runs: list[dict[str, object]] = []

    for task_file in sorted(active_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        run_ref = task.get("run_ref")
        if not run_ref:
            continue

        dispatch_path = root / run_ref
        if not dispatch_path.exists():
            continue

        dispatch = _load_yaml(dispatch_path)
        runs.append(
            {
                "task_id": dispatch.get("task_id", task.get("id")),
                "worker_id": dispatch.get("worker_id"),
                "dispatch_state": dispatch.get("dispatch_state"),
                "checkpoint_refs": dispatch.get("execution", {}).get(
                    "checkpoint_refs", []
                ),
                "reclaim_ref": dispatch.get("reclaim", {}).get("note_ref"),
                "review_ref": dispatch.get("handoff", {}).get("output_summary_ref"),
                "lease": dispatch.get("lease", {}),
            }
        )

    return {
        "active_dispatches": len(runs),
        "runs": runs,
    }


def update_dispatch_checkpoint(
    root: Path,
    dispatch_id: str,
    completed_step: str,
    changed_files: list[str],
    note: str,
    now: str | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, object]:
    dispatch_path = _find_dispatch_file(
        _omo_path(root, omo_dir) / "workers" / "runs", dispatch_id
    )
    dispatch = _load_yaml(dispatch_path)
    checkpoint_ref = dispatch.get("execution", {}).get("checkpoint_refs", [None])[-1]
    if not checkpoint_ref:
        raise ValueError(f"dispatch {dispatch_id} has no checkpoint ref")

    timestamp = now or _utc_now()
    changed_file_lines = [f"- `{path}`" for path in changed_files] or ["- None"]
    checkpoint_lines = [
        "# Checkpoint Note",
        "",
        "## Last completed step",
        "",
        completed_step,
        "",
        "## Changed files",
        "",
        *changed_file_lines,
        "",
        "## Operator note",
        "",
        note,
        "",
    ]
    write_text_atomic(root / checkpoint_ref, "\n".join(checkpoint_lines))

    dispatch["dispatch_state"] = "checkpointed"
    dispatch["lease"]["last_checkpoint_at"] = timestamp
    dispatch["lease"]["last_material_write_at"] = timestamp
    _write_yaml(dispatch_path, dispatch)
    return dispatch


def scan_runtime_watchdog(
    root: Path, now: str | None = None, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    current_time = _parse_iso8601(now) or datetime.now(timezone.utc)
    status = collect_worker_status(root, omo_dir=omo_dir)
    runs: list[dict[str, object]] = []
    counts = {"healthy": 0, "warning": 0, "stale": 0, "reclaim_due": 0}

    for run in status["runs"]:
        lease = run.get("lease", {})
        last_seen = _parse_iso8601(
            lease.get("last_material_write_at")
        ) or _parse_iso8601(lease.get("last_checkpoint_at"))
        age_seconds = (
            int((current_time - last_seen).total_seconds()) if last_seen else None
        )
        health = "healthy"
        if age_seconds is not None:
            if age_seconds >= lease.get("reclaim_after_seconds", 0):
                health = "reclaim_due"
            elif age_seconds >= lease.get("lease_expired_after_seconds", 0):
                health = "stale"
            elif age_seconds >= lease.get("warning_after_seconds", 0):
                health = "warning"
        counts[health] += 1
        runs.append(
            {
                **run,
                "age_seconds": age_seconds,
                "health": health,
            }
        )

    return {"counts": counts, "runs": runs}


def _build_launch_argv(
    registry: dict, worker_id: str, transport: str, prompt_text: str
) -> list[str]:
    sentinel = "__OMO_PROMPT__"
    template = _worker_command(registry, worker_id, transport).format(prompt=sentinel)
    argv = shlex.split(template)
    forbidden_fragments = ("&&", "||", "|")
    for index, arg in enumerate(argv):
        if index > 0 and argv[index - 1] == "-c":
            continue
        if any(fragment in arg for fragment in forbidden_fragments):
            raise ValueError(f"unsafe worker command template: {template}")
        if ";" in arg and arg != ";" and not arg.startswith("-c"):
            raise ValueError(f"unsafe worker command template: {template}")
    return [prompt_text if arg == sentinel else arg for arg in argv]


def dispatch_task(
    root: Path,
    task_id: str,
    worker_id: str,
    allowed_write_paths: list[str],
    launch: bool = False,
    transport: str = "cli_prompt",
    prior_evidence: list[str] | None = None,
    prompt_addendum: list[str] | None = None,
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

    dispatch_now = now or _utc_now()
    dispatch_id = f"{task_id.lower()}-{worker_id}-{_timestamp_slug(dispatch_now)}"
    run_dir = omo / "workers" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)

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

    source_docs = task.get("source_docs", [])
    deliverables = task.get("deliverables", [])
    allowed_paths = list(allowed_write_paths)
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
            *(f"- You may write to `{path}`" for path in allowed_paths),
            f"- You may write to `{task_file.relative_to(root)}`",
            f"- You may write to `{review_path}`",
            "- Do not modify global state files.",
            "- Do not mark the task `done`.",
            "",
            "## Required deliverables",
            "",
            *(f"- Required deliverable: `{path}`" for path in deliverables),
            "- Updating only the review note is not sufficient when required deliverables are listed.",
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

    launch_command = _worker_command(registry, worker_id, transport).format(
        prompt=f"<prompt:{prompt_path}>"
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

    if launch:
        prompt_text = (root / prompt_path).read_text(encoding="utf-8")
        argv = _build_launch_argv(registry, worker_id, transport, prompt_text)
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        log_content = redact_sensitive_text((result.stdout or "") + (result.stderr or ""))
        write_text_atomic(root / stdout_path, log_content)
        
        # Phase 28 Step 3: Tri-Plane Bus - Broadcast event to Agora EventBus
        def push_log_to_agora(dispatch_id: str, content: str):
            """Push log synchronization event to Agora via internal Event Bus."""
            try:
                import urllib.request
                import json
                import os
                req = urllib.request.Request(
                    "http://127.0.0.1:7430/api/events",
                    data=json.dumps({
                        "type": "omo:log_sync",
                        "source": "omo_worker",
                        "payload": {
                            "dispatch_id": dispatch_id,
                            "content": content
                        }
                    }).encode("utf-8"),
                    method="POST"
                )
                req.add_header("Content-Type", "application/json")
                
                jwt_secret = os.environ.get("AGORA_JWT_SECRET")
                api_key = os.environ.get("AGORA_API_KEY")
                if jwt_secret:
                    import jwt
                    import time
                    token = jwt.encode(
                        {"role": "system_daemon", "exp": time.time() + 3600}, 
                        jwt_secret, 
                        algorithm="HS256"
                    )
                    req.add_header("Authorization", f"Bearer {token}")
                elif api_key:
                    req.add_header("X-API-Key", api_key)
                    
                # Bypass proxy for 127.0.0.1
                proxy_handler = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy_handler)
                opener.open(req, timeout=3.0)
            except Exception as e:
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
    return 0


def _print_worker_status(root: Path, omo_dir: str | Path = ".omo") -> int:
    status = collect_worker_status(root, omo_dir=omo_dir)
    print(f"active_dispatches={status['active_dispatches']}")
    for run in status["runs"]:
        print(
            f"{run['task_id']} worker={run['worker_id']} "
            f"state={run['dispatch_state']} checkpoints={len(run['checkpoint_refs'])} "
            f"reclaim={run['reclaim_ref']}"
        )
    return 0


def _print_worker_watchdog(
    root: Path, now: str | None = None, omo_dir: str | Path = ".omo"
) -> int:
    watchdog = scan_runtime_watchdog(root, now=now, omo_dir=omo_dir)
    counts = watchdog["counts"]
    print(
        f"healthy={counts['healthy']} warning={counts['warning']} "
        f"stale={counts['stale']} reclaim_due={counts['reclaim_due']}"
    )
    for run in watchdog["runs"]:
        print(
            f"{run['task_id']} worker={run['worker_id']} state={run['dispatch_state']} "
            f"health={run['health']} age_seconds={run['age_seconds']}"
        )
    return 0


def _print_worker_admission_eval(
    root: Path, envelope_ref: str, matrix_ref: str | None = None
) -> int:
    result = evaluate_worker_envelope(
        root,
        Path(envelope_ref),
        matrix_ref=Path(matrix_ref) if matrix_ref else None,
    )
    print(
        f"action={result['action']} membership={result['membership_ref']} "
        f"decision={result['decision']} approval_required={result['approval_required']}"
    )
    return 0


def _request_worker_admission_approval(
    root: Path,
    envelope_ref: str,
    requested_by: str,
    now: str,
) -> int:
    result = request_conditional_approval(
        root, Path(envelope_ref), requested_by=requested_by, now=now
    )
    print(
        f"proposal={result['proposal_id']} approval_ref={result['approval_ref']} decision={result['decision']}"
    )
    return 0


def _print_worker_rollout_eval(root: Path, envelope_ref: str) -> int:
    result = evaluate_rollout_envelope(root, Path(envelope_ref))
    print(
        f"action={result['action']} approval={result['approval_status']} "
        f"decision={result['decision']} acceptance_ready={result['acceptance_ready']}"
    )
    return 0


def _accept_worker_rollout(
    root: Path, envelope_ref: str, accepted_by: str, now: str
) -> int:
    result = accept_rollout_envelope(
        root, Path(envelope_ref), accepted_by=accepted_by, now=now
    )
    print(f"acceptance_ref={result['acceptance_ref']} decision={result['decision']}")
    return 0


def _print_worker_rules_eval(root: Path, envelope_ref: str) -> int:
    result = evaluate_rule_bundle(root, Path(envelope_ref))
    delivery_contract = result.get("delivery_contract_ref")
    delivery_segment = (
        f" delivery_contract={delivery_contract}" if delivery_contract else ""
    )
    print(
        f"action={result['action']} registry={result['registry_ref']} "
        f"data_policy={result['data_policy_ref']}{delivery_segment} "
        f"runtime_boundary={result['runtime_boundary_ref']}"
    )
    return 0


def _promotion_eval(
    root: Path, task_id: str, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    task_file = _find_planned_task_file(omo / "tasks" / "planned", task_id)
    task = _load_yaml(task_file)
    active_target = omo / "tasks" / "active" / task_file.name
    approval_result = (
        {"approval_ready": True, "blocker": None}
        if not task.get("human_approval_required")
        else evaluate_promotion_approval(
            root,
            approval_ref=task.get("approval_ref"),
            task_id=task_id,
            task_ref=str(task_file.relative_to(root)),
        )
    )

    checks = {
        "queue_membership_ok": True,
        "status_ok": task.get("status") in {"candidate", "pending"},
        "phase_ok": task.get("phase") == int(goals["phase"]) + 1,
        "approval_ready": approval_result["approval_ready"],
        "target_path_clear": not active_target.exists(),
    }

    active_ready_errors = validate_task_file(task_file)
    checks["active_schema_ready"] = not active_ready_errors

    blockers: list[str] = []
    if not checks["status_ok"]:
        blockers.append("status_invalid")
    if not checks["phase_ok"]:
        blockers.append("phase_mismatch")
    if approval_result["blocker"] == "approval_missing":
        blockers.append("approval_missing")
    elif approval_result["blocker"] == "approval_invalid":
        blockers.append("approval_invalid")
    if not checks["target_path_clear"]:
        blockers.append("target_path_exists")
    if not checks["active_schema_ready"]:
        blockers.append("active_schema_invalid")

    return {
        "task_id": task_id,
        "task_ref": str(task_file.relative_to(root)),
        "eligible": not blockers,
        "blockers": blockers,
        "checks": checks,
        "errors": active_ready_errors,
    }


def _print_task_promotion_eval(
    root: Path, task_id: str, omo_dir: str | Path = ".omo"
) -> int:
    result = _promotion_eval(root, task_id, omo_dir=omo_dir)
    print(
        f"task_id={result['task_id']} eligible={str(result['eligible']).lower()} "
        f"blockers={','.join(result['blockers']) or 'none'}"
    )
    return 0 if result["eligible"] else 1


def _promotion_stamp(now: str) -> str:
    return now.replace(":", "-")


def _task_has_task_specific_promotion_approval(approval_ref: str | None) -> bool:
    return bool(
        approval_ref
        and approval_ref.endswith(".yaml")
        and "-promotion-approval-" in approval_ref
    )


def _execute_governance_overlay_target_actions(
    root: Path,
    *,
    actor: str,
    run_now: str,
    omo_dir: str | Path,
    target_results: list[dict[str, object]],
) -> tuple[list[dict[str, object]], bool, bool]:
    executed_results: list[dict[str, object]] = []
    any_advanced = False
    any_waiting = False
    for target in target_results:
        executed = dict(target)
        action = executed.get("action")
        task_id = executed.get("task_id")
        if action == "request_approval":
            approval_ref, proposal_ref = _request_task_promotion_approval_record(
                root,
                str(task_id),
                requested_by=actor,
                now=run_now,
                omo_dir=omo_dir,
            )
            executed["result"] = "approval_requested"
            executed["approval_ref"] = approval_ref
            executed["proposal_ref"] = proposal_ref
            executed["detail"] = "task-specific promotion approval request created"
            any_advanced = True
        elif action == "promote_apply":
            promote_rc = _apply_task_promotion(
                root, str(task_id), promoted_by=actor, now=run_now, omo_dir=omo_dir
            )
            if promote_rc == 0:
                executed["result"] = "promoted"
                executed["promotion_ref"] = (
                    f".omo/workers/runs/{task_id}-promotion-{_promotion_stamp(run_now)}.yaml"
                )
                executed["detail"] = "planned task promoted into active queue"
                any_advanced = True
            else:
                executed["result"] = "promotion_blocked"
                executed["detail"] = (
                    "promote-apply was blocked by existing promotion gates"
                )
                any_waiting = True
        elif action == "await_approval":
            executed["result"] = "approval_pending"
            executed["detail"] = (
                "task-specific promotion approval exists but is not granted yet"
            )
            any_waiting = True
        executed_results.append(executed)
    return executed_results, any_advanced, any_waiting


def _sync_omo_state(root: Path, omo_dir: str | Path) -> None:
    subprocess.run(
        ["python3", "scripts/sync_omo_state.py", "--omo-dir", str(omo_dir)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _apply_task_promotion(
    root: Path, task_id: str, promoted_by: str, now: str, omo_dir: str | Path = ".omo"
) -> int:
    result = _promotion_eval(root, task_id, omo_dir=omo_dir)
    if not result["eligible"]:
        print(
            f"task_id={task_id} eligible=false blockers={','.join(result['blockers'])}"
        )
        return 1

    omo = _omo_path(root, omo_dir)
    planned_path = root / result["task_ref"]
    active_path = omo / "tasks" / "active" / planned_path.name
    task = _load_yaml(planned_path)
    stamp = _promotion_stamp(now)
    envelope_rel = (
        Path(omo_dir) / "workers" / "runs" / f"{task_id}-promotion-{stamp}.yaml"
    )
    envelope_path = root / envelope_rel
    envelope = {
        "version": 1,
        "promotion_id": f"{task_id}-promotion-{stamp}",
        "task_id": task_id,
        "task_ref_before": str(Path(omo_dir) / "tasks" / "planned" / planned_path.name),
        "task_ref_after": str(Path(omo_dir) / "tasks" / "active" / planned_path.name),
        "promotion_status": "approved",
        "promoted_by": promoted_by,
        "promoted_at": now,
        "phase_gate": {
            "current_phase": int(_load_yaml(omo / "goals" / "current.yaml")["phase"]),
            "target_phase": task["phase"],
            "allowed_by_rule": True,
        },
        "approval": {
            "required": bool(task.get("human_approval_required")),
            "approval_ref": task.get("approval_ref"),
        },
        "checks": result["checks"],
        "rollback": {
            "supported": True,
            "rollback_action": "move task back to planned and rerun sync",
        },
        "refs": {
            "state_ref": str(Path(omo_dir) / "state" / "system.yaml"),
            "goals_ref": str(Path(omo_dir) / "goals" / "current.yaml"),
        },
    }
    _write_yaml(envelope_path, envelope)

    original_handoffs = list(task.get("handoff_refs", []))
    task["handoff_refs"] = _append_unique(original_handoffs, [str(envelope_rel)])
    _write_yaml(planned_path, task)

    active_path.parent.mkdir(parents=True, exist_ok=True)
    planned_path.replace(active_path)
    try:
        _sync_omo_state(root, omo_dir)
    except subprocess.CalledProcessError:
        active_task = _load_yaml(active_path)
        active_task["handoff_refs"] = original_handoffs
        _write_yaml(active_path, active_task)
        active_path.replace(planned_path)
        envelope_path.unlink(missing_ok=True)
        print(f"task_id={task_id} promoted=false blockers=sync_failed")
        return 1

    print(
        f"promotion_ref={envelope_rel} task_ref={Path(omo_dir) / 'tasks' / 'active' / planned_path.name}"
    )
    return 0


def _request_task_promotion_approval(
    root: Path,
    task_id: str,
    requested_by: str,
    now: str,
    omo_dir: str | Path = ".omo",
) -> int:
    approval_ref, proposal_ref = _request_task_promotion_approval_record(
        root,
        task_id,
        requested_by=requested_by,
        now=now,
        omo_dir=omo_dir,
    )
    print(f"approval_ref={approval_ref} proposal_ref={proposal_ref}")
    return 0


def _request_task_contract_declaration(
    root: Path,
    task_id: str,
    deliverables: list[str],
    actor: str,
    now: str,
    omo_dir: str | Path = ".omo",
) -> int:
    request_ref, proposal_ref = _request_task_contract_declaration_record(
        root,
        task_id,
        deliverables=deliverables,
        actor=actor,
        now=now,
        omo_dir=omo_dir,
    )
    print(f"request_ref={request_ref} proposal_ref={proposal_ref}")
    return 0


def _request_task_contract_declaration_record(
    root: Path,
    task_id: str,
    *,
    deliverables: list[str],
    actor: str,
    now: str,
    omo_dir: str | Path = ".omo",
) -> tuple[str, str]:
    if not deliverables:
        raise ValueError("deliverables must not be empty")

    omo = _omo_path(root, omo_dir)
    task_path = _find_task_file(omo / "tasks" / "active", task_id)
    task = _load_yaml(task_path)
    status = build_governance_overlay_status(root, omo_dir=omo_dir, now=now)["yaml"]
    target_state = next(
        (
            target
            for target in status.get("active_target_states", [])
            if target.get("task_id") == task_id
        ),
        None,
    )
    if target_state is None or target_state.get("state") != "active_dispatch_blocked":
        raise ValueError("task is not currently blocked on contract gap")

    request_ref = contract_request_ref(task_id, now)
    request_record = build_contract_request(
        task_id=task_id,
        task_ref=str(task_path.relative_to(root)),
        deliverables=deliverables,
        requested_at=now,
        requested_by=actor,
        request_ref=request_ref,
    )
    proposal = build_contract_proposal(
        task_id=task_id,
        task_ref=str(task_path.relative_to(root)),
        deliverables=deliverables,
        requested_by=actor,
        request_ref=request_ref,
    )
    proposal_record = propose_truth_mutation(root, proposal, now=now)

    _write_yaml(root / request_ref, request_record)
    task["handoff_refs"] = _append_unique(task.get("handoff_refs", []), [request_ref])
    _write_yaml(task_path, task)
    proposal_ref = (
        Path(omo_dir)
        / "_truth"
        / "task-center"
        / "proposals"
        / f"{proposal_record['id']}.yaml"
    )
    return request_ref, str(proposal_ref)


def _request_task_promotion_approval_record(
    root: Path,
    task_id: str,
    requested_by: str,
    now: str,
    omo_dir: str | Path = ".omo",
) -> tuple[str, str]:
    omo = _omo_path(root, omo_dir)
    task_path = _find_planned_task_file(omo / "tasks" / "planned", task_id)
    task = _load_yaml(task_path)
    if not task.get("human_approval_required"):
        raise ValueError("task does not require human approval")
    if task.get("status") not in {"candidate", "pending"}:
        raise ValueError(
            "task must remain candidate or pending before requesting promotion approval"
        )
    if _task_has_task_specific_promotion_approval(task.get("approval_ref")):
        raise ValueError("task already points to a task-specific promotion approval")

    approval_ref = promotion_approval_ref(task_id, now)
    approval_record = build_promotion_approval_request(
        task_id=task_id,
        task_ref=str(task_path.relative_to(root)),
        requested_operation_level=str(task["risk_level"]),
        requested_at=now,
        approval_ref=approval_ref,
    )
    proposal = build_promotion_approval_proposal(
        task_id=task_id,
        requested_by=requested_by,
        approval_ref=approval_ref,
    )
    proposal_record = propose_truth_mutation(root, proposal, now=now)

    _write_yaml(root / approval_ref, approval_record)
    task["approval_ref"] = approval_ref
    _write_yaml(task_path, task)
    proposal_ref = (
        Path(omo_dir)
        / "_truth"
        / "task-center"
        / "proposals"
        / f"{proposal_record['id']}.yaml"
    )
    return approval_ref, str(proposal_ref)


def _write_task_promotion_history(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_promotion_history(root, omo_dir=omo_dir, now=now or _utc_now())
    omo = _omo_path(root, omo_dir)
    current_yaml = omo / "workers" / "promotion" / "current.yaml"
    current_md = omo / "workers" / "promotion" / "current.md"
    _write_yaml(current_yaml, result["yaml"])
    write_text_atomic(current_md, result["markdown"])
    print(
        f"promotion_count={result['yaml']['promotion_count']} "
        f"latest_promotion_ref={result['yaml']['latest_promotion_ref']}"
    )
    return 0


def _promotion_readiness_entry(
    root: Path, task_path: Path, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    task = _load_yaml(task_path)
    eval_result = _promotion_eval(root, task["id"], omo_dir=omo_dir)
    return {
        "task_id": task["id"],
        "task_ref": eval_result["task_ref"],
        "phase": task["phase"],
        "status": task["status"],
        "risk_level": task["risk_level"],
        "allowed_operation_level": task["allowed_operation_level"],
        "human_approval_required": bool(task.get("human_approval_required")),
        "approval_ref": task.get("approval_ref"),
        "eligible": eval_result["eligible"],
        "blockers": eval_result["blockers"],
        "checks": eval_result["checks"],
        "errors": eval_result["errors"],
    }


def _write_task_promotion_readiness(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    planned_dir = omo / "tasks" / "planned"
    entries = tuple(
        _promotion_readiness_entry(root, task_path, omo_dir=omo_dir)
        for task_path in sorted(planned_dir.glob("*.yaml"))
    )
    packet = build_promotion_readiness_packet(
        generated_at=now or _utc_now(),
        current_phase=int(goals["phase"]),
        tasks=entries,
    )
    readiness_dir = omo / "workers" / "promotion"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(readiness_dir / "readiness.yaml", packet)
    write_text_atomic(
        readiness_dir / "readiness.md", render_promotion_readiness_markdown(packet)
    )
    print(
        f"ready_count={packet['ready_count']} blocked_count={packet['blocked_count']}"
    )
    return 0


def _proposal_status(root: Path, proposal_ref: str) -> str:
    proposal_path = root / proposal_ref
    if not proposal_path.exists():
        return "missing"
    proposal = _load_yaml(proposal_path)
    return str(proposal.get("status", "missing"))


def _promotion_approval_status_entry(
    root: Path, task_path: Path, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    task = _load_yaml(task_path)
    approval_ref = str(task.get("approval_ref") or "")
    if not _task_has_task_specific_promotion_approval(approval_ref):
        raise ValueError("task does not point to a task-specific promotion approval")

    approval = _load_yaml(root / approval_ref)
    approval_id = str(approval.get("approval_id") or Path(approval_ref).stem)
    proposal_id = f"{approval_id}-proposal"
    proposal_ref = str(
        Path(omo_dir) / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml"
    )
    eval_result = _promotion_eval(root, task["id"], omo_dir=omo_dir)
    return {
        "task_id": task["id"],
        "task_ref": str(task_path.relative_to(root)),
        "approval_ref": approval_ref,
        "approval_id": approval_id,
        "approval_status": str(approval.get("approval_status", "missing")),
        "proposal_id": proposal_id,
        "proposal_ref": proposal_ref,
        "proposal_status": _proposal_status(root, proposal_ref),
        "human_approval_required": bool(task.get("human_approval_required")),
        "eligible": eval_result["eligible"],
        "blockers": eval_result["blockers"],
    }


def _write_task_promotion_approval_status(
    root: Path,
    omo_dir: str | Path = ".omo",
    now: str | None = None,
    task_id: str | None = None,
) -> int:
    omo = _omo_path(root, omo_dir)
    planned_dir = omo / "tasks" / "planned"
    task_paths = (
        [_find_planned_task_file(planned_dir, task_id)]
        if task_id
        else [
            path
            for path in sorted(planned_dir.glob("*.yaml"))
            if _task_has_task_specific_promotion_approval(
                _load_yaml(path).get("approval_ref")
            )
        ]
    )
    entries = [
        _promotion_approval_status_entry(root, path, omo_dir=omo_dir)
        for path in task_paths
    ]
    packet = build_promotion_approval_status_packet(
        generated_at=now or _utc_now(), tasks=entries
    )
    approvals_dir = omo / "workers" / "promotion" / "approvals"
    approvals_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(approvals_dir / "current.yaml", packet)
    write_text_atomic(
        approvals_dir / "current.md", render_promotion_approval_status_markdown(packet)
    )
    print(
        f"approval_task_count={packet['approval_task_count']} granted_count={packet['granted_count']}"
    )
    return 0


def _write_task_promotion_approval_history(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_promotion_approval_history(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    history_dir = omo / "workers" / "promotion" / "approvals" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(history_dir / "current.yaml", result["yaml"])
    write_text_atomic(history_dir / "current.md", result["markdown"])
    print(
        f"approval_count={result['yaml']['approval_count']} latest_approval_ref={result['yaml']['latest_approval_ref']}"
    )
    return 0


def _write_task_promotion_approval_analytics(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_promotion_approval_analytics_packet(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    analytics_dir = omo / "workers" / "promotion" / "approvals" / "analytics"
    analytics_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(analytics_dir / "current.yaml", result["yaml"])
    write_text_atomic(analytics_dir / "current.md", result["markdown"])
    print(
        "approval_task_count="
        f"{result['yaml']['approval_task_count']} "
        f"approve_now={len(result['yaml']['action_queues']['approve_now'])} "
        f"apply_now={len(result['yaml']['action_queues']['apply_now'])}"
    )
    return 0


def _write_task_governance_overlay_status(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_status(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "eligible_count="
        f"{result['yaml']['eligible_count']} "
        f"blocked_count={result['yaml']['blocked_count']} "
        f"next_action={result['yaml']['next_action']}"
    )
    return 0


def _write_task_governance_overlay_approval_prep_status(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_approval_prep_status(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay" / "approval-prep"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "prep_task_count="
        f"{result['yaml']['prep_task_count']} "
        f"request_now_count={result['yaml']['request_now_count']} "
        f"awaiting_approval_count={result['yaml']['awaiting_approval_count']}"
    )
    return 0


def _write_task_governance_overlay_approval_prep_history(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_approval_prep_history(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay" / "approval-prep" / "history"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        f"event_count={result['yaml']['event_count']} latest_run_id={result['yaml']['latest_run_id'] or 'none'}"
    )
    return 0


def _write_task_governance_overlay_approval_prep_analytics(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_approval_prep_analytics(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay" / "approval-prep" / "analytics"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "prep_task_count="
        f"{result['yaml']['prep_task_count']} "
        f"awaiting_approval_count={result['yaml']['awaiting_approval_count']}"
    )
    return 0


def _write_task_governance_overlay_approval_prep_trend(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_approval_prep_trend(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay" / "approval-prep" / "trend"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "trend_status="
        f"{result['yaml']['trend_status']} "
        f"window_event_count={result['yaml']['window_event_count']}"
    )
    return 0


def _write_task_governance_overlay_approval_prep_aging(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_approval_prep_aging(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay" / "approval-prep" / "aging"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "aging_status="
        f"{result['yaml']['aging_status']} "
        f"prep_task_count={result['yaml']['prep_task_count']}"
    )
    return 0


def _write_task_governance_overlay_approval_prep_diff(
    root: Path, omo_dir: str | Path = ".omo", now: str | None = None
) -> int:
    result = build_governance_overlay_approval_prep_diff(
        root, omo_dir=omo_dir, now=now or _utc_now()
    )
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay" / "approval-prep" / "diff"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "diff_status="
        f"{result['yaml']['diff_status']} "
        f"current_task_count={result['yaml']['current_task_count']}"
    )
    return 0


def _write_task_governance_overlay_run_next(
    root: Path,
    *,
    omo_dir: str | Path = ".omo",
    actor: str,
    now: str | None = None,
) -> int:
    run_now = now or _utc_now()
    planned = plan_governance_overlay_cycle(
        root, omo_dir=omo_dir, actor=actor, now=run_now
    )
    run = planned["run"]
    roadmap = planned["roadmap"]
    omo = _omo_path(root, omo_dir)
    control = _load_yaml(omo / "_control" / "governance-overlay" / "current.yaml")

    roadmap_item = None
    if run["roadmap_item_id"]:
        for item in roadmap.get("items", []):
            if item.get("id") == run["roadmap_item_id"]:
                roadmap_item = item
                break

    if run.get("mode") == "continue_active":
        if roadmap_item is not None and run["summary"] == "close_ready":
            roadmap_item["status"] = "done"
            control["current_milestone"] = run["control_updates"].get(
                "current_milestone"
            )
            control["next_milestone"] = run["control_updates"].get("next_milestone")
            control["updated_at"] = run_now
            run["summary"] = "closed"
        elif roadmap_item is not None and run["summary"] == "block_ready":
            roadmap_item["status"] = "blocked"
            roadmap_item["blocked_reason"] = "all_targets_terminal_blocked"
            run["summary"] = "blocked"
        elif str(run.get("next_action_before_run", "")).startswith("dispatch:"):
            task_id = str(run["next_action_before_run"]).split(":", 1)[1]
            registry = _load_yaml(omo / "_truth" / "registry" / "workers.yaml")
            task = _load_yaml(_find_task_file(omo / "tasks" / "active", task_id))
            dispatch = dispatch_task(
                root,
                task_id,
                _default_enabled_worker_id(registry),
                _dispatch_allowed_write_paths(task),
                launch=False,
                now=run_now,
                omo_dir=omo_dir,
            )
            for target in run["target_results"]:
                if target.get("task_id") == task_id:
                    target["result"] = "dispatched"
                    target["dispatch_id"] = dispatch["dispatch_id"]
                    target["dispatch_path"] = dispatch["dispatch_path"]
                    target["detail"] = (
                        "active pending task was preclaimed into worker dispatch flow"
                    )
                    break
            run["summary"] = "dispatched"
        elif str(run.get("next_action_before_run", "")).startswith("contract:"):
            task_id = str(run["next_action_before_run"]).split(":", 1)[1]
            for target in run["target_results"]:
                if target.get("task_id") == task_id:
                    target["result"] = "contract_gap"
                    target["detail"] = (
                        "task must declare explicit deliverables/write scope before autonomous launch"
                    )
                    break
            run["summary"] = "contract_gap"
        elif str(run.get("next_action_before_run", "")).startswith("launch:"):
            task_id = str(run["next_action_before_run"]).split(":", 1)[1]
            task = _load_yaml(_find_task_file(omo / "tasks" / "active", task_id))
            dispatch = _launch_existing_dispatch(
                root, root / task["run_ref"], omo_dir=omo_dir
            )
            for target in run["target_results"]:
                if target.get("task_id") == task_id:
                    target["result"] = "launched"
                    target["dispatch_state"] = dispatch["dispatch_state"]
                    target["detail"] = (
                        "dispatched task was launched through the stored worker prompt"
                    )
                    break
            run["summary"] = "launched"
        elif str(run.get("next_action_before_run", "")).startswith("verify:"):
            task_id = str(run["next_action_before_run"]).split(":", 1)[1]
            for target in run["target_results"]:
                if target.get("task_id") == task_id:
                    target["result"] = "verify_ready"
                    target["detail"] = (
                        "active review task is ready for coordinator verification/closeout"
                    )
                    break
            run["summary"] = "verify_ready"
        elif (
            str(run.get("next_action_before_run", "")).startswith("advance:")
            and roadmap_item is not None
        ):
            target_results = [
                evaluate_governance_overlay_planned_target(
                    root, str(ref), omo_dir=omo_dir
                )
                for ref in roadmap_item.get("target_refs", [])
            ]
            executed_results, any_advanced, any_waiting = (
                _execute_governance_overlay_target_actions(
                    root,
                    actor=actor,
                    run_now=run_now,
                    omo_dir=omo_dir,
                    target_results=target_results,
                )
            )
            run["target_results"] = executed_results
            if any_advanced:
                run["summary"] = "advanced"
            elif any_waiting:
                run["summary"] = "waiting_on_external_gate"
        elif str(run.get("next_action_before_run", "")).startswith("monitor:"):
            run["summary"] = "waiting_on_external_gate"

        run_path = omo / "workers" / "runs" / f"{run['run_id']}.yaml"
        _write_yaml(run_path, run)
        _write_yaml(omo / "_truth" / "governance-overlay" / "roadmap.yaml", roadmap)
        _write_yaml(omo / "_control" / "governance-overlay" / "current.yaml", control)

        refreshed = build_governance_overlay_status(root, omo_dir=omo_dir, now=run_now)
        current_dir = omo / "workers" / "governance-overlay"
        current_dir.mkdir(parents=True, exist_ok=True)
        _write_yaml(current_dir / "current.yaml", refreshed["yaml"])
        write_text_atomic(current_dir / "current.md", refreshed["markdown"])
        print(f"summary={run['summary']} roadmap_item_id={run['roadmap_item_id']}")
        return 0

    unsupported_only = bool(run["target_results"]) and all(
        result.get("action") == "mark_blocked" for result in run["target_results"]
    )
    executed_results, any_advanced, any_waiting = (
        _execute_governance_overlay_target_actions(
            root,
            actor=actor,
            run_now=run_now,
            omo_dir=omo_dir,
            target_results=run["target_results"],
        )
    )

    run["target_results"] = executed_results
    if roadmap_item is not None:
        if any_advanced or any_waiting:
            roadmap_item["status"] = "in_progress"
            roadmap_item.pop("blocked_reason", None)
        elif unsupported_only:
            roadmap_item["status"] = "blocked"
            roadmap_item["blocked_reason"] = "unsupported_target_ref"
        elif executed_results:
            roadmap_item["status"] = "blocked"
            roadmap_item["blocked_reason"] = "promotion_blocked"
    if any_advanced:
        run["summary"] = "advanced"
    elif any_waiting:
        run["summary"] = "waiting_on_external_gate"
    elif unsupported_only or executed_results:
        run["summary"] = "blocked"

    run_path = omo / "workers" / "runs" / f"{run['run_id']}.yaml"
    _write_yaml(run_path, run)
    _write_yaml(omo / "_truth" / "governance-overlay" / "roadmap.yaml", roadmap)

    refreshed = build_governance_overlay_status(root, omo_dir=omo_dir, now=run_now)
    current_dir = omo / "workers" / "governance-overlay"
    current_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(current_dir / "current.yaml", refreshed["yaml"])
    write_text_atomic(current_dir / "current.md", refreshed["markdown"])
    print(f"summary={run['summary']} roadmap_item_id={run['roadmap_item_id']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worker_parser = subparsers.add_parser("worker")
    worker_sub = worker_parser.add_subparsers(dest="worker_command", required=True)

    dispatch_parser = worker_sub.add_parser("dispatch")
    dispatch_parser.add_argument("task_id")
    dispatch_parser.add_argument("--worker", required=True, dest="worker_id")
    dispatch_parser.add_argument(
        "--write-path", action="append", default=[], dest="write_paths"
    )
    dispatch_parser.add_argument("--launch", action="store_true")
    dispatch_parser.add_argument("--transport", default="cli_prompt")
    dispatch_parser.add_argument("--omo-dir", default=".omo")

    reclaim_parser = worker_sub.add_parser("reclaim")
    reclaim_parser.add_argument("task_id")
    reclaim_parser.add_argument(
        "--successor", required=True, dest="successor_worker_id"
    )
    reclaim_parser.add_argument("--reason", required=True)
    reclaim_parser.add_argument(
        "--write-path", action="append", default=[], dest="write_paths"
    )
    reclaim_parser.add_argument("--launch", action="store_true")
    reclaim_parser.add_argument("--transport", default="cli_prompt")
    reclaim_parser.add_argument("--omo-dir", default=".omo")

    gc_parser = worker_sub.add_parser("gc")
    gc_parser.add_argument(
        "--dry-run", action="store_true", help="Just list, don't delete"
    )
    gc_parser.add_argument(
        "--retain",
        type=int,
        default=50,
        help="Number of latest dispatch runs to retain",
    )
    gc_parser.add_argument("--omo-dir", default=".omo")

    status_parser = worker_sub.add_parser("status")
    status_parser.add_argument("--omo-dir", default=".omo")
    baseline_parser = worker_sub.add_parser("baseline")
    baseline_parser.add_argument("--root", default=".")
    handoff_parser = worker_sub.add_parser("handoff-index")
    handoff_parser.add_argument("task_id")
    watchdog_parser = worker_sub.add_parser("watchdog")
    watchdog_parser.add_argument("--now")
    watchdog_parser.add_argument("--omo-dir", default=".omo")
    admission_parser = worker_sub.add_parser("admission-eval")
    admission_parser.add_argument("envelope_ref")
    admission_parser.add_argument("--matrix-ref")
    request_approval_parser = worker_sub.add_parser("admission-request-approval")
    request_approval_parser.add_argument("envelope_ref")
    request_approval_parser.add_argument("--requested-by", required=True)
    request_approval_parser.add_argument("--now", required=True)
    rules_eval_parser = worker_sub.add_parser("rules-eval")
    rules_eval_parser.add_argument("envelope_ref")
    rollout_eval_parser = worker_sub.add_parser("rollout-eval")
    rollout_eval_parser.add_argument("envelope_ref")
    rollout_accept_parser = worker_sub.add_parser("rollout-accept")
    rollout_accept_parser.add_argument("envelope_ref")
    rollout_accept_parser.add_argument("--accepted-by", required=True)
    rollout_accept_parser.add_argument("--now", required=True)

    task_parser = subparsers.add_parser("task")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)
    validate_parser = task_sub.add_parser("validate")
    validate_parser.add_argument("task_file", nargs="?")
    validate_parser.add_argument("--all-active", action="store_true")
    validate_parser.add_argument("--all-planned", action="store_true")
    promote_eval_parser = task_sub.add_parser("promote-eval")
    promote_eval_parser.add_argument("task_id")
    promote_eval_parser.add_argument("--omo-dir", default=".omo")
    promote_apply_parser = task_sub.add_parser("promote-apply")
    promote_apply_parser.add_argument("task_id")
    promote_apply_parser.add_argument("--promoted-by", required=True)
    promote_apply_parser.add_argument("--now", required=True)
    promote_apply_parser.add_argument("--omo-dir", default=".omo")
    promotion_history_parser = task_sub.add_parser("promotion-history")
    promotion_history_parser.add_argument("--omo-dir", default=".omo")
    promotion_history_parser.add_argument("--now")
    promotion_readiness_parser = task_sub.add_parser("promotion-readiness")
    promotion_readiness_parser.add_argument("--omo-dir", default=".omo")
    promotion_readiness_parser.add_argument("--now")
    promotion_request_parser = task_sub.add_parser("promotion-request-approval")
    promotion_request_parser.add_argument("task_id")
    promotion_request_parser.add_argument("--requested-by", required=True)
    promotion_request_parser.add_argument("--now", required=True)
    promotion_request_parser.add_argument("--omo-dir", default=".omo")
    contract_request_parser = task_sub.add_parser("contract-declare-deliverables")
    contract_request_parser.add_argument("task_id")
    contract_request_parser.add_argument("--deliverables", nargs="+", required=True)
    contract_request_parser.add_argument("--actor", required=True)
    contract_request_parser.add_argument("--now", required=True)
    contract_request_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_status_parser = task_sub.add_parser("promotion-approval-status")
    promotion_approval_status_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_status_parser.add_argument("--task-id")
    promotion_approval_status_parser.add_argument("--now")
    promotion_approval_history_parser = task_sub.add_parser(
        "promotion-approval-history"
    )
    promotion_approval_history_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_history_parser.add_argument("--now")
    promotion_approval_analytics_parser = task_sub.add_parser(
        "promotion-approval-analytics"
    )
    promotion_approval_analytics_parser.add_argument("--omo-dir", default=".omo")
    promotion_approval_analytics_parser.add_argument("--now")
    governance_overlay_status_parser = task_sub.add_parser("governance-overlay-status")
    governance_overlay_status_parser.add_argument("--omo-dir", default=".omo")
    governance_overlay_status_parser.add_argument("--now")
    governance_overlay_approval_prep_status_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-status"
    )
    governance_overlay_approval_prep_status_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_status_parser.add_argument("--now")
    governance_overlay_approval_prep_history_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-history"
    )
    governance_overlay_approval_prep_history_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_history_parser.add_argument("--now")
    governance_overlay_approval_prep_analytics_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-analytics"
    )
    governance_overlay_approval_prep_analytics_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_analytics_parser.add_argument("--now")
    governance_overlay_approval_prep_aging_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-aging"
    )
    governance_overlay_approval_prep_aging_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_aging_parser.add_argument("--now")
    governance_overlay_approval_prep_diff_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-diff"
    )
    governance_overlay_approval_prep_diff_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_diff_parser.add_argument("--now")
    governance_overlay_approval_prep_trend_parser = task_sub.add_parser(
        "governance-overlay-approval-prep-trend"
    )
    governance_overlay_approval_prep_trend_parser.add_argument(
        "--omo-dir", default=".omo"
    )
    governance_overlay_approval_prep_trend_parser.add_argument("--now")
    governance_overlay_run_next_parser = task_sub.add_parser(
        "governance-overlay-run-next"
    )
    governance_overlay_run_next_parser.add_argument("--omo-dir", default=".omo")
    governance_overlay_run_next_parser.add_argument("--actor", required=True)
    governance_overlay_run_next_parser.add_argument("--now")

    args = parser.parse_args(argv)

    if args.command == "worker" and args.worker_command == "dispatch":
        dispatch_task(
            Path.cwd(),
            task_id=args.task_id,
            worker_id=args.worker_id,
            allowed_write_paths=args.write_paths,
            launch=args.launch,
            transport=args.transport,
            omo_dir=args.omo_dir,
        )
        return 0

    if args.command == "worker" and args.worker_command == "reclaim":
        reclaim_task(
            Path.cwd(),
            task_id=args.task_id,
            successor_worker_id=args.successor_worker_id,
            allowed_write_paths=args.write_paths,
            reason=args.reason,
            launch=args.launch,
            transport=args.transport,
            omo_dir=args.omo_dir,
        )
        return 0

    if args.command == "worker" and args.worker_command == "gc":
        return _worker_gc(
            Path.cwd(), dry_run=args.dry_run, retain=args.retain, omo_dir=args.omo_dir
        )

    if args.command == "worker" and args.worker_command == "status":
        return _print_worker_status(Path.cwd(), omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "baseline":
        print(write_worker_utilization_summary(Path(args.root).resolve()))
        return 0

    if args.command == "worker" and args.worker_command == "handoff-index":
        print(write_handoff_index(Path.cwd(), args.task_id))
        return 0

    if args.command == "worker" and args.worker_command == "watchdog":
        return _print_worker_watchdog(Path.cwd(), now=args.now, omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "admission-eval":
        return _print_worker_admission_eval(
            Path.cwd(), args.envelope_ref, matrix_ref=args.matrix_ref
        )

    if args.command == "worker" and args.worker_command == "admission-request-approval":
        return _request_worker_admission_approval(
            Path.cwd(), args.envelope_ref, requested_by=args.requested_by, now=args.now
        )

    if args.command == "worker" and args.worker_command == "rules-eval":
        return _print_worker_rules_eval(Path.cwd(), args.envelope_ref)

    if args.command == "worker" and args.worker_command == "rollout-eval":
        return _print_worker_rollout_eval(Path.cwd(), args.envelope_ref)

    if args.command == "worker" and args.worker_command == "rollout-accept":
        return _accept_worker_rollout(
            Path.cwd(), args.envelope_ref, accepted_by=args.accepted_by, now=args.now
        )

    if args.command == "task" and args.task_command == "validate":
        if args.all_planned:
            results = validate_planned_tasks(Path.cwd())
            if not results:
                return 0
            for path, errors in results.items():
                print(path)
                for error in errors:
                    print(f"  - {error}")
            return 1

        if args.all_active or not args.task_file:
            results = validate_active_tasks(Path.cwd())
            if not results:
                return 0
            for path, errors in results.items():
                print(path)
                for error in errors:
                    print(f"  - {error}")
            return 1

        errors = validate_task_file(Path(args.task_file))
        if not errors:
            return 0
        for error in errors:
            print(error)
        return 1

    if args.command == "task" and args.task_command == "promote-eval":
        return _print_task_promotion_eval(
            Path.cwd(), args.task_id, omo_dir=args.omo_dir
        )

    if args.command == "task" and args.task_command == "promote-apply":
        return _apply_task_promotion(
            Path.cwd(),
            args.task_id,
            promoted_by=args.promoted_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "promotion-history":
        return _write_task_promotion_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "promotion-readiness":
        return _write_task_promotion_readiness(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "promotion-request-approval":
        return _request_task_promotion_approval(
            Path.cwd(),
            args.task_id,
            requested_by=args.requested_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "contract-declare-deliverables":
        return _request_task_contract_declaration(
            Path.cwd(),
            args.task_id,
            deliverables=list(args.deliverables),
            actor=args.actor,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "promotion-approval-status":
        return _write_task_promotion_approval_status(
            Path.cwd(),
            omo_dir=args.omo_dir,
            now=args.now,
            task_id=args.task_id,
        )

    if args.command == "task" and args.task_command == "promotion-approval-history":
        return _write_task_promotion_approval_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "promotion-approval-analytics":
        return _write_task_promotion_approval_analytics(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "governance-overlay-status":
        return _write_task_governance_overlay_status(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-status"
    ):
        return _write_task_governance_overlay_approval_prep_status(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-history"
    ):
        return _write_task_governance_overlay_approval_prep_history(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-analytics"
    ):
        return _write_task_governance_overlay_approval_prep_analytics(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-aging"
    ):
        return _write_task_governance_overlay_approval_prep_aging(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-diff"
    ):
        return _write_task_governance_overlay_approval_prep_diff(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if (
        args.command == "task"
        and args.task_command == "governance-overlay-approval-prep-trend"
    ):
        return _write_task_governance_overlay_approval_prep_trend(
            Path.cwd(), omo_dir=args.omo_dir, now=args.now
        )

    if args.command == "task" and args.task_command == "governance-overlay-run-next":
        return _write_task_governance_overlay_run_next(
            Path.cwd(),
            omo_dir=args.omo_dir,
            actor=args.actor,
            now=args.now,
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
