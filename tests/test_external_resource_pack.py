from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/external-resource-pack.py"
SPEC = importlib.util.spec_from_file_location("external_resource_pack", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).parents[1]


def _pack(**overrides):
    descriptor = {
        "id": "source:research",
        "kind": "knowledge_source",
        "provider": "research-provider",
        "protocol": "external-resource/v1",
        "capabilities": ["discover", "search", "read"],
        "data_classification": "public",
        "provenance": {"source_ref": "evidence://research/provider"},
        "lifecycle": "sandbox",
        "health": {
            "status": "healthy",
            "observed_at": "2026-08-03T00:00:00+00:00",
            "latency_ms": 10,
            "source": "probe:research",
        },
        "owner": "owner:research",
        "version": "1.0.0",
        "permission_ref": "permission://research/read",
        "mode": "live_query",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "rollback_plan": "disable provider and return unavailable",
    }
    pack = {
        "schema": "external-resource-pack/v1",
        "pack_id": "pack:research-provider",
        "pack_version": "1.0.0",
        "provider": "research-provider",
        "activation": "forbidden",
        "extension": {
            "entry_point_group": "external.resources",
            "entry_point": "research-provider",
            "provider_method": "external_descriptor",
            "health_probe": {
                "method": "health_probe",
                "side_effect": "read_only",
                "required": True,
            },
        },
        "descriptor": descriptor,
    }
    pack.update(overrides)
    return pack


def test_valid_pack_is_ready_for_catalog_preview_without_activation() -> None:
    result = MODULE.check_external_resource_pack(ROOT, _pack())

    assert result["schema"] == "external-resource-pack-check/v1"
    assert result["status"] == "ready_for_catalog_preview"
    assert result["activation"] == "forbidden"
    assert result["reason_codes"] == []
    assert result["execution_policy"]["provider_import"] == "forbidden"
    assert result["catalog_preview"]["schema"] == "external-resource-pack-catalog-preview/v1"
    assert result["catalog_preview"]["resource"]["availability"] == "unobserved"
    assert result["catalog_preview"]["resource"]["health"]["status"] == "unobserved"
    assert result["catalog_preview"]["next_action"] == "通过只读目录发现和健康探针后再评估可用性。"


def test_method_pack_remains_proposal_only() -> None:
    pack = _pack()
    pack["descriptor"] = dict(pack["descriptor"], kind="method_pack", capabilities=["discover", "explain"], mode="proposal_only")

    result = MODULE.check_external_resource_pack(ROOT, pack)

    assert result["status"] == "proposal_only"
    assert result["descriptor"]["kind"] == "method_pack"
    assert result["catalog_preview"]["status"] == "proposal_only"
    assert result["catalog_preview"]["resource"]["availability"] == "unobserved"


def test_invalid_extension_and_capability_are_blocked() -> None:
    pack = _pack()
    pack["extension"] = dict(pack["extension"], health_probe={"method": "invoke", "side_effect": "write", "required": False})
    pack["descriptor"] = dict(pack["descriptor"], capabilities=["delete"])

    result = MODULE.check_external_resource_pack(ROOT, pack)

    assert result["status"] == "blocked"
    assert "health_probe_method_must_be_health_probe" in result["reason_codes"]
    assert "health_probe_must_be_read_only" in result["reason_codes"]
    assert "capability_not_allowed_for_kind" in result["reason_codes"]
    assert result["catalog_preview"] is None


def test_active_descriptor_cannot_smuggle_activation_into_a_pack() -> None:
    pack = _pack()
    pack["descriptor"] = dict(pack["descriptor"], lifecycle="active")
    pack["activation"] = "allowed"

    result = MODULE.check_external_resource_pack(ROOT, pack)

    assert result["status"] == "blocked"
    assert "lifecycle_must_start_discovered_or_sandbox" in result["reason_codes"]
    assert "activation_must_be_forbidden" in result["reason_codes"]


def test_forbidden_nested_secret_is_rejected_before_preview() -> None:
    pack = _pack()
    pack["descriptor"] = dict(pack["descriptor"], metadata={"nested": {"token": "do-not-store"}})

    try:
        MODULE.check_external_resource_pack(ROOT, pack)
    except MODULE.ExternalResourcePackError as exc:
        assert "secret field is forbidden" in str(exc)
    else:
        raise AssertionError("nested secret must be rejected")
