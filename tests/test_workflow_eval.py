from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from omo.workflow_eval import (
    build_eval_dataset,
    build_operations_snapshot,
    build_request_eval_dataset,
    evaluate_policy,
    propose_policy_feedback,
)
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event


def _grant(run_id: str) -> dict:
    grant = {
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


def test_build_eval_dataset_uses_real_event_labels(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    run_id = "run-eval-1"
    grant = _grant(run_id)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    for event_type, payload in (
        ("StepDispatched", {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}),
        ("StepStarted", {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}),
        ("WorkflowSucceeded", {}),
    ):
        store.append(new_workflow_event(event_type, run_id, payload=payload))

    dataset = build_eval_dataset(tmp_path)
    assert dataset["dataset_version"] == "workflow-mesh-eval/v1"
    assert dataset["summary"]["row_count"] == 1
    row = dataset["rows"][0]
    assert row["labels"]["outcome"] == "success"
    assert row["label_source"]["event_ids"]
    assert row["label_source"]["labeling_rule"] == "workflow-mesh-eval/v1:event-derived"


def test_policy_feedback_is_offline_and_requires_approval(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    run_id = "run-policy-1"
    grant = _grant(run_id)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
    store.append(new_workflow_event("WorkflowFailed", run_id))
    dataset = build_eval_dataset(tmp_path)
    evaluation = evaluate_policy(dataset, {"require_admission": True})
    proposal = propose_policy_feedback(
        dataset, {"require_admission": True}, proposal_id="policy-proposal-1"
    )
    assert evaluation["not_applied"] is True
    assert proposal["status"] == "proposal_only"
    assert proposal["requires_human_approval"] is True


def test_request_eval_dataset_includes_pending_request_and_operations_funnel(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    run_id = "run-request-pending"
    store.append(
        new_workflow_event(
            "WorkflowRequested",
            run_id,
            scene_binding={
                "scene_id": "engineering-delivery",
                "journey_id": "knowledge-to-action",
                "outcome_metric": "task_adoption_rate",
            },
            payload={
                "task_id": "task-1",
                "workflow": {"name": "knowledge-to-action", "version": "v1"},
                "operation_level": "L1",
                "approval_required": True,
                "evidence_plan": ["result summary"],
                "knowledge_ref_digest": "sha256:test",
                "requested_at": "2026-08-03T10:00:00+00:00",
            },
        )
    )

    dataset = build_request_eval_dataset(tmp_path)
    operations = build_operations_snapshot(tmp_path)

    assert dataset["dataset_version"] == "workflow-request-eval/v1"
    assert dataset["summary"]["row_count"] == 1
    assert dataset["rows"][0]["labels"]["gate_outcome"] == "pending_admission"
    assert dataset["rows"][0]["label_source"]["event_ids"]
    assert operations["workflow_requests"]["pending_count"] == 1
    assert operations["workflow_requests"]["approval_required_count"] == 1
