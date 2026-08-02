from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/external-activation-preflight.py"
SPEC = importlib.util.spec_from_file_location("external_activation_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _scene(**overrides):
    value = {
        "scene_id": "research-brief",
        "journey_id": "weekly-decision",
        "goal": "reduce decision latency",
        "trigger": "before weekly review",
        "input_contract": "authorized references",
        "result_contract": "cited brief",
        "outcome_metric": "decision_latency_hours",
        "consumer": "research-lead",
        "approver": "human:owner",
        "owner": "research-ops",
        "failure_cost": "wrong conclusion",
        "data_classification": "private",
        "data_scope": "private:research",
        "operator": "human:owner",
        "permission_ref": "credential://research",
        "rollback_plan": "disable-resource",
        "sample_refs": [
            "vault://sample/1",
            "vault://sample/2",
            "vault://sample/3",
        ],
        "demand_evidence_refs": ["evidence://demand/1"],
        "activation_evidence_refs": ["evidence://activation/1"],
        "required_capabilities": ["search", "summarize"],
    }
    value.update(overrides)
    return value


def _catalog(
    *,
    summarize_availability="available",
    observed_at="2026-08-03T00:00:00Z",
    catalog_ttl_seconds=3600,
):
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "observed_at": observed_at,
        "catalog_ttl_seconds": catalog_ttl_seconds,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [
            {
                "id": "source:research",
                "capabilities": ["search"],
                "availability": "available",
                "lifecycle": "active",
                "reason_codes": [],
            },
            {
                "id": "method:summarize",
                "capabilities": ["summarize"],
                "availability": summarize_availability,
                "lifecycle": "active",
                "reason_codes": [],
            },
        ],
    }


def test_ready_preflight_is_non_activating():
    result = MODULE.build_preflight(
        _scene(),
        _catalog(),
        now=datetime(2026, 8, 3, 1, tzinfo=UTC),
    )

    assert result["schema"] == "external-activation-preflight/v1"
    assert result["status"] == "ready_for_admission_preview"
    assert result["activation"] == "forbidden"
    assert result["next_action"] == "submit_omo_admission_preview"
    assert result["catalog_freshness"]["status"] == "fresh"
    assert result["side_effects"] == {
        "provider_called": False,
        "omo_written": False,
        "workflow_created": False,
    }


def test_missing_scene_card_evidence_is_blocked():
    result = MODULE.build_preflight(
        _scene(sample_refs=[], activation_evidence_refs=[]), _catalog()
    )

    assert result["status"] == "blocked"
    assert "sample_refs:3-10" in result["missing_fields"]
    assert "activation_evidence_refs" in result["missing_fields"]


def test_proposal_only_capability_never_becomes_executable():
    result = MODULE.build_preflight(
        _scene(), _catalog(summarize_availability="proposal_only")
    )

    assert result["status"] == "proposal_only"
    assert result["next_action"] == "replace_proposal_only_capabilities_before_admission"
    assert result["capability_checks"][1]["status"] == "proposal_only"


def test_stale_catalog_blocks_admission_preview():
    result = MODULE.build_preflight(
        _scene(),
        _catalog(observed_at="2026-08-02T00:00:00Z"),
        now=datetime(2026, 8, 3, 1, tzinfo=UTC),
    )

    assert result["status"] == "blocked"
    assert "catalog_freshness" in result["missing_fields"]
    assert result["catalog_freshness"]["status"] == "stale"
    assert result["catalog_freshness"]["reason_codes"] == ["catalog_stale"]


def test_invalid_catalog_freshness_fails_closed():
    result = MODULE.build_preflight(
        _scene(),
        _catalog(observed_at="not-a-timestamp", catalog_ttl_seconds=0),
        now=datetime(2026, 8, 3, 1, tzinfo=UTC),
    )

    assert result["status"] == "blocked"
    assert "catalog_freshness" in result["missing_fields"]
    assert result["catalog_freshness"]["status"] == "unknown"
    assert result["catalog_freshness"]["reason_codes"] == ["invalid_catalog_ttl"]


def test_unavailable_capability_is_explicitly_blocked():
    catalog = _catalog()
    catalog["resources"].pop()

    result = MODULE.build_preflight(_scene(), catalog)

    assert result["status"] == "blocked"
    assert "catalog_capability_availability" in result["missing_fields"]
    assert result["capability_checks"][1]["status"] == "unavailable"


def test_requested_activation_or_non_proposal_lifecycle_is_blocked():
    result = MODULE.build_preflight(
        _scene(activation="active", lifecycle="active"), _catalog()
    )

    assert result["status"] == "blocked"
    assert "activation_must_be_forbidden" in result["missing_fields"]
    assert "lifecycle_must_be_proposal_only" in result["missing_fields"]
    assert result["activation"] == "forbidden"


def test_wrong_scene_card_schema_fails_closed():
    with pytest.raises(MODULE.PreflightInputError, match="scene-card/v1"):
        MODULE.build_preflight(_scene(schema="scene-card/v0"), _catalog())


def test_raw_content_and_non_opaque_refs_fail_closed():
    with pytest.raises(MODULE.PreflightInputError, match="forbidden field"):
        MODULE.build_preflight(
            _scene(raw_content="private body"), _catalog()
        )

    with pytest.raises(MODULE.PreflightInputError, match="opaque references"):
        MODULE.build_preflight(
            _scene(sample_refs=["https://example.test/raw"] * 3), _catalog()
        )


def test_cli_writes_only_stdout(tmp_path: Path, capsys):
    scene_path = tmp_path / "scene.json"
    catalog_path = tmp_path / "catalog.json"
    scene_path.write_text(json.dumps(_scene()), encoding="utf-8")
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    assert MODULE.main(
        ["--scene-card", str(scene_path), "--catalog", str(catalog_path)]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ready_for_admission_preview"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.json", "scene.json"]
