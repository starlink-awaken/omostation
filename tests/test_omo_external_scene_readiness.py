from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from omo.omo_external_receipt import record_external_receipt
from omo.omo_external_scene_consumer import record_external_scene_consumer
from omo.omo_external_scene_readiness import (
    build_external_scene_trial_promotion_readiness,
)
from omo.omo_external_scene_trial import record_external_scene_trial
from omo.omo_external_scene_trial_feedback import record_external_scene_trial_feedback
from omo.outcome_feedback import record_outcome_feedback
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event


def _binding() -> dict[str, str]:
    return {
        "scene_id": "scene:research-brief",
        "journey_id": "journey:weekly-decision",
        "outcome_metric": "metric:decision-latency",
    }


def _trial() -> dict[str, object]:
    return {
        "schema": "external-scene-trial/v1",
        "trial_id": "scene-trial:readiness",
        "scene_binding": _binding(),
        "consumer_ref": "ref://consumer/research",
        "owner_ref": "ref://owner/research",
        "approver_ref": "ref://approver/research",
        "permission_ref": "ref://permission/research",
        "evidence_refs": [
            "evidence://demand/research",
            "evidence://activation/research",
        ],
        "preflight_ref": "ref://preflight/research",
        "catalog_observation_id": "external-resource-observation:test",
        "trial_stage": "observation_only",
        "status": "proposal_only",
        "metric": {
            "metric_id": "metric:decision-latency",
            "direction": "decrease",
            "unit": "hours",
            "target": 20,
            "baseline_ref": "evidence://baseline/research",
            "measurement_ref": "evidence://measurement/research",
        },
        "sample_plan": {"minimum_samples": 3, "window_seconds": 604800},
        "rollback_ref": "ref://rollback/research",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "feedback_contract": {"schema": "outcome-feedback/v1"},
        "actor": "test",
        "source_ref": "test:scene-trial-readiness",
        "observed_at": "2026-08-03T00:00:00Z",
    }


def _review() -> dict[str, object]:
    return {
        "schema": "external-scene-trial-feedback/v1",
        "feedback_id": "review:readiness",
        "trial_id": "scene-trial:readiness",
        "review_action": "continue",
        "evidence_refs": ["evidence://review/readiness"],
        "reviewer_ref": "ref://reviewer/readiness",
        "review_ref": "ref://review/readiness",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "actor": "test-reviewer",
        "source_ref": "test:scene-trial-review",
        "observed_at": "2026-08-03T00:10:00Z",
    }


def _consumer() -> dict[str, object]:
    return {
        "schema": "external-scene-consumer/v1",
        "consumer_id": "consumer:research",
        "consumer_ref": "ref://consumer/research",
        "consumer_kind": "workflow",
        "scene_binding": _binding(),
        "owner_ref": "ref://owner/research",
        "entrypoint_ref": "ref://entrypoint/research",
        "capability_ref": "ref://capability/research",
        "permission_ref": "ref://permission/research",
        "metric_ref": "ref://metric/decision-latency",
        "rollback_ref": "ref://rollback/research",
        "evidence_refs": ["evidence://consumer/research"],
        "status": "declared",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "actor": "test-consumer",
        "source_ref": "test:scene-consumer",
        "observed_at": "2026-08-03T00:00:00Z",
    }


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


def _completed_run(tmp_path, run_id: str = "run-readiness") -> None:
    store = WorkflowMeshStore(tmp_path)
    grant = _grant(run_id)
    store.append(
        new_workflow_event("WorkflowRequested", run_id, scene_binding=_binding())
    )
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    context = {
        "step_run_id": f"{run_id}:execute",
        "admission_id": grant["admission_id"],
    }
    store.append(new_workflow_event("StepDispatched", run_id, payload=context))
    store.append(new_workflow_event("StepStarted", run_id, payload=context))
    store.append(new_workflow_event("WorkflowSucceeded", run_id))
    record_external_receipt(
        tmp_path,
        {
            "receipt_id": "receipt:readiness",
            "trace_id": run_id,
            "resource_id": "source:research",
            "operation": "search",
            "result_state": "succeeded",
            "observed_at": "2026-08-03T00:20:00Z",
            "provenance_ref": "evidence://source/research",
            "policy_digest": "external-connection-fabric/v1",
            "decision_factors": {"health": "healthy"},
            "output_digest": "a" * 64,
        },
        workflow_run_id=run_id,
    )
    store.append(new_workflow_event("WorkflowVerified", run_id))
    store.append(new_workflow_event("PRMerged", run_id))
    store.append(new_workflow_event("WorkflowClosed", run_id))
    record_outcome_feedback(
        tmp_path,
        {
            "workflow_run_id": run_id,
            "outcome_id": "outcome:readiness",
            "scene_binding": _binding(),
            "consumption_state": "adopted",
            "consumer_ref": "ref://consumer/research",
            "result_ref": "evidence://outcome/readiness",
            "evidence_refs": ["evidence://outcome/readiness"],
            "value": {"amount": 1, "unit": "brief"},
            "observed_at": "2026-08-03T00:30:00Z",
        },
    )


def test_empty_and_blocked_projection_are_explicit(tmp_path):
    empty = build_external_scene_trial_promotion_readiness(tmp_path)
    assert empty["status"] == "empty"
    assert empty["summary"]["trial_count"] == 0
    record_external_scene_trial(tmp_path, _trial())
    record_external_scene_trial_feedback(tmp_path, _review())

    blocked = build_external_scene_trial_promotion_readiness(tmp_path)
    item = blocked["items"][0]
    assert blocked["status"] == "blocked"
    assert item["status"] == "blocked"
    assert "workflow_run_missing" in item["blockers"]
    assert blocked["activation"] == "forbidden"


def test_projection_is_ready_only_after_real_run_receipt_and_consumption(tmp_path):
    record_external_scene_trial(tmp_path, _trial())
    record_external_scene_trial_feedback(tmp_path, _review())
    record_external_scene_consumer(tmp_path, _consumer())
    _completed_run(tmp_path)

    projection = build_external_scene_trial_promotion_readiness(tmp_path)
    item = projection["items"][0]
    assert projection["status"] == "ready"
    assert item["status"] == "ready"
    assert item["blockers"] == []
    assert item["checks"]["external_receipt_recorded"] is True
    assert item["checks"]["outcome_feedback_recorded"] is True
    assert item["matched_workflow_run_ids"] == ["run-readiness"]
    assert projection["workflow_run_creation"] == "forbidden"
