from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from omo.workflow_eval import build_operations_snapshot
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event


def _grant(run_id: str) -> dict[str, object]:
    grant: dict[str, object] = {
        "admission_id": f"admit-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "runtime",
        "step_run_ids": [f"{run_id}:execute"],
        "capabilities": ["runtime"],
        "policy_digest": "policy-test",
        "issued_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    grant["proof"] = hashlib.sha256(
        json.dumps(grant, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return grant


def _admit(store: WorkflowMeshStore, run_id: str, *, scene: dict[str, str] | None) -> dict[str, object]:
    grant = _grant(run_id)
    store.append(new_workflow_event("WorkflowRequested", run_id, scene_binding=scene))
    store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
    return grant


def _start(store: WorkflowMeshStore, run_id: str, grant: dict[str, object]) -> None:
    payload = {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}
    store.append(new_workflow_event("StepDispatched", run_id, payload=payload))
    store.append(new_workflow_event("StepStarted", run_id, payload=payload))


def test_operations_snapshot_reports_milestones_review_queue_and_unknown_consumption(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    scene = {
        "scene_id": "engineering-delivery",
        "journey_id": "intent-to-evidence",
        "outcome_metric": "verified_delivery_lead_time",
    }

    success_run = "run-operations-success"
    grant = _admit(store, success_run, scene=scene)
    _start(store, success_run, grant)
    store.append(new_workflow_event("WorkflowSucceeded", success_run))
    store.append(
        new_workflow_event(
            "EvidenceRecorded",
            success_run,
            payload={"evidence_id": "evidence-1", "kind": "test-report"},
        )
    )
    store.append(new_workflow_event("WorkflowVerified", success_run))
    store.append(new_workflow_event("PRMerged", success_run))
    store.append(new_workflow_event("WorkflowClosed", success_run))

    failed_run = "run-operations-failed"
    _admit(store, failed_run, scene=scene)
    store.append(new_workflow_event("WorkflowFailed", failed_run))

    unbound_run = "run-operations-unbound"
    _admit(store, unbound_run, scene=None)
    store.append(new_workflow_event("WorkflowFailed", unbound_run))
    store.append(new_workflow_event("WorkflowClosed", unbound_run))

    recovered_run = "run-operations-recovered"
    recovered_grant = _admit(store, recovered_run, scene=scene)
    _start(store, recovered_run, recovered_grant)
    step_payload = {
        "step_run_id": f"{recovered_run}:execute",
        "admission_id": recovered_grant["admission_id"],
    }
    store.append(new_workflow_event("StepFailed", recovered_run, payload=step_payload))
    store.append(new_workflow_event("WorkflowRecovered", recovered_run))
    store.append(new_workflow_event("WorkflowSucceeded", recovered_run))

    unavailable_run = "run-operations-unavailable"
    _admit(store, unavailable_run, scene=scene)
    store.append(new_workflow_event("BackendUnavailable", unavailable_run))
    store.append(new_workflow_event("WorkflowClosed", unavailable_run))

    projection = build_operations_snapshot(tmp_path)

    assert projection["schema_version"] == "workflow-mesh-operations/v1"
    assert projection["summary"]["run_count"] == 5
    assert projection["summary"]["succeeded_runs"] == 2
    assert projection["summary"]["verified_runs"] == 1
    assert projection["summary"]["merged_runs"] == 1
    assert projection["summary"]["closed_runs"] == 3
    assert projection["summary"]["failed_runs"] == 3
    assert projection["summary"]["unavailable_runs"] == 1
    assert projection["summary"]["recovered_runs"] == 1
    assert projection["summary"]["rates"]["verification_rate_among_succeeded"] == 0.5
    assert projection["consumption"]["status"] == "not_observed"
    assert projection["consumption"]["consumed_runs"] == 0
    assert {item["category"] for item in projection["review_queue"]} == {
        "recovery",
        "verification",
        "evidence",
        "attribution",
    }

    filtered = build_operations_snapshot(tmp_path, scene_id="engineering-delivery")
    assert filtered["summary"]["run_count"] == 4
    assert all(
        item["scene_binding"]["scene_id"] == "engineering-delivery"
        for item in filtered["by_scene"]
    )
