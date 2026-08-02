from __future__ import annotations

import pytest
from omo.omo_external_scene_trial import (
    ExternalSceneTrialError,
    read_external_scene_trials,
    record_external_scene_trial,
)


def _payload(trial_id: str = "scene-trial:test-1") -> dict[str, object]:
    return {
        "schema": "external-scene-trial/v1",
        "trial_id": trial_id,
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
            "unit": "seconds",
            "target": 20,
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


def test_trial_receipt_is_durable_idempotent_and_proposal_only(tmp_path):
    first = record_external_scene_trial(tmp_path, _payload())
    second = record_external_scene_trial(tmp_path, _payload())

    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    receipt = first["receipt"]
    assert receipt["schema"] == "external-scene-trial/v1"
    assert receipt["trial_stage"] == "observation_only"
    assert receipt["provider_invocation"] is False
    assert receipt["workflow_run_id"] is None
    assert receipt["feedback_contract"]["required_workflow_run_id"] is True
    assert len(read_external_scene_trials(tmp_path)) == 1


def test_trial_rejects_activation_workflow_and_raw_content(tmp_path):
    payload = _payload()
    payload["activation"] = "allowed"
    with pytest.raises(ExternalSceneTrialError, match="activation"):
        record_external_scene_trial(tmp_path, payload)

    payload = _payload()
    payload["workflow_run_id"] = "run-should-not-exist"
    with pytest.raises(ExternalSceneTrialError, match="WorkflowRun"):
        record_external_scene_trial(tmp_path, payload)

    payload = _payload()
    payload["metric"] = {"raw_output": "private"}
    with pytest.raises(ExternalSceneTrialError, match="forbidden"):
        record_external_scene_trial(tmp_path, payload)


def test_conflicting_trial_id_fails_closed(tmp_path):
    record_external_scene_trial(tmp_path, _payload())
    changed = _payload()
    changed["sample_plan"] = {"minimum_samples": 4, "window_seconds": 604800}
    with pytest.raises(ExternalSceneTrialError, match="conflicting"):
        record_external_scene_trial(tmp_path, changed)


def test_retry_with_new_observation_time_is_idempotent(tmp_path):
    first = record_external_scene_trial(tmp_path, _payload())
    retried = _payload()
    retried["observed_at"] = "2026-08-03T00:05:00Z"
    retried["actor"] = "another-observer"

    second = record_external_scene_trial(tmp_path, retried)

    assert first["receipt"]["trial_digest"] == second["receipt"]["trial_digest"]
    assert second["status"] == "deduplicated"
