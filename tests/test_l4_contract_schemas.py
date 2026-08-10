"""L4 Phase 0 M2 contract schema tests."""

from __future__ import annotations

from dataclasses import MISSING, fields
from pathlib import Path
import runpy

import pytest
import yaml


M2_L4 = Path(__file__).resolve().parents[1] / "src" / "ecos" / "ssot" / "mof" / "m2" / "l4"

SCHEMAS = {
    "domain-manifest.yaml": {
        "m2_type": "L4DomainManifest",
        "body": "L4DomainManifest",
        "required": {
            "api_version",
            "kind",
            "id",
            "display_name",
            "archetype",
            "space_ref",
            "root",
            "owners",
            "principal_ref",
            "default_sensitivity",
            "default_visibility",
            "sharing_policy",
            "retention",
            "authority_policy",
            "harness_profile_ref",
            "lifecycle",
        },
        "optional": {"policy_refs"},
    },
    "harness-profile.yaml": {
        "m2_type": "L4HarnessProfile",
        "body": "L4HarnessProfile",
        "required": {"id", "archetype", "required_gates"},
        "optional": {"advisory_gates", "disabled_gates"},
    },
    "domain-health.yaml": {
        "m2_type": "L4DomainHealth",
        "body": "L4DomainHealth",
        "required": {"domain_id", "profile_id", "checked_at", "issues"},
        "optional": set(),
    },
}


@pytest.mark.parametrize("filename", sorted(SCHEMAS))
def test_l4_contract_schema_is_strict_m2_definition(filename: str) -> None:
    expected = SCHEMAS[filename]
    path = M2_L4 / filename

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload["m2_type"] == expected["m2_type"]
    assert payload["version"] == "1.0.0"
    assert payload["created"]
    body = payload[expected["body"]]
    assert body["m3_parent"]
    assert body["description"]
    assert set(body["requiredProperties"]) == expected["required"]
    assert set(body.get("optionalProperties", {})) == expected["optional"]
    assert body["stateMachine"]
    assert body["validationRules"]


def test_domain_manifest_schema_declares_wire_alias_and_phase0_enums() -> None:
    payload = yaml.safe_load((M2_L4 / "domain-manifest.yaml").read_text(encoding="utf-8"))
    body = payload["L4DomainManifest"]

    assert body["wireAliases"] == {"api_version": "apiVersion"}
    assert body["wireConstants"] == {"apiVersion": "l4/v1", "kind": "DomainManifest"}
    assert body["requiredProperties"]["archetype"]["values"] == [
        "constitutional",
        "private-core",
        "operational",
        "library",
        "federation",
        "projection",
    ]
    assert body["requiredProperties"]["space_ref"]["pattern"] == "^personal-space$"


def test_mof_schema_loader_discovers_nested_l4_contracts() -> None:
    tool = M2_L4.parent.parent.parent / "tools" / "mof-schema-validate.py"
    namespace = runpy.run_path(str(tool))

    schemas = namespace["load_m2_schemas"]()

    assert {"L4DomainManifest", "L4HarnessProfile", "L4DomainHealth"}.issubset(schemas)


def test_l4_runtime_models_match_m2_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    ecos_root = Path(__file__).resolve().parents[1]
    l4_src = ecos_root.parent / "l4-kernel" / "src"
    if not l4_src.exists():
        pytest.skip("l4-kernel sibling checkout is required for cross-project contract alignment")
    monkeypatch.syspath_prepend(str(l4_src))

    from l4_kernel.contracts import DomainHealth, DomainManifest, HarnessProfile

    runtime_models = {
        "domain-manifest.yaml": DomainManifest,
        "harness-profile.yaml": HarnessProfile,
        "domain-health.yaml": DomainHealth,
    }
    for filename, model in runtime_models.items():
        expected = SCHEMAS[filename]["required"]
        required = {
            field.name
            for field in fields(model)
            if field.default is MISSING and field.default_factory is MISSING
        }
        assert required == expected
