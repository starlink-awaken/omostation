from __future__ import annotations

import json

import pytest
from omo.omo_external_evaluation import (
    ExternalResourceEvaluationError,
    read_external_resource_evaluations,
    record_external_resource_evaluation,
)


def _evaluation() -> dict[str, object]:
    return {
        "schema": "external-resource-evaluation/v1",
        "mode": "read_only_evaluation",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "capability": "search",
        "trace_id": "trace:evaluation-1",
        "policy_digest": "external-connection-fabric/v1",
        "scene_binding": {
            "scene_id": "research-brief",
            "journey_id": "weekly-decision",
            "outcome_metric": "decision_latency_hours",
            "data_scope": "public:research",
            "operator": "human:test",
            "permission_ref": "permission://test",
        },
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


def test_evaluation_observation_is_safe_durable_and_idempotent(tmp_path):
    first = record_external_resource_evaluation(
        tmp_path,
        _evaluation(),
        workflow_run_id="run-evaluation-1",
        actor="cockpit-user",
    )
    repeated = record_external_resource_evaluation(
        tmp_path,
        _evaluation(),
        workflow_run_id="run-evaluation-1",
        actor="cockpit-user",
    )

    assert first["status"] == "recorded"
    assert repeated["status"] == "deduplicated"
    observation = first["observation"]
    assert observation["schema"] == "external-resource-evaluation-observation/v1"
    assert observation["workflow_run_id"] == "run-evaluation-1"
    assert observation["summary"]["candidate_count"] == 1
    assert len(read_external_resource_evaluations(tmp_path)) == 1
    encoded = json.dumps(observation, ensure_ascii=False)
    assert '"raw_content"' not in encoded
    assert '"raw_output"' not in encoded
    assert "permission://test" in encoded


def test_evaluation_observation_rejects_raw_fields_and_invalid_boundary(tmp_path):
    raw = _evaluation()
    raw["raw_output"] = "private result"
    with pytest.raises(ExternalResourceEvaluationError, match="forbidden"):
        record_external_resource_evaluation(tmp_path, raw)

    invalid = _evaluation()
    invalid["activation"] = "allowed"
    with pytest.raises(ExternalResourceEvaluationError, match="activation"):
        record_external_resource_evaluation(tmp_path, invalid)


def test_evaluation_id_conflict_fails_closed(tmp_path):
    record_external_resource_evaluation(
        tmp_path, _evaluation(), evaluation_id="evaluation-fixed"
    )
    changed = _evaluation()
    changed["selected_resource_id"] = None
    with pytest.raises(ExternalResourceEvaluationError, match="conflicting"):
        record_external_resource_evaluation(
            tmp_path, changed, evaluation_id="evaluation-fixed"
        )
