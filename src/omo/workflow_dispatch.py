"""Workflow Mesh admission and worker dispatch bridge.

This module owns the control-plane decision only. It does not execute a worker
or call a backend. A successful result is a signed admission grant plus an
immutable dispatch packet recorded in OMO's append-only event log.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .omo_shared import load_yaml
from .omo_task_schema import validate_task_file
from .workflow_mesh import WorkflowMeshStore, new_workflow_event


class WorkflowDispatchError(ValueError):
    """Admission or dispatch packet failed a governance gate."""


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _proof(grant: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in grant.items() if key != "proof"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _parse_health(health: dict[str, Any], required: list[str]) -> dict[str, Any]:
    if not isinstance(health, dict):
        raise WorkflowDispatchError("capability health snapshot is required")
    status = str(health.get("status", "unavailable"))
    capabilities = health.get("capabilities")
    if not isinstance(capabilities, dict):
        raise WorkflowDispatchError("capability health snapshot has no capabilities")
    unavailable = []
    for capability in required:
        item = capabilities.get(capability)
        if not isinstance(item, dict) or not item.get("available", False):
            unavailable.append(capability)
    if unavailable:
        raise WorkflowDispatchError(
            "required capabilities unavailable: " + ", ".join(unavailable)
        )
    if status == "unhealthy":
        raise WorkflowDispatchError("capability health is unhealthy")
    return {
        "status": status,
        "capabilities": {
            capability: capabilities[capability] for capability in required
        },
        "observed_at": health.get("observed_at"),
        "source": health.get("source", "agora"),
        "snapshot_digest": hashlib.sha256(_canonical(health)).hexdigest(),
    }


def _approval_state(
    root: Path, task: dict[str, Any], task_file: Path
) -> dict[str, Any]:
    required = (
        task.get("risk_level") in {"L2", "L3"}
        or task.get("allowed_operation_level") in {"L2", "L3"}
        or bool(task.get("human_approval_required"))
    )
    approval_ref = task.get("approval_ref")
    if not required:
        return {"required": False, "status": "not_required", "ref": approval_ref}
    if not approval_ref:
        raise WorkflowDispatchError("human approval is required before dispatch")
    approval_path = root / str(approval_ref)
    try:
        approval = load_yaml(approval_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise WorkflowDispatchError("approval record is missing or invalid") from exc
    if approval.get("task_id") != task.get("id"):
        raise WorkflowDispatchError("approval record task mismatch")
    if approval.get("approval_status") != "granted":
        raise WorkflowDispatchError("approval is not granted")
    scope = approval.get("approval_scope")
    if scope not in {"workflow.execute", "task.promote_apply"}:
        raise WorkflowDispatchError("approval scope does not authorize execution")
    task_ref = str(task_file.relative_to(root))
    refs = approval.get("refs", {})
    if refs.get("task_ref") not in {task_ref, str(approval_ref)}:
        raise WorkflowDispatchError("approval record task reference mismatch")
    return {
        "required": True,
        "status": "granted",
        "ref": str(approval_ref),
        "approval_id": approval.get("approval_id"),
        "scope": scope,
    }


def admit_workflow(
    root: Path,
    *,
    task_id: str,
    backend: str,
    required_capabilities: list[str],
    capability_health: dict[str, Any],
    workflow_run_id: str | None = None,
    trace_id: str | None = None,
    requested_budget: float = 0.0,
    remaining_budget: float | None = None,
    ttl_seconds: int = 900,
    now: str | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, Any]:
    """Validate gates, append request/admission events, and return a packet."""
    omo = root / Path(omo_dir)
    task_file = next(
        (
            path
            for path in (omo / "tasks" / "active").glob("*.yaml")
            if load_yaml(path).get("id") == task_id
        ),
        None,
    )
    if task_file is None:
        raise WorkflowDispatchError(f"active task not found: {task_id}")
    validation_errors = validate_task_file(task_file)
    if validation_errors:
        raise WorkflowDispatchError("; ".join(validation_errors))
    task = load_yaml(task_file)
    approval = _approval_state(root, task, task_file)
    health = _parse_health(
        capability_health, list(dict.fromkeys(required_capabilities))
    )
    if requested_budget < 0:
        raise WorkflowDispatchError("requested budget must be non-negative")
    if remaining_budget is not None and requested_budget > remaining_budget:
        raise WorkflowDispatchError("insufficient execution budget")

    issued_at = now or datetime.now(UTC).replace(microsecond=0).isoformat()
    run_id = workflow_run_id or f"mesh-{task_id.lower()}-{uuid4().hex[:12]}"
    trace = trace_id or run_id
    step_run_ids = [f"{run_id}:execute"]
    expires_at = (
        datetime.fromisoformat(issued_at) + timedelta(seconds=ttl_seconds)
    ).isoformat()
    policy = {
        "task_id": task_id,
        "backend": backend,
        "required_capabilities": list(dict.fromkeys(required_capabilities)),
        "approval": approval,
        "health": health["snapshot_digest"],
        "requested_budget": requested_budget,
    }
    grant = {
        "admission_id": f"admit-{uuid4().hex}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": trace,
        "backend": backend,
        "step_run_ids": step_run_ids,
        "capabilities": list(dict.fromkeys(required_capabilities)),
        "policy_digest": hashlib.sha256(_canonical(policy)).hexdigest(),
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    grant["proof"] = _proof(grant)

    store = WorkflowMeshStore(omo)
    store.append(
        new_workflow_event(
            "WorkflowRequested",
            run_id,
            trace_id=trace,
            producer="omo.workflow_dispatch",
            idempotency_key=f"{run_id}:requested",
            payload={
                "task_id": task_id,
                "backend": backend,
                "required_capabilities": grant["capabilities"],
                "approval": approval,
                "health": health,
                "requested_budget": requested_budget,
            },
        )
    )
    store.append(
        new_workflow_event(
            "WorkflowAdmitted",
            run_id,
            trace_id=trace,
            producer="omo.workflow_dispatch",
            idempotency_key=f"{run_id}:admitted",
            payload={"admission": grant, **grant, "task_id": task_id},
        )
    )
    return {
        "workflow_run_id": run_id,
        "trace_id": trace,
        "task_id": task_id,
        "backend": backend,
        "admission": grant,
        "approval": approval,
        "capability_health": health,
        "dispatch_state": "admitted",
    }


def dispatch_admitted_workflow(
    root: Path,
    *,
    task_id: str,
    worker_id: str,
    allowed_write_paths: list[str],
    backend: str,
    required_capabilities: list[str],
    capability_health: dict[str, Any],
    launch: bool = False,
    transport: str = "cli_prompt",
    **admission_options: Any,
) -> dict[str, Any]:
    """Admit first, then hand the immutable packet to the legacy worker bridge."""
    packet = admit_workflow(
        root,
        task_id=task_id,
        backend=backend,
        required_capabilities=required_capabilities,
        capability_health=capability_health,
        **admission_options,
    )
    from .omo_worker_dispatch import dispatch_task

    worker_dispatch = dispatch_task(
        root,
        task_id=task_id,
        worker_id=worker_id,
        allowed_write_paths=allowed_write_paths,
        launch=launch,
        transport=transport,
        workflow_packet=packet,
    )
    return {
        **packet,
        "worker_dispatch": worker_dispatch,
        "dispatch_state": "dispatched",
    }


__all__ = [
    "WorkflowDispatchError",
    "admit_workflow",
    "dispatch_admitted_workflow",
]
