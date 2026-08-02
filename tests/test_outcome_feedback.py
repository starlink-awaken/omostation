from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from omo.outcome_feedback import (
    OutcomeFeedbackError,
    read_outcome_feedback,
    record_outcome_feedback,
)
from omo.workflow_eval import build_operations_snapshot
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

SCENE = {
    "scene_id": "engineering-delivery",
    "journey_id": "intent-to-evidence",
    "outcome_metric": "verified_delivery_lead_time",
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


def _closed_run(omo_dir, run_id: str = "run-feedback-1") -> None:
    store = WorkflowMeshStore(omo_dir)
    grant = _grant(run_id)
    store.append(new_workflow_event("WorkflowRequested", run_id, scene_binding=SCENE))
    store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
    step_payload = {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}
    store.append(new_workflow_event("StepDispatched", run_id, payload=step_payload))
    store.append(new_workflow_event("StepStarted", run_id, payload=step_payload))
    store.append(new_workflow_event("WorkflowSucceeded", run_id))
    store.append(
        new_workflow_event(
            "EvidenceRecorded",
            run_id,
            payload={"evidence_id": f"evidence-{run_id}", "kind": "test-report"},
        )
    )
    store.append(new_workflow_event("WorkflowVerified", run_id))
    store.append(new_workflow_event("PRMerged", run_id))
    store.append(new_workflow_event("WorkflowClosed", run_id))


def _payload(run_id: str = "run-feedback-1") -> dict[str, object]:
    return {
        "workflow_run_id": run_id,
        "outcome_id": "outcome:engineering-delivery:2026-08-02",
        "scene_binding": SCENE,
        "consumption_state": "adopted",
        "consumer_ref": "operator://redacted/reviewer-1",
        "result_ref": "evidence://workflow-mesh/outcome/2026-08-02",
        "evidence_refs": ["evidence://github/pr/813"],
        "value": {"amount": 42, "unit": "minutes", "comparison": "saved"},
        "observed_at": "2026-08-02T14:45:00Z",
        "note": "内部复盘备注不应落盘，只保留摘要哈希",
    }


def test_record_feedback_is_durable_idempotent_and_consumed(tmp_path):
    _closed_run(tmp_path)

    first = record_outcome_feedback(tmp_path, _payload(), actor="cockpit-user")
    second = record_outcome_feedback(tmp_path, _payload(), actor="cockpit-user")

    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    feedback = first["feedback"]
    assert feedback["schema"] == "outcome-feedback/v1"
    assert feedback["consumption_state"] == "adopted"
    assert feedback["value"]["amount"] == 42
    assert feedback["note_digest"].startswith("sha256:")
    assert "内部复盘备注" not in json.dumps(feedback, ensure_ascii=False)
    assert len(read_outcome_feedback(tmp_path)) == 1

    operations = build_operations_snapshot(tmp_path)
    assert operations["consumption"]["status"] == "observed"
    assert operations["consumption"]["consumed_runs"] == 1
    assert operations["consumption"]["feedback_count"] == 1
    assert operations["consumption"]["consumption_rate_among_eligible_closed_runs"] == 1.0
    assert operations["by_scene"][0]["consumed_runs"] == 1


def test_feedback_must_match_run_scene_and_not_record_before_outcome(tmp_path):
    _closed_run(tmp_path)
    invalid = _payload()
    invalid["scene_binding"] = {**SCENE, "scene_id": "other-scene"}

    with pytest.raises(OutcomeFeedbackError, match="scene_binding"):
        record_outcome_feedback(tmp_path, invalid)

    running_dir = tmp_path / "running"
    store = WorkflowMeshStore(running_dir)
    store.append(new_workflow_event("WorkflowRequested", "run-running", scene_binding=SCENE))
    running_payload = _payload("run-running")
    with pytest.raises(OutcomeFeedbackError, match="eligible outcome"):
        record_outcome_feedback(running_dir, running_payload)


def test_feedback_rejects_raw_or_unsupported_value_fields(tmp_path):
    _closed_run(tmp_path)
    raw = _payload()
    raw["raw_output"] = "private content"
    with pytest.raises(OutcomeFeedbackError, match="forbidden"):
        record_outcome_feedback(tmp_path, raw)

    unsupported = _payload()
    unsupported["value"] = {"raw_note": "do not store"}
    with pytest.raises(OutcomeFeedbackError, match="unsupported fields"):
        record_outcome_feedback(tmp_path, unsupported)
