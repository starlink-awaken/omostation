from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from omo.omo_ingress_task_lifecycle import (
    complete_task,
    create_planned_task,
    promote_task_to_active,
    record_task_execution,
)
from omo.worker_lifecycle import acknowledge_worker
from omo.workflow_dispatch import dispatch_admitted_workflow
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event


def _task() -> dict[str, object]:
    return {
        "id": "TASK-DOGFOOD-1",
        "title": "Workflow Mesh engineering dogfood",
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L1",
        "depends_on": [],
        "source_docs": ["docs/WORKFLOW-MESH-IMPLEMENTATION.md"],
        "deliverables": ["runtime/omo/dogfood.log"],
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "entry_gate": [],
        "evidence_required": ["runtime/omo/dogfood.log"],
        "test_plan": ["pytest projects/omo/tests/test_workflow_mesh_task_dogfood.py"],
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "metadata": {"command": "printf workflow-mesh-dogfood"},
    }


def _worker_registry(root: Path) -> None:
    registry = root / ".omo" / "_truth" / "registry" / "workers.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump(
            {
                "workers": [
                    {
                        "id": "worker-dogfood",
                        "enabled": True,
                        "transports": {"cli_prompt": {"command": "worker-dogfood"}},
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_task_and_workflow_mesh_closeout_converge_with_scene_binding(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    _worker_registry(tmp_path)

    create_planned_task(
        omo_dir,
        task_data=_task(),
        ingress_plane="projects/omo/tests",
        source_ref="dogfood:task:TASK-DOGFOOD-1",
        now="2026-08-02T12:00:00Z",
    )
    promote_task_to_active(
        omo_dir,
        task_id="TASK-DOGFOOD-1",
        actor="dogfood-coordinator",
        source_ref="dogfood:promote:TASK-DOGFOOD-1",
        now="2026-08-02T12:01:00Z",
    )

    scene_binding = {
        "scene_id": "engineering-delivery",
        "journey_id": "task-to-pr-closeout",
        "outcome_metric": "verified_delivery",
    }
    packet = dispatch_admitted_workflow(
        tmp_path,
        task_id="TASK-DOGFOOD-1",
        worker_id="worker-dogfood",
        allowed_write_paths=["runtime/omo/"],
        backend="runtime",
        required_capabilities=["workflow.execute", "runtime"],
        capability_health={
            "status": "healthy",
            "source": "dogfood",
            "observed_at": datetime.now(UTC).isoformat(),
            "capabilities": {
                "workflow.execute": {"available": True, "health": "green"},
                "runtime": {"available": True, "health": "green"},
            },
        },
        workflow_run_id="run-task-dogfood-1",
        scene_binding=scene_binding,
        now="2026-08-02T12:02:00+00:00",
    )

    grant = packet["admission"]
    dispatch = packet["worker_dispatch"]
    step_run_id = grant["step_run_ids"][0]
    acknowledge_worker(
        omo_dir,
        workflow_run_id=packet["workflow_run_id"],
        trace_id=packet["trace_id"],
        dispatch_id=dispatch["dispatch_id"],
        worker_id="worker-dogfood",
        step_run_id=step_run_id,
        admission_id=grant["admission_id"],
        now="2026-08-02T12:02:05Z",
    )

    store = WorkflowMeshStore(omo_dir)
    store.append(
        new_workflow_event(
            "StepStarted",
            packet["workflow_run_id"],
            trace_id=packet["trace_id"],
            payload={
                "step_run_id": step_run_id,
                "step_name": "execute",
                "admission_id": grant["admission_id"],
            },
        )
    )

    log_path = tmp_path / "runtime" / "omo" / "dogfood.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("workflow-mesh-dogfood: ok\n", encoding="utf-8")
    record_task_execution(
        omo_dir,
        task_id="TASK-DOGFOOD-1",
        actor="worker-dogfood",
        command="printf workflow-mesh-dogfood",
        exit_code=0,
        log_ref="runtime/omo/dogfood.log",
        source_ref="dogfood:execution:TASK-DOGFOOD-1",
        now="2026-08-02T12:02:10Z",
    )
    complete_task(
        omo_dir,
        task_id="TASK-DOGFOOD-1",
        actor="dogfood-coordinator",
        source_ref="dogfood:complete:TASK-DOGFOOD-1",
        evidence_paths=["runtime/omo/dogfood.log"],
        now="2026-08-02T12:02:20Z",
    )

    for event_type, payload in (
        ("WorkflowSucceeded", {"step_run_id": step_run_id}),
        (
            "EvidenceRecorded",
            {
                "evidence_id": "evidence-task-dogfood-1",
                "kind": "task-execution-log",
                "uri": "runtime/omo/dogfood.log",
                "sha256": "dogfood-log",
            },
        ),
        ("WorkflowVerified", {"verification": "task-and-mesh-converged"}),
        ("WorkflowClosed", {"closeout": "dogfood"}),
    ):
        store.append(
            new_workflow_event(
                event_type,
                packet["workflow_run_id"],
                trace_id=packet["trace_id"],
                payload=payload,
            )
        )

    task_path = omo_dir / "tasks" / "done" / "TASK-DOGFOOD-1.yaml"
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    snapshot = store.snapshot(packet["workflow_run_id"])

    assert task["status"] == "done"
    assert task["metadata"]["execution_audit"]["exit_code"] == 0
    assert task["evidence_paths"] == ["runtime/omo/dogfood.log"]
    assert snapshot["state"] == "closed"
    assert snapshot["scene_binding"] == scene_binding
    assert snapshot["worker"]["worker_id"] == "worker-dogfood"
    assert "evidence-task-dogfood-1" in snapshot["evidence"]
    assert snapshot["last_event_type"] == "WorkflowClosed"
