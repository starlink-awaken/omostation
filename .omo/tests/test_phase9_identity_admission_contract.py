from __future__ import annotations

from pathlib import Path

import yaml


OMO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OMO_ROOT.parent


def _load_workspace_yaml(rel_path: str) -> dict:
    return yaml.safe_load((WORKSPACE_ROOT / rel_path).read_text(encoding="utf-8")) or {}


def test_identity_admission_schema_declares_actor_membership_anchor() -> None:
    schema = _load_workspace_yaml("spaces/_schema/space-identity-admission.schema.yaml")

    assert schema["apiVersion"] == "omo/v1"
    assert schema["kind"] == "SpaceIdentityAdmissionSchema"
    assert schema["identity_anchor"] == "actor_space_membership"
    assert schema["required"] == [
        "apiVersion",
        "kind",
        "id",
        "space_ref",
        "identity_anchor",
        "actors",
        "memberships",
        "capability_bindings",
        "admission",
    ]
    assert schema["actor_types"] == [
        "human",
        "agent",
        "service",
    ]
    assert schema["membership_required"] == [
        "id",
        "actor_ref",
        "space_ref",
        "roles",
    ]
    assert schema["admission_required"] == [
        "decision_scope",
        "subject_binding",
        "default_mode",
    ]


def test_system_space_identity_contract_is_linked_and_concrete() -> None:
    manifest = _load_workspace_yaml("spaces/system-space.yaml")
    contract = _load_workspace_yaml("spaces/system-space-identity-admission.yaml")

    assert "spaces/system-space-identity-admission.yaml" in manifest["policy_refs"]
    assert ".omo/plans/phase9-wave3-execution-plan.md" in manifest["policy_refs"]

    assert contract["apiVersion"] == "omo/v1"
    assert contract["kind"] == "SpaceIdentityAdmission"
    assert contract["space_ref"] == "spaces/system-space.yaml"
    assert contract["identity_anchor"] == "actor_space_membership"

    actor_ids = [entry["id"] for entry in contract["actors"]]
    membership_ids = [entry["id"] for entry in contract["memberships"]]
    capability_ids = [entry["id"] for entry in contract["capability_bindings"]]

    assert "system-operator" in actor_ids
    assert "automation-agent" in actor_ids
    assert "system-governor-membership" in membership_ids
    assert "automation-runtime-membership" in membership_ids
    assert "governance-admin" in capability_ids
    assert "runtime-observer" in capability_ids

    assert contract["admission"] == {
        "decision_scope": "cross_root_action",
        "subject_binding": "membership",
        "default_mode": "explicit_grant_required",
    }

    for rel_path in manifest["policy_refs"]:
        assert (WORKSPACE_ROOT / rel_path).exists(), rel_path


def test_system_space_identity_contract_links_taxonomy_and_matrix() -> None:
    schema = _load_workspace_yaml("spaces/_schema/space-identity-admission.schema.yaml")
    contract = _load_workspace_yaml("spaces/system-space-identity-admission.yaml")
    taxonomy = _load_workspace_yaml("spaces/system-space-capability-taxonomy.yaml")
    matrix = _load_workspace_yaml("spaces/system-space-admission-matrix.yaml")

    assert schema["capability_taxonomy_ref_field"] == "capability_taxonomy_ref"
    assert schema["admission_matrix_ref_field"] == "admission_matrix_ref"

    assert contract["capability_taxonomy_ref"] == "spaces/system-space-capability-taxonomy.yaml"
    assert contract["admission_matrix_ref"] == "spaces/system-space-admission-matrix.yaml"

    assert taxonomy["apiVersion"] == "omo/v1"
    assert taxonomy["kind"] == "SpaceCapabilityTaxonomy"
    assert taxonomy["actions"] == [
        "governance.write",
        "space.membership.manage",
        "data.read",
        "runtime.observe",
        "runtime.mutate",
        "project.dispatch",
    ]

    assert matrix["apiVersion"] == "omo/v1"
    assert matrix["kind"] == "SpaceAdmissionMatrix"

    matrix_rules = {rule["action"]: rule for rule in matrix["rules"]}
    assert matrix_rules["governance.write"] == {
        "action": "governance.write",
        "required_capabilities": ["governance.write"],
        "decision": "allow",
    }
    assert matrix_rules["runtime.mutate"] == {
        "action": "runtime.mutate",
        "required_capabilities": ["runtime.mutate"],
        "decision": "conditional_approval",
    }
    assert matrix_rules["project.dispatch"] == {
        "action": "project.dispatch",
        "required_capabilities": ["project.dispatch"],
        "decision": "conditional_approval",
    }


def test_worker_envelope_binds_action_and_membership_to_admission_contract() -> None:
    template = _load_workspace_yaml(".omo/workers/templates/worker-task-envelope.yaml")
    envelope = _load_workspace_yaml(".omo/workers/runs/phase9-wave3-identity-admission-envelope.yaml")

    assert template["execution_context"] == {
        "space_ref": "<space manifest path>",
        "membership_ref": "<space membership id>",
        "action": "<capability action>",
        "admission_contract_ref": "<identity/admission contract path>",
        "required_capabilities": ["<capability action>"],
        "decision_mode": "<allow|conditional_approval|deny>",
    }

    assert envelope["execution_context"] == {
        "space_ref": "spaces/system-space.yaml",
        "membership_ref": "system-governor-membership",
        "action": "project.dispatch",
        "admission_contract_ref": "spaces/system-space-identity-admission.yaml",
        "required_capabilities": ["project.dispatch"],
        "decision_mode": "conditional_approval",
    }
