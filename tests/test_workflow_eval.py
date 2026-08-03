from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from omo.omo_external_evaluation import record_external_resource_evaluation
from omo.omo_external_receipt import record_external_receipt
from omo.outcome_feedback import record_outcome_feedback
from omo.workflow_eval import (
    build_eval_dataset,
    build_evaluation_sample_readiness,
    build_external_resource_selection_dataset,
    build_operations_snapshot,
    build_request_eval_dataset,
    evaluate_policy,
    evaluate_selection_policy,
    propose_policy_feedback,
    propose_selection_policy_feedback,
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


def _selection_scene() -> dict[str, str]:
    return {
        "scene_id": "research-brief",
        "journey_id": "weekly-decision",
        "outcome_metric": "decision_latency_hours",
        "data_scope": "public:research",
        "operator": "human:test",
        "permission_ref": "permission://test",
    }


def _selection_evaluation(trace_id: str) -> dict[str, object]:
    return {
        "schema": "external-resource-evaluation/v1",
        "mode": "read_only_evaluation",
        "activation": "forbidden",
        "capability": "search",
        "trace_id": trace_id,
        "policy_digest": "external-connection-fabric/v1",
        "scene_binding": _selection_scene(),
        "status": "selected",
        "selected_resource_id": "source:test",
        "candidates": [
            {
                "resource_id": "source:test",
                "capability": "search",
                "status": "eligible",
                "reasons": [],
                "decision_factors": {"health": "healthy", "freshness": 0.9},
                "rank": [1, 0.9, "source:test"],
                "availability": "available",
                "provenance_ref": "evidence://source/test",
            }
        ],
        "reasons": [],
    }


def _selection_run(tmp_path, run_id: str = "run-selection-1") -> WorkflowMeshStore:
    store = WorkflowMeshStore(tmp_path)
    grant = _grant(run_id)
    store.append(new_workflow_event("WorkflowRequested", run_id, trace_id=run_id, scene_binding=_selection_scene()))
    store.append(new_workflow_event("WorkflowAdmitted", run_id, trace_id=run_id, payload={"admission": grant, **grant}))
    context = {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}
    store.append(new_workflow_event("StepDispatched", run_id, trace_id=run_id, payload=context))
    store.append(new_workflow_event("StepStarted", run_id, trace_id=run_id, payload=context))
    store.append(new_workflow_event("WorkflowSucceeded", run_id, trace_id=run_id))
    return store


def test_selection_dataset_joins_event_receipt_and_feedback_without_promoting_unbound(tmp_path):
    _selection_run(tmp_path)
    record_external_resource_evaluation(
        tmp_path, _selection_evaluation("run-selection-1"), workflow_run_id="run-selection-1"
    )
    record_external_receipt(
        tmp_path,
        {
            "receipt_id": "receipt-selection-1",
            "trace_id": "run-selection-1",
            "resource_id": "source:test",
            "operation": "search",
            "result_state": "succeeded",
            "observed_at": "2026-08-03T10:00:00Z",
            "provenance_ref": "evidence://source/test",
            "policy_digest": "external-connection-fabric/v1",
            "decision_factors": {"health": "healthy"},
            "output_digest": "a" * 64,
        },
        workflow_run_id="run-selection-1",
    )
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowVerified", "run-selection-1", trace_id="run-selection-1"))
    store.append(new_workflow_event("PRMerged", "run-selection-1", trace_id="run-selection-1"))
    store.append(new_workflow_event("WorkflowClosed", "run-selection-1", trace_id="run-selection-1"))
    record_outcome_feedback(
        tmp_path,
        {
            "workflow_run_id": "run-selection-1",
            "outcome_id": "outcome:research-brief:1",
            "scene_binding": _selection_scene() | {"data_scope": "public:research", "operator": "human:test", "permission_ref": "permission://test"},
            "consumption_state": "adopted",
            "consumer_ref": "operator://test",
            "result_ref": "evidence://outcome/1",
            "evidence_refs": [],
            "value": {"amount": 1, "unit": "brief"},
            "observed_at": "2026-08-03T10:05:00Z",
        },
    )

    unbound = _selection_evaluation("trace:unbound")
    unbound["selected_resource_id"] = None
    unbound["status"] = "unavailable"
    record_external_resource_evaluation(tmp_path, unbound)

    dataset = build_external_resource_selection_dataset(tmp_path)
    assert dataset["dataset_version"] == "external-resource-selection-eval/v1"
    assert dataset["summary"]["row_count"] == 2
    linked = next(row for row in dataset["rows"] if row["workflow_run_id"] == "run-selection-1")
    assert linked["labels"]["execution_outcome"] == "success"
    assert linked["labels"]["selection_alignment"] == "aligned"
    assert linked["labels"]["consumption_state"] == "adopted"
    assert linked["labels"]["label_quality"] == "execution_and_consumption"
    assert linked["label_source"]["receipt_ids"] == ["receipt-selection-1"]
    unexecuted = next(row for row in dataset["rows"] if row["workflow_run_id"] is None)
    assert unexecuted["labels"]["execution_outcome"] == "not_executed"
    assert unexecuted["labels"]["selection_alignment"] == "not_executed"

    policy = evaluate_selection_policy(dataset, {"max_unaligned_rate": 0.2})
    proposal = propose_selection_policy_feedback(
        dataset, {"max_unaligned_rate": 0.2}, proposal_id="selection-proposal-1"
    )
    assert policy["not_applied"] is True
    assert policy["success_rate"] == 1.0
    assert proposal["status"] == "proposal_only"
    assert proposal["requires_human_approval"] is True


def test_evaluation_sample_readiness_distinguishes_execution_from_full_label():
    dataset = {
        "dataset_version": "external-resource-selection-eval/v1",
        "rows": [
            {
                "evaluation_id": "eval-ready",
                "workflow_run_id": "run-ready",
                "scene_binding": {"scene_id": "scene"},
                "join": {"status": "explicit", "receipt_count": 1},
                "labels": {
                    "execution_outcome": "success",
                    "selection_alignment": "aligned",
                    "consumption_state": "adopted",
                    "label_quality": "execution_and_consumption",
                },
            },
            {
                "evaluation_id": "eval-gap",
                "workflow_run_id": "run-gap",
                "scene_binding": {"scene_id": "scene"},
                "join": {"status": "explicit", "receipt_count": 0},
                "labels": {
                    "execution_outcome": "success",
                    "selection_alignment": "missing_receipt",
                    "consumption_state": "unobserved",
                    "label_quality": "execution",
                },
            },
        ],
    }

    readiness = build_evaluation_sample_readiness(dataset)

    assert readiness["schema_version"] == "workflow-mesh-evaluation-readiness/v1"
    assert readiness["summary"] == {
        "row_count": 2,
        "ready_count": 1,
        "execution_ready_count": 1,
        "blocked_count": 1,
        "blockers": {
            "consumption_feedback_missing": 1,
            "external_receipt_not_aligned": 1,
        },
    }
    assert readiness["rows"][0]["status"] == "ready"
    assert readiness["rows"][1]["status"] == "blocked"
