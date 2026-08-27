"""Tests for internal-scene-preflight.py — internal pipeline capability validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_preflight():
    spec = importlib.util.spec_from_file_location(
        "internal_scene_preflight", ROOT / "bin/ssot/internal-scene-preflight.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["internal_scene_preflight"] = module
    spec.loader.exec_module(module)
    return module


preflight_mod = _load_preflight()
build_preflight = preflight_mod.build_preflight


def _base_scene_card() -> dict:
    """Minimal valid internal pipeline scene card."""
    return {
        "schema": "scene-card/v1",
        "scene_type": "internal_pipeline",
        "lifecycle": "proposal_only",
        "activation": "forbidden",
        "scene_id": "test-internal",
        "journey_id": "test-journey",
        "goal": "test goal",
        "trigger": "test trigger",
        "input_contract": "test input",
        "result_contract": "test result",
        "outcome_metric": "test_metric",
        "consumer": "test-consumer",
        "approver": "test-approver",
        "owner": "test-owner",
        "failure_cost": "test failure",
        "data_classification": "internal",
        "data_scope": "test-scope",
        "operator": "test-operator",
        "permission_ref": "permission://internal/test-scene",
        "permission_scope": ["ci-read", "evidence-write"],
        "rollback_plan": "test-rollback",
        "sample_refs": [
            "evidence://github/pr/755",
            "evidence://github/pr/765",
            "evidence://github/pr/766",
        ],
        "activation_evidence_refs": [
            "evidence://github/pr/755",
            "evidence://github/pr/766",
        ],
        "required_capabilities": [
            "ref://capability/gac-local-gate",
        ],
    }


class TestSceneCardValidation:
    def test_complete_scene_card_passes_schema(self):
        card = _base_scene_card()
        result = build_preflight(card, root=ROOT)
        assert result["schema"] == "internal-activation-preflight/v1"
        assert result["scene_card"]["missing_fields"] == []

    def test_missing_scene_type_blocks(self):
        card = _base_scene_card()
        del card["scene_type"]
        result = build_preflight(card, root=ROOT)
        assert "scene_type:must_be_internal_pipeline" in result["missing_fields"]

    def test_wrong_scene_type_blocks(self):
        card = _base_scene_card()
        card["scene_type"] = "external"
        result = build_preflight(card, root=ROOT)
        assert "scene_type:must_be_internal_pipeline" in result["missing_fields"]

    def test_activation_not_forbidden_blocks(self):
        card = _base_scene_card()
        card["activation"] = "allowed"
        result = build_preflight(card, root=ROOT)
        assert "activation_must_be_forbidden" in result["missing_fields"]

    def test_lifecycle_not_proposal_only_blocks(self):
        card = _base_scene_card()
        card["lifecycle"] = "active"
        result = build_preflight(card, root=ROOT)
        assert "lifecycle_must_be_proposal_only" in result["missing_fields"]


class TestCapabilityChecks:
    def test_existing_make_target_is_available(self):
        card = _base_scene_card()
        card["required_capabilities"] = ["ref://capability/gac-local-gate"]
        result = build_preflight(card, root=ROOT)
        caps = result["capability_checks"]
        assert len(caps) == 1
        assert caps[0]["status"] == "available"

    def test_nonexistent_make_target_is_unavailable(self):
        card = _base_scene_card()
        card["required_capabilities"] = ["ref://capability/nonexistent-target-xyz"]
        result = build_preflight(card, root=ROOT)
        caps = result["capability_checks"]
        assert caps[0]["status"] == "unavailable"
        assert "internal_capability_availability" in result["missing_fields"]

    def test_prefix_match_finds_capability(self):
        """agent-workflow-lifecycle → prefix match to agent-workflow-* targets."""
        card = _base_scene_card()
        card["required_capabilities"] = ["ref://capability/agent-workflow-lifecycle"]
        result = build_preflight(card, root=ROOT)
        caps = result["capability_checks"]
        assert caps[0]["status"] == "available"
        assert "prefix match" in caps[0].get("detail", "")

    def test_invalid_capability_format_blocks(self):
        card = _base_scene_card()
        card["required_capabilities"] = ["not-a-valid-format"]
        result = build_preflight(card, root=ROOT)
        caps = result["capability_checks"]
        assert caps[0]["status"] == "invalid_format"


class TestPermissionValidation:
    def test_valid_internal_permission(self):
        card = _base_scene_card()
        result = build_preflight(card, root=ROOT)
        assert result["permission_check"]["status"] == "valid"

    def test_external_permission_format_rejected(self):
        card = _base_scene_card()
        card["permission_ref"] = "permission://workflow-mesh/test"
        result = build_preflight(card, root=ROOT)
        assert result["permission_check"]["status"] == "invalid_format"

    def test_missing_permission_scope_blocks(self):
        card = _base_scene_card()
        del card["permission_scope"]
        result = build_preflight(card, root=ROOT)
        assert result["permission_check"]["status"] == "missing_scope"


class TestSideEffects:
    def test_no_side_effects(self):
        card = _base_scene_card()
        result = build_preflight(card, root=ROOT)
        assert result["side_effects"]["omo_written"] is False
        assert result["side_effects"]["provider_called"] is False
        assert result["side_effects"]["workflow_created"] is False
        assert result["activation"] == "forbidden"
