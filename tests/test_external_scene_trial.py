from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/external-scene-trial.py"
SPEC = importlib.util.spec_from_file_location("external_scene_trial", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _scene() -> dict[str, object]:
    return {
        "schema": "scene-card/v1",
        "scene_id": "scene:trial",
        "journey_id": "journey:trial",
        "goal": "降低只读检索耗时",
        "trigger": "人工复核请求",
        "input_contract": "ref://contract/input",
        "result_contract": "ref://contract/result",
        "outcome_metric": "metric:latency",
        "consumer": "业务复核人",
        "approver": "业务负责人",
        "owner": "场景负责人",
        "failure_cost": "低",
        "data_classification": "public",
        "data_scope": "metadata-only",
        "operator": "ref://operator/trial",
        "permission_ref": "ref://permission/trial",
        "rollback_plan": "ref://rollback/trial",
        "sample_refs": ["sample://1", "sample://2", "sample://3"],
        "demand_evidence_refs": ["evidence://demand/trial"],
        "activation_evidence_refs": ["evidence://activation/trial"],
        "required_capabilities": ["discover"],
        "activation": "forbidden",
        "lifecycle": "proposal_only",
    }


def _catalog() -> dict[str, object]:
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "observed_at": "2026-08-03T00:00:00Z",
        "catalog_ttl_seconds": 3600,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [
            {
                "id": "source:trial",
                "kind": "knowledge_source",
                "capabilities": ["discover"],
                "availability": "available",
                "lifecycle": "sandbox",
                "reason_codes": [],
            }
        ],
    }


def _plan() -> dict[str, object]:
    return {
        "consumer_ref": "ref://consumer/trial",
        "owner_ref": "ref://owner/trial",
        "approver_ref": "ref://approver/trial",
        "evidence_refs": ["evidence://demand/trial", "evidence://activation/trial"],
        "catalog_observation_id": "external-resource-observation:trial",
        "metric": {
            "metric_id": "metric:latency",
            "direction": "decrease",
            "unit": "seconds",
            "target": 20,
            "baseline_ref": "evidence://baseline/trial",
            "measurement_ref": "evidence://measurement/trial",
        },
        "sample_plan": {"minimum_samples": 3, "window_seconds": 604800},
        "rollback_ref": "ref://rollback/trial",
    }


def test_builds_observation_only_trial_without_side_effects(tmp_path: Path) -> None:
    result = MODULE.build_scene_trial(
        Path(__file__).parents[1],
        _scene(),
        _catalog(),
        _plan(),
        now=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert result["status"] == "proposal_only"
    trial = result["trial"]
    assert trial["trial_stage"] == "observation_only"
    assert trial["activation"] == "forbidden"
    assert trial["provider_invocation"] is False
    assert trial["workflow_run_id"] is None
    assert trial["side_effects"]["omo_written"] is False
    assert trial["feedback_contract"]["schema"] == "outcome-feedback/v1"


def test_blocked_preflight_does_not_produce_recordable_trial() -> None:
    scene = _scene()
    scene["required_capabilities"] = ["missing-capability"]
    result = MODULE.build_scene_trial(
        Path(__file__).parents[1],
        scene,
        _catalog(),
        _plan(),
        now=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert result["status"] == "blocked"
    assert result["activation"] == "forbidden"
    assert "catalog_capability_availability" in result["missing_fields"]
    assert "trial" not in result


def test_trial_builder_rejects_raw_plan_fields() -> None:
    plan = _plan()
    plan["evidence_refs"] = ["private body", "evidence://activation/trial"]
    try:
        MODULE.build_scene_trial(Path(__file__).parents[1], _scene(), _catalog(), plan)
    except MODULE.SceneTrialInputError as exc:
        assert "opaque" in str(exc)
    else:
        raise AssertionError("raw plan reference must be rejected")
