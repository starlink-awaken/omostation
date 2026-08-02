"""Agent Workflow Mesh event helpers - Phase 1b/4 bridge.

Makes Agent Workflow lifecycle events visible to Workflow Mesh.
Events are emitted to OMO's Workflow Mesh store by default.

Uses standard Workflow Mesh event types (WorkflowRequested, WorkflowClosed)
to remain compatible with the Mesh state machine and projection.

Phase 4: Supports scene_binding injection so WorkflowRequested events carry
business scene context from the External Connection Fabric.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _run_mesh_sink(workspace: Path | str | None = None) -> Any | None:
    """Lazy load Workflow Mesh store - breaks circular import."""
    try:
        from omo.workflow_mesh import WorkflowMeshStore
        ws = Path(workspace) if workspace else Path.cwd()
        omo_dir = ws / ".omo"
        (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)
        return WorkflowMeshStore(omo_dir)
    except Exception:
        return None


def emit_workflow_mesh_event(
    event_type: str,
    run_id: str,
    payload: dict[str, Any] | None = None,
    workspace: Path | str | None = None,
    scene_binding: dict[str, str] | None = None,
) -> bool:
    """Emit a Workflow Mesh event. Returns True on success, False on silent failure.

    Uses standard Mesh event types so events are accepted by the Mesh state machine:
    - Agent workflow "start" -> WorkflowRequested
    - Agent workflow "closeout" -> WorkflowClosed

    Phase 4: If scene_binding is provided, it is injected into the payload so
    the Mesh can correlate the execution with a business scene.

    Silently returns False if OMO Mesh is not available.
    """
    sink = _run_mesh_sink(workspace)
    if sink is None:
        return False

    mesh_event_type = {
        "AgentWorkflowStarted": "WorkflowRequested",
        "AgentWorkflowClosed": "WorkflowClosed",
    }.get(event_type, event_type)

    try:
        event_payload = {
            "agent_event_type": event_type,
            **(payload or {}),
        }
        if scene_binding:
            event_payload["scene_binding"] = scene_binding

        event = {
            "event_id": uuid4().hex,
            "event_type": mesh_event_type,
            "workflow_run_id": run_id,
            "trace_id": run_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "producer": "agent-workflow",
            "schema_version": "workflow-mesh/v1",
            "idempotency_key": f"{run_id}:{event_type}",
            "payload": event_payload,
        }
        sink.append(event)
        return True
    except Exception:
        return False
