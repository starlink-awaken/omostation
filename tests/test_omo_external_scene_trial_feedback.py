from __future__ import annotations

import pytest
from omo.omo_external_scene_trial import record_external_scene_trial
from omo.omo_external_scene_trial_feedback import (
    ExternalSceneTrialFeedbackError,
    read_external_scene_trial_feedback,
    record_external_scene_trial_feedback,
)


def _trial_payload() -> dict[str, object]:
    return {
        "schema": "external-scene-trial/v1",
        "trial_id": "scene-trial:test-1",
        "scene_binding": {
            "scene_id": "scene:test",
            "journey_id": "journey:test",
            "outcome_metric": "metric:test",
        },
        "consumer_ref": "ref://consumer/test",
        "owner_ref": "ref://owner/test",
        "approver_ref": "ref://approver/test",
        "permission_ref": "ref://permission/test",
        "evidence_refs": ["evidence://demand/test", "evidence://activation/test"],
        "preflight_ref": "ref://preflight/test",
        "catalog_observation_id": "external-resource-observation:test",
        "trial_stage": "observation_only",
        "status": "proposal_only",
        "metric": {
            "metric_id": "metric:test",
            "direction": "decrease",
            "baseline_ref": "evidence://baseline/test",
            "measurement_ref": "evidence://measurement/test",
        },
        "sample_plan": {"minimum_samples": 3, "window_seconds": 604800},
        "rollback_ref": "ref://rollback/test",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "feedback_contract": {"schema": "outcome-feedback/v1"},
        "actor": "test",
        "source_ref": "test:scene-trial",
        "observed_at": "2026-08-03T00:00:00Z",
    }


def _feedback(feedback_id: str = "review:test-1") -> dict[str, object]:
    return {
        "schema": "external-scene-trial-feedback/v1",
        "feedback_id": feedback_id,
        "trial_id": "scene-trial:test-1",
        "review_action": "continue",
        "evidence_refs": ["evidence://review/test"],
        "reviewer_ref": "ref://reviewer/test",
        "review_ref": "ref://review/test",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "actor": "test-reviewer",
        "source_ref": "test:scene-trial-review",
        "observed_at": "2026-08-03T00:10:00Z",
    }


def test_review_receipt_requires_existing_trial_and_is_idempotent(tmp_path):
    record_external_scene_trial(tmp_path, _trial_payload())
    first = record_external_scene_trial_feedback(tmp_path, _feedback())
    second = record_external_scene_trial_feedback(tmp_path, _feedback())

    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    assert first["feedback"]["activation"] == "forbidden"
    assert first["feedback"]["workflow_run_id"] is None
    assert len(read_external_scene_trial_feedback(tmp_path)) == 1


def test_review_rejects_workflow_activation_and_raw_rationale(tmp_path):
    record_external_scene_trial(tmp_path, _trial_payload())
    payload = _feedback()
    payload["workflow_run_id"] = "run-should-not-exist"
    with pytest.raises(ExternalSceneTrialFeedbackError, match="WorkflowRun"):
        record_external_scene_trial_feedback(tmp_path, payload)

    payload = _feedback()
    payload["rationale"] = "private text"
    with pytest.raises(ExternalSceneTrialFeedbackError, match="forbidden"):
        record_external_scene_trial_feedback(tmp_path, payload)


def test_review_conflict_fails_closed(tmp_path):
    record_external_scene_trial(tmp_path, _trial_payload())
    record_external_scene_trial_feedback(tmp_path, _feedback())
    changed = _feedback()
    changed["review_action"] = "reject"
    with pytest.raises(ExternalSceneTrialFeedbackError, match="conflicting"):
        record_external_scene_trial_feedback(tmp_path, changed)
