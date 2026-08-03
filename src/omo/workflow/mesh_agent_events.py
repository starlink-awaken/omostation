"""Agent Workflow Mesh event helpers - Phase 1b/4/5 bridge.

Makes Agent Workflow lifecycle events visible to Workflow Mesh.
Events are emitted to OMO's Workflow Mesh store by default.

Uses standard Workflow Mesh event types to remain compatible with the Mesh
state machine and projection.

Phase 1b: WorkflowRequested on start, WorkflowClosed on closeout.
Phase 4:  scene_binding injection into WorkflowRequested payload.
Phase 5:  Event chain closure -- emits intermediate admission + dispatch +
          running + terminal events before WorkflowClosed so the Mesh state
          machine accepts the full transition chain.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("omo.workflow.mesh_agent_events")


def _run_mesh_sink(workspace: Any | None = None) -> Any | None:
    """Lazy load Workflow Mesh store - breaks circular import."""
    try:
        from omo.workflow_mesh import WorkflowMeshStore
        ws = Path(workspace) if workspace else Path.cwd()
        omo_dir = ws / ".omo"
        (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)
        return WorkflowMeshStore(omo_dir)
    except Exception:
        return None


def _make_event(
    mesh_event_type: str,
    run_id: str,
    payload: dict[str, Any],
    *,
    suffix: str = "",
) -> dict[str, Any]:
    """Build a standard Mesh event envelope."""
    idem = f"{run_id}:{mesh_event_type}"
    if suffix:
        idem = f"{idem}:{suffix}"
    return {
        "event_id": uuid4().hex,
        "event_type": mesh_event_type,
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": "agent-workflow",
        "schema_version": "workflow-mesh/v1",
        "idempotency_key": idem,
        "payload": payload,
    }


def _try_append(sink: Any, event: dict[str, Any]) -> bool:
    """Append event to sink, return True on success, False on failure."""
    try:
        sink.append(event)
        return True
    except Exception as exc:
        logger.debug("Mesh event append failed (%s): %s", event.get("event_type"), exc)
        return False


def _emit_admission_chain(
    sink: Any,
    run_id: str,
    payload: dict[str, Any],
) -> tuple[str, str]:
    """Emit WorkflowAdmitted + StepDispatched + StepStarted.

    Transitions: planned -> admitted -> dispatched -> running.
    Returns (step_run_id, admission_id) used.

    Best-effort: if the run is already past these states, appends are
    silently skipped by _try_append.
    """
    now = datetime.now(UTC)
    step_run_id = f"{run_id}:execute"
    admission_id = f"agent-{uuid4().hex[:12]}"
    expires_at = (now + timedelta(seconds=3600)).isoformat()

    grant = {
        "admission_id": admission_id,
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "agent-workflow",
        "step_run_ids": [step_run_id],
        "capabilities": [],
        "policy_digest": hashlib.sha256(
            f"{run_id}:agent-workflow".encode()
        ).hexdigest(),
        "issued_at": now.isoformat(),
        "expires_at": expires_at,
    }
    unsigned = {k: v for k, v in grant.items() if k != "proof"}
    grant["proof"] = hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # planned -> admitted
    admitted_payload = {**payload, **grant, "admission": grant}
    _try_append(sink, _make_event("WorkflowAdmitted", run_id, admitted_payload))

    # admitted -> dispatched
    dispatch_payload = {
        **payload,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "step_name": "execute",
        "dispatch_id": f"agent-{uuid4().hex[:8]}",
        "worker_id": "agent-workflow",
    }
    _try_append(sink, _make_event("StepDispatched", run_id, dispatch_payload))

    # dispatched -> running
    started_payload = {
        **payload,
        "step_run_id": step_run_id,
        "admission_id": admission_id,
        "step_name": "execute",
    }
    _try_append(sink, _make_event("StepStarted", run_id, started_payload))

    return step_run_id, admission_id


def emit_workflow_mesh_event(
    event_type: str,
    run_id: str,
    payload: dict[str, Any] | None = None,
    workspace: Any | None = None,
    scene_binding: dict[str, str] | None = None,
) -> bool:
    """Emit a Workflow Mesh event. Returns True on success, False on silent failure.

    Maps agent workflow lifecycle events to Mesh event types and ensures the
    state machine transition chain is valid:

    - AgentWorkflowStarted -> WorkflowRequested
    - AgentWorkflowClosed   -> full chain: planned -> admitted -> dispatched
                               -> running -> terminal (succeeded via
                               WorkflowSucceeded, failed via StepFailed,
                               cancelled via WorkflowCancelled) -> closed.

    Phase 4: If scene_binding is provided, it is injected into the
    WorkflowRequested payload so the Mesh can correlate the execution
    with a business scene.

    Silently returns False if OMO Mesh is not available.
    """
    sink = _run_mesh_sink(workspace)
    if sink is None:
        return False

    event_payload = {
        "agent_event_type": event_type,
        **(payload or {}),
    }
    if scene_binding:
        event_payload["scene_binding"] = scene_binding

    if event_type == "AgentWorkflowStarted":
        event = _make_event("WorkflowRequested", run_id, event_payload)
        return _try_append(sink, event)

    if event_type == "AgentWorkflowClosed":
        # Phase 5: Emit intermediate events so the state machine transition
        # chain is valid.
        status = (payload or {}).get("status", "")
        ok = (payload or {}).get("ok", False)

        if status == "cancelled":
            # cancelled can go directly from planned (no admission needed)
            _try_append(sink, _make_event("WorkflowCancelled", run_id, event_payload))
        else:
            # Transition: planned -> admitted -> dispatched -> running
            step_run_id, admission_id = _emit_admission_chain(sink, run_id, event_payload)

            # Transition: running -> terminal
            if ok or status in ("succeeded", "verified", "merged"):
                _try_append(sink, _make_event("WorkflowSucceeded", run_id, event_payload))
            else:
                # StepFailed transitions running -> failed
                fail_payload = {
                    **event_payload,
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "step_name": "execute",
                    "error": (payload or {}).get("error", "workflow failed"),
                }
                _try_append(sink, _make_event("StepFailed", run_id, fail_payload))

        # Transition: terminal -> closed
        close_event = _make_event("WorkflowClosed", run_id, event_payload)
        return _try_append(sink, close_event)

    # Pass-through for other event types
    event = _make_event(event_type, run_id, event_payload)
    return _try_append(sink, event)
