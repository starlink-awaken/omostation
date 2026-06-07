#!/usr/bin/env python3
from __future__ import annotations
import subprocess
from pathlib import Path

from .omo_contract_request import (
    build_contract_proposal,
    build_contract_request,
    contract_request_ref,
)
from .omo_governance import propose_truth_mutation
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
from .omo_io import write_text_atomic
from .omo_promotion_approval import evaluate_promotion_approval
from .omo_promotion_approval_analytics import build_promotion_approval_analytics_packet
from .omo_promotion_approval_history import build_promotion_approval_history
from .omo_promotion_approval_status import (
    build_promotion_approval_status_packet,
    render_promotion_approval_status_markdown,
)
from .omo_promotion_history import build_promotion_history
from .omo_promotion_readiness import (
    build_promotion_readiness_packet,
    render_promotion_readiness_markdown,
)
from .omo_promotion_request import (
    build_promotion_approval_proposal,
    build_promotion_approval_request,
    promotion_approval_ref,
)
from .omo_redaction import redact_sensitive_text
from .omo_task_schema import validate_task_file
from .omo_worker_core import (
    _append_unique,
    _build_launch_argv,
    _default_enabled_worker_id,
    _dispatch_allowed_write_paths,
    _find_planned_task_file,
    _find_task_file,
    _load_yaml,
    _omo_path,
    _utc_now,
    _write_yaml,
)
from .omo_worker_dispatch import dispatch_task

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


