from __future__ import annotations

from pathlib import Path

import yaml


OMO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OMO_ROOT.parent


def _load_workspace_yaml(rel_path: str) -> dict:
    return yaml.safe_load((WORKSPACE_ROOT / rel_path).read_text(encoding="utf-8")) or {}


def test_space_registry_declares_system_space_manifest() -> None:
    registry = _load_workspace_yaml("spaces/registry.yaml")

    assert registry["apiVersion"] == "omo/v1"
    assert registry["kind"] == "SpaceRegistry"
    assert registry["schema_version"] == "v1"

    spaces = registry["spaces"]
    system_space = next(space for space in spaces if space["id"] == "system-space")
    assert system_space["manifest"] == "spaces/system-space.yaml"
    assert (WORKSPACE_ROOT / system_space["manifest"]).exists()


def test_space_registry_entry_carries_boundary_metadata() -> None:
    registry = _load_workspace_yaml("spaces/registry.yaml")
    entry = next(space for space in registry["spaces"] if space["id"] == "system-space")

    assert registry["manifest_root"] == "spaces"
    assert entry["display_name"] == "System Space"
    assert entry["owners"]["governance_root"] == ".omo"
    assert entry["roots"]["data"] == "data"
    assert entry["roots"]["runtime"] == "runtime"
    assert {
        ".omo/plans/phase9-program-plan.md",
        ".omo/plans/phase9-wave2-execution-plan.md",
        ".omo/plans/phase9-wave3-execution-plan.md",
        ".omo/plans/phase9-wave4-execution-plan.md",
        "spaces/system-space-identity-admission.yaml",
        "spaces/system-space-capability-taxonomy.yaml",
        "spaces/system-space-admission-matrix.yaml",
        "spaces/system-space-rollout-policy.yaml",
    }.issubset(set(entry["policy_refs"]))

    for rel_path in entry["policy_refs"]:
        assert (WORKSPACE_ROOT / rel_path).exists(), rel_path


def test_system_space_manifest_matches_schema_contract() -> None:
    schema = _load_workspace_yaml("spaces/_schema/space-manifest.schema.yaml")
    manifest = _load_workspace_yaml("spaces/system-space.yaml")

    assert schema["kind"] == "SpaceManifestSchema"
    assert schema["required"] == [
        "apiVersion",
        "kind",
        "id",
        "display_name",
        "space_kind",
        "owners",
        "roots",
        "routing",
    ]
    assert schema["owner_keys"] == [
        "governance_root",
        "capability_roots",
    ]
    assert schema["root_keys"] == [
        "governance",
        "spaces",
        "data",
        "runtime",
    ]
    assert schema["policy_ref_field"] == "policy_refs"
    assert schema["registry_entry_required"] == [
        "id",
        "display_name",
        "manifest",
        "space_kind",
        "owners",
        "roots",
        "policy_refs",
    ]

    for field in schema["required"]:
        assert field in manifest

    assert manifest["kind"] == "SpaceManifest"
    assert manifest["id"] == "system-space"
    assert manifest["space_kind"] == "system"
    assert manifest["owners"]["governance_root"] == ".omo"
    assert manifest["owners"]["capability_roots"] == [
        "projects/SharedBrain",
        "projects/gbrain",
        "projects/agentmesh",
        "projects/kairon",
    ]
    assert manifest["roots"] == {
        "governance": ".omo",
        "spaces": "spaces",
        "data": "data",
        "runtime": "runtime",
    }
    assert manifest["routing"]["default_project"] == "projects/SharedBrain"

    for rel_path in manifest["owners"]["capability_roots"]:
        assert (WORKSPACE_ROOT / rel_path).exists(), rel_path
    for rel_path in manifest["roots"].values():
        assert (WORKSPACE_ROOT / rel_path).exists(), rel_path
    for rel_path in manifest["policy_refs"]:
        assert (WORKSPACE_ROOT / rel_path).exists(), rel_path
