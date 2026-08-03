from __future__ import annotations

from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_external_scene_trial_review_contract_is_registered():
    documents = list(
        yaml.safe_load_all(
            (ROOT / ".omo/_truth/registry/external-connection-fabric.yaml").read_text(encoding="utf-8")
        )
    )
    registry = next(document for document in documents if isinstance(document, dict) and "dynamic_discovery" in document)
    extension = registry["dynamic_discovery"]["extension_contract"]
    assert extension["scene_trial_review_schema"] == "external-scene-trial-feedback/v1"
    assert extension["scene_trial_review_api"] == {
        "read": "GET /api/external-resources/scene-trials",
        "write": "POST /api/external-resources/scene-trials/review",
        "mode": "proposal_only",
        "allowed_actions": ["continue", "request_changes", "reject"],
        "required_refs": ["trial_id", "reviewer_ref", "review_ref", "evidence_refs"],
        "activation": "forbidden",
        "provider_invocation": "forbidden",
        "workflow_run_creation": "forbidden",
        "admission_mutation": "forbidden",
        "idempotency_key": "feedback_id_and_stable_review_digest",
    }
    assert extension["scene_trial_readiness_schema"] == "external-scene-trial-promotion-readiness/v1"
    assert extension["scene_trial_readiness_cli"] == "omo external-resources scene-trial-readiness"
    assert extension["scene_trial_readiness_api"] == {
        "read": "GET /api/external-resources/scene-trials/readiness",
        "mode": "read_only_projection",
        "required_facts": [
            "trial_recorded",
            "review_continue",
            "workflow_run",
            "external_receipt",
            "outcome_feedback",
        ],
        "statuses": ["empty", "blocked", "ready", "unavailable"],
        "activation": "forbidden",
        "provider_invocation": "forbidden",
        "workflow_run_creation": "forbidden",
        "admission_mutation": "forbidden",
        "external_side_effects": "disabled",
        "promotion_semantics": "human_proposal_only",
    }
    assert extension["scene_consumer_schema"] == "external-scene-consumer/v1"
    assert extension["scene_consumer_cli"] == "omo external-resources record-scene-consumer --stdin"
    assert extension["scene_consumer_semantics"] == {
        "allowed_status": ["declared"],
        "required_refs": [
            "consumer_ref",
            "owner_ref",
            "entrypoint_ref",
            "capability_ref",
            "permission_ref",
            "metric_ref",
            "rollback_ref",
        ],
        "required_scene_binding": True,
        "activation": "forbidden",
        "provider_invocation": "forbidden",
        "workflow_run_binding_before_promotion": "forbidden",
        "readiness_role": "required_fact",
        "idempotency_key": "consumer_id_and_stable_contract_digest",
    }
