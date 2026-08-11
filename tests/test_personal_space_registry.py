"""Phase 0 personal-space configuration contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPACES = ROOT / "spaces"


def _yaml(name: str) -> dict[str, Any]:
    payload = yaml.safe_load((SPACES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _all_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _all_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_strings(child)]
    return []


def test_space_manifest_schema_supports_optional_knowledge_root() -> None:
    yaml_schema = _yaml("_schema/space-manifest.schema.yaml")
    json_schema = json.loads((SPACES / "_schema/json/space-manifest.schema.json").read_text(encoding="utf-8"))

    assert yaml_schema["root_keys"] == ["governance", "spaces", "data", "runtime"]
    assert yaml_schema["optional_root_keys"] == ["knowledge"]
    assert json_schema["properties"]["roots"]["properties"]["knowledge"] == {"type": "string"}
    assert "knowledge" not in json_schema["properties"]["roots"]["required"]


def test_registry_contains_one_personal_space_and_no_team_space() -> None:
    registry = _yaml("registry.yaml")
    personal_entries = [entry for entry in registry["spaces"] if entry["id"] == "personal-space"]

    assert len(personal_entries) == 1
    assert all(entry["space_kind"] != "team" for entry in registry["spaces"])
    entry = personal_entries[0]
    assert entry["manifest"] == "spaces/personal-space.yaml"
    assert entry["status"] == "active"
    assert entry["roots"]["knowledge"] == "../Documents"
    for policy_ref in entry["policy_refs"]:
        assert (ROOT / policy_ref).exists(), policy_ref


def test_personal_space_manifest_is_single_owner_and_portable() -> None:
    manifest = _yaml("personal-space.yaml")

    assert manifest["kind"] == "SpaceManifest"
    assert manifest["id"] == "personal-space"
    assert manifest["space_kind"] == "personal"
    assert manifest["owners"]["governance_root"] == ".omo"
    assert manifest["owners"]["capability_roots"] == [
        "projects/l4-kernel",
        "projects/kairon",
        "projects/gbrain",
    ]
    assert manifest["roots"]["knowledge"] == "../Documents"
    assert not Path(manifest["roots"]["knowledge"]).is_absolute()
    assert all("/Users/" not in value for value in _all_strings(manifest))


def test_personal_space_admission_is_default_deny_with_readonly_agent() -> None:
    identity = _yaml("personal-space-identity-admission.yaml")
    taxonomy = _yaml("personal-space-capability-taxonomy.yaml")
    matrix = _yaml("personal-space-admission-matrix.yaml")

    assert identity["identity_anchor"] == "actor_space_membership"
    assert identity["capability_taxonomy_ref"] == "spaces/personal-space-capability-taxonomy.yaml"
    assert identity["admission_matrix_ref"] == "spaces/personal-space-admission-matrix.yaml"
    assert {actor["id"] for actor in identity["actors"]} == {
        "personal-space-owner",
        "l4-readonly-agent",
    }
    memberships = {item["id"]: item for item in identity["memberships"]}
    assert memberships["personal-owner-membership"]["roles"] == ["owner"]
    assert memberships["l4-readonly-membership"]["roles"] == ["readonly-validator"]
    bindings = {item["membership_ref"]: set(item["capabilities"]) for item in identity["capability_bindings"]}
    assert bindings["personal-owner-membership"] == {
        "knowledge.read",
        "knowledge.propose",
        "knowledge.approve",
    }
    assert bindings["l4-readonly-membership"] == {"knowledge.read", "knowledge.validate"}
    assert identity["admission"]["default_mode"] == "explicit_grant_required"

    actions = set(taxonomy["actions"])
    assert actions == {
        "knowledge.read",
        "knowledge.validate",
        "knowledge.propose",
        "knowledge.approve",
    }
    assert "knowledge.write" not in actions
    assert matrix["default_decision"] == "deny"
    assert {rule["action"] for rule in matrix["rules"]} == actions
    assert all(rule["decision"] != "allow_unconditional" for rule in matrix["rules"])


def test_personal_space_files_do_not_declare_team_space() -> None:
    names = [
        "personal-space.yaml",
        "personal-space-identity-admission.yaml",
        "personal-space-capability-taxonomy.yaml",
        "personal-space-admission-matrix.yaml",
    ]
    values = [value for name in names for value in _all_strings(_yaml(name))]

    assert "team-space" not in values
