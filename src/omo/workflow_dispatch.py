"""Workflow Mesh admission and worker dispatch bridge.

This module owns the control-plane decision only. It does not execute a worker
or call a backend. A successful result is a signed admission grant plus an
immutable dispatch packet recorded in OMO's append-only event log.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
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
    root: Path,
    task: dict[str, Any],
    task_file: Path,
    *,
    accepted_task_refs: set[str] | None = None,
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
    valid_task_refs = {task_ref, str(approval_ref), *(accepted_task_refs or set())}
    if refs.get("task_ref") not in valid_task_refs:
        raise WorkflowDispatchError("approval record task reference mismatch")
    return {
        "required": True,
        "status": "granted",
        "ref": str(approval_ref),
        "approval_id": approval.get("approval_id"),
        "scope": scope,
    }


def _requested_event(store: WorkflowMeshStore, workflow_run_id: str) -> dict[str, Any]:
    for event in store.events():
        if (
            str(event.get("workflow_run_id")) == workflow_run_id
            and event.get("event_type") == "WorkflowRequested"
        ):
            return event
    raise WorkflowDispatchError(f"workflow request not found: {workflow_run_id}")


def _task_file_for_request(
    root: Path,
    task_id: str,
    *,
    groups: tuple[str, ...],
    omo_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    omo = root / Path(omo_dir)
    for group in groups:
        for path in (omo / "tasks" / group).glob("*.yaml"):
            try:
                payload = load_yaml(path)
            except (OSError, ValueError):
                continue
            if payload.get("id") == task_id:
                return path, payload
    raise WorkflowDispatchError(f"task not found for workflow request: {task_id}")


def _request_context(
    root: Path,
    workflow_run_id: str,
    *,
    omo_dir: str | Path,
) -> tuple[WorkflowMeshStore, dict[str, Any], dict[str, Any]]:
    store = WorkflowMeshStore(root / Path(omo_dir))
    event = _requested_event(store, workflow_run_id)
    snapshot = store.snapshot(workflow_run_id)
    if snapshot.get("state") == "closed":
        raise WorkflowDispatchError("workflow request is already closed")
    payload = event.get("payload")
    if not isinstance(payload, dict) or not payload.get("task_id"):
        raise WorkflowDispatchError("workflow request has no task binding")
    return store, event, snapshot


def _validate_admission_inputs(
    *,
    backend: str,
    required_capabilities: list[str],
    requested_budget: float,
    remaining_budget: float | None,
) -> list[str]:
    if not str(backend).strip():
        raise WorkflowDispatchError("backend is required")
    required = list(dict.fromkeys(str(item).strip() for item in required_capabilities))
    if not required or any(not item for item in required):
        raise WorkflowDispatchError("required capabilities must not be empty")
    if requested_budget < 0:
        raise WorkflowDispatchError("requested budget must be non-negative")
    if remaining_budget is not None and requested_budget > remaining_budget:
        raise WorkflowDispatchError("insufficient execution budget")
    return required


def _check_scene_binding(
    event: dict[str, Any], scene_binding: Mapping[str, Any] | None
) -> None:
    if scene_binding is None:
        return
    payload = event.get("payload")
    recorded = payload.get("scene_binding") if isinstance(payload, dict) else None
    if dict(scene_binding) != recorded:
        raise WorkflowDispatchError("scene binding does not match workflow request")


def _build_admission_grant(
    *,
    workflow_run_id: str,
    trace_id: str,
    task_id: str,
    backend: str,
    required_capabilities: list[str],
    approval: dict[str, Any],
    health: dict[str, Any],
    requested_budget: float,
    ttl_seconds: int,
    now: str | None,
) -> dict[str, Any]:
    issued_at = now or datetime.now(UTC).replace(microsecond=0).isoformat()
    if ttl_seconds <= 0:
        raise WorkflowDispatchError("admission ttl must be positive")
    expires_at = (
        datetime.fromisoformat(issued_at) + timedelta(seconds=ttl_seconds)
    ).isoformat()
    policy = {
        "task_id": task_id,
        "backend": backend,
        "required_capabilities": required_capabilities,
        "approval": approval,
        "health": health["snapshot_digest"],
        "requested_budget": requested_budget,
    }
    grant = {
        "admission_id": f"admit-{uuid4().hex}",
        "status": "admitted",
        "workflow_run_id": workflow_run_id,
        "trace_id": trace_id,
        "backend": backend,
        "step_run_ids": [f"{workflow_run_id}:execute"],
        "capabilities": required_capabilities,
        "policy_digest": hashlib.sha256(_canonical(policy)).hexdigest(),
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    grant["proof"] = _proof(grant)
    return grant


def preview_requested_workflow(
    root: Path,
    *,
    workflow_run_id: str,
    backend: str,
    required_capabilities: list[str],
    capability_health: dict[str, Any],
    requested_budget: float = 0.0,
    remaining_budget: float | None = None,
    scene_binding: Mapping[str, Any] | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, Any]:
    """Evaluate admission gates for an existing request without writing state."""
    _store, event, snapshot = _request_context(root, workflow_run_id, omo_dir=omo_dir)
    _check_scene_binding(event, scene_binding)
    if snapshot.get("state") == "admitted":
        return {
            "status": "deduplicated",
            "dispatch_state": "admitted",
            "workflow_run_id": workflow_run_id,
            "external_side_effects": "disabled",
            "worker_launch": False,
            "admission": snapshot.get("admission"),
        }
    if snapshot.get("state") != "planned":
        return {
            "status": "blocked",
            "blocker": "workflow request is not awaiting admission",
            "workflow_run_id": workflow_run_id,
            "current_state": snapshot.get("state"),
            "external_side_effects": "disabled",
            "worker_launch": False,
        }

    required = _validate_admission_inputs(
        backend=backend,
        required_capabilities=required_capabilities,
        requested_budget=requested_budget,
        remaining_budget=remaining_budget,
    )
    task_id = str(event["payload"]["task_id"])
    task_file, task = _task_file_for_request(
        root, task_id, groups=("active", "planned"), omo_dir=omo_dir
    )
    validation_errors = validate_task_file(task_file)
    if validation_errors:
        raise WorkflowDispatchError("; ".join(validation_errors))
    request_task_ref = str(event.get("payload", {}).get("task_ref") or "")
    try:
        approval = _approval_state(
            root,
            task,
            task_file,
            accepted_task_refs={request_task_ref} if request_task_ref else set(),
        )
        health = _parse_health(capability_health, required)
    except WorkflowDispatchError as exc:
        return {
            "status": "blocked",
            "blocker": str(exc),
            "workflow_run_id": workflow_run_id,
            "task_id": task_id,
            "task_group": task_file.parent.name,
            "current_state": "planned",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "status": "eligible",
        "dispatch_state": "preview",
        "workflow_run_id": workflow_run_id,
        "trace_id": event.get("trace_id", workflow_run_id),
        "task_id": task_id,
        "task_group": task_file.parent.name,
        "backend": backend,
        "required_capabilities": required,
        "approval": approval,
        "capability_health": health,
        "requested_budget": requested_budget,
        "scene_binding": event.get("payload", {}).get("scene_binding"),
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


def admit_requested_workflow(
    root: Path,
    *,
    workflow_run_id: str,
    backend: str,
    required_capabilities: list[str],
    capability_health: dict[str, Any],
    requested_budget: float = 0.0,
    remaining_budget: float | None = None,
    ttl_seconds: int = 900,
    now: str | None = None,
    scene_binding: Mapping[str, Any] | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, Any]:
    """Admit only an existing request; never create an implicit request."""
    store, event, snapshot = _request_context(root, workflow_run_id, omo_dir=omo_dir)
    _check_scene_binding(event, scene_binding)
    if snapshot.get("state") == "admitted":
        return {
            "status": "deduplicated",
            "dispatch_state": "admitted",
            "workflow_run_id": workflow_run_id,
            "trace_id": snapshot.get("trace_id", workflow_run_id),
            "task_id": event.get("payload", {}).get("task_id"),
            "admission": snapshot.get("admission"),
            "scene_binding": snapshot.get("scene_binding"),
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    if snapshot.get("state") != "planned":
        raise WorkflowDispatchError(
            f"workflow request cannot be admitted from state: {snapshot.get('state')}"
        )
    required = _validate_admission_inputs(
        backend=backend,
        required_capabilities=required_capabilities,
        requested_budget=requested_budget,
        remaining_budget=remaining_budget,
    )
    task_id = str(event["payload"]["task_id"])
    try:
        task_file, task = _task_file_for_request(
            root, task_id, groups=("active",), omo_dir=omo_dir
        )
    except WorkflowDispatchError as exc:
        try:
            _task_file_for_request(root, task_id, groups=("planned",), omo_dir=omo_dir)
        except WorkflowDispatchError:
            raise exc
        raise WorkflowDispatchError("active task is required before admission") from exc
    validation_errors = validate_task_file(task_file)
    if validation_errors:
        raise WorkflowDispatchError("; ".join(validation_errors))
    request_task_ref = str(event.get("payload", {}).get("task_ref") or "")
    approval = _approval_state(
        root,
        task,
        task_file,
        accepted_task_refs={request_task_ref} if request_task_ref else set(),
    )
    health = _parse_health(capability_health, required)
    trace_id = str(event.get("trace_id") or workflow_run_id)
    grant = _build_admission_grant(
        workflow_run_id=workflow_run_id,
        trace_id=trace_id,
        task_id=task_id,
        backend=backend,
        required_capabilities=required,
        approval=approval,
        health=health,
        requested_budget=requested_budget,
        ttl_seconds=ttl_seconds,
        now=now,
    )
    admitted = store.append(
        new_workflow_event(
            "WorkflowAdmitted",
            workflow_run_id,
            trace_id=trace_id,
            producer="omo.workflow_dispatch",
            idempotency_key=f"{workflow_run_id}:admitted",
            payload={
                "admission": grant,
                **grant,
                "task_id": task_id,
                "backend": backend,
                "required_capabilities": required,
                "capability_health": health,
                "requested_budget": requested_budget,
                "external_side_effects": "disabled",
            },
        )
    )
    return {
        "status": "admitted",
        "dispatch_state": "admitted",
        "workflow_run_id": workflow_run_id,
        "trace_id": trace_id,
        "task_id": task_id,
        "backend": backend,
        "admission": grant,
        "approval": approval,
        "capability_health": health,
        "scene_binding": event.get("payload", {}).get("scene_binding"),
        "event": {
            "event_id": admitted["event_id"],
            "event_type": admitted["event_type"],
            "idempotency_key": admitted["idempotency_key"],
        },
        "external_side_effects": "disabled",
        "worker_launch": False,
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
    scene_binding: Mapping[str, Any] | None = None,
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
            scene_binding=scene_binding,
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
        "scene_binding": dict(scene_binding) if scene_binding is not None else None,
        "dispatch_state": "admitted",
    }


def _dispatch_iris_via_executor(
    root: Path,
    packet: dict[str, Any],
    iris_caps: list[str],
    omo_dir: str | Path = ".omo",
) -> dict[str, Any]:
    """P0 完整第一块: iris capability → mesh-iris-executor 快速路径.

    capability_refs 含 ``iris:xxx`` → subprocess 调 mesh-iris-executor (新 run_id, 自 seed).
    admission gate (admit_workflow) 已验证 iris capability 可用; executor 执行
    list_items + record receipt (mesh 6 事件链 + EvidenceRecorded).
    """
    import subprocess

    executor = root / "bin" / "ssot" / "mesh-iris-executor.py"
    if not executor.exists():
        raise WorkflowDispatchError(f"mesh-iris-executor not found: {executor}")

    results: list[dict[str, Any]] = []
    for cap in iris_caps:
        connector = cap[len("iris:") :]
        proc = subprocess.run(
            [
                "python3",
                str(executor),
                "--connector",
                connector,
                "--omo-dir",
                str(omo_dir),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        results.append(
            {
                "capability": cap,
                "connector": connector,
                "returncode": proc.returncode,
                "tail": (proc.stdout or "")[-400:],
                "stderr_tail": (proc.stderr or "")[-200:],
            }
        )
    all_ok = all(r["returncode"] == 0 for r in results)
    return {
        **packet,
        "iris_dispatch": results,
        "dispatch_state": "dispatched" if all_ok else "failed",
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
    # P0 完整第一块: iris capability → mesh-iris-executor 快速路径 (不 launch agent).
    # admission gate 已验证 iris capability 可用, 直接调 executor 执行 + record receipt.
    iris_caps = [c for c in required_capabilities if str(c).startswith("iris:")]
    if iris_caps:
        return _dispatch_iris_via_executor(root, packet, iris_caps)

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
    "admit_requested_workflow",
    "admit_workflow",
    "dispatch_admitted_workflow",
    "preview_requested_workflow",
]
