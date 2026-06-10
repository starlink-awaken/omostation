from __future__ import annotations

import sys
from pathlib import Path

import yaml

import pytest

from omo.omo_governance import (
    approve_truth_mutation,
    apply_truth_mutation,
    list_truth_mutations,
    main as omo_governance_main,
    propose_truth_mutation,
)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_propose_truth_mutation_writes_proposal_record(tmp_path: Path):
    target = tmp_path / ".omo" / "state" / "system.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("next_milestone: planning\n", encoding="utf-8")

    proposal = propose_truth_mutation(
        tmp_path,
        {
            "id": "p-001",
            "title": "Advance Wave 1 milestone",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/state/system.yaml",
            },
            "changes": {
                "set": {
                    "next_milestone": "Phase 6 Wave 1 runtime core",
                }
            },
            "change_summary": ["advance next milestone for ratified Wave 1"],
            "impact": {
                "blast_radius": "medium",
                "touches": [".omo/state/system.yaml"],
            },
            "verification_plan": ["python3 scripts/sync_omo_state.py --omo-dir .omo"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-001",
        },
        now="2026-05-31T07:00:00Z",
    )

    assert proposal["status"] == "proposed"
    proposal_path = tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "p-001.yaml"
    assert proposal_path.exists()

    payload = _load_yaml(proposal_path)
    assert payload["id"] == "p-001"
    assert payload["status"] == "proposed"
    assert payload["requested_at"] == "2026-05-31T07:00:00Z"
    assert payload["target"]["ref"] == ".omo/state/system.yaml"
    assert payload["changes"]["set"]["next_milestone"] == "Phase 6 Wave 1 runtime core"


def test_apply_truth_mutation_rejects_unapproved_proposal(tmp_path: Path):
    target = tmp_path / ".omo" / "state" / "system.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("next_milestone: planning\n", encoding="utf-8")

    propose_truth_mutation(
        tmp_path,
        {
            "id": "p-002",
            "title": "Advance Wave 1 milestone",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/state/system.yaml",
            },
            "changes": {
                "set": {
                    "next_milestone": "Phase 6 Wave 1 runtime core",
                }
            },
            "change_summary": ["advance next milestone for ratified Wave 1"],
            "impact": {
                "blast_radius": "medium",
                "touches": [".omo/state/system.yaml"],
            },
            "verification_plan": ["python3 scripts/sync_omo_state.py --omo-dir .omo"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-002",
        },
        now="2026-05-31T07:00:00Z",
    )

    with pytest.raises(ValueError, match="approved"):
        apply_truth_mutation(tmp_path, "p-002", now="2026-05-31T07:05:00Z")


def test_approved_truth_mutation_applies_yaml_patch_and_writes_audit_artifacts(tmp_path: Path):
    target = tmp_path / ".omo" / "state" / "system.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("next_milestone: planning\nphase_status: pending\n", encoding="utf-8")

    propose_truth_mutation(
        tmp_path,
        {
            "id": "p-003",
            "title": "Advance Wave 1 milestone",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/state/system.yaml",
            },
            "changes": {
                "set": {
                    "next_milestone": "Phase 6 Wave 1 runtime core",
                    "phase_status": "in_progress",
                }
            },
            "change_summary": ["advance next milestone for ratified Wave 1"],
            "impact": {
                "blast_radius": "medium",
                "touches": [".omo/state/system.yaml"],
            },
            "verification_plan": ["python3 scripts/sync_omo_state.py --omo-dir .omo"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-003",
        },
        now="2026-05-31T07:00:00Z",
    )
    approve_truth_mutation(
        tmp_path,
        "p-003",
        approver="copilot-cli",
        now="2026-05-31T07:02:00Z",
    )

    applied = apply_truth_mutation(tmp_path, "p-003", now="2026-05-31T07:05:00Z")

    target_payload = _load_yaml(target)
    assert target_payload["next_milestone"] == "Phase 6 Wave 1 runtime core"
    assert target_payload["phase_status"] == "in_progress"
    assert applied["status"] == "verified"

    apply_artifact = tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "p-003" / "apply.yaml"
    verify_artifact = tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "p-003" / "verify.yaml"
    assert apply_artifact.exists()
    assert verify_artifact.exists()

    apply_payload = _load_yaml(apply_artifact)
    verify_payload = _load_yaml(verify_artifact)
    assert apply_payload["trace_id"] == "trace-003"
    assert apply_payload["changed_keys"] == ["next_milestone", "phase_status"]
    assert verify_payload["status"] == "verified"


def test_propose_truth_mutation_rejects_secret_like_values(tmp_path: Path):
    with pytest.raises(ValueError, match="secret-like"):
        propose_truth_mutation(
            tmp_path,
            {
                "id": "p-004",
                "title": "Bad secret proposal",
                "operation_level": "L3",
                "requested_by": "copilot-cli",
                "target": {
                    "plane": "truth",
                    "kind": "yaml_file",
                    "ref": ".omo/state/system.yaml",
                },
                "changes": {
                    "set": {
                        "notes": "token=abc123",
                    }
                },
                "change_summary": ["do not store password=hunter2 here"],
                "impact": {
                    "blast_radius": "high",
                    "touches": [".omo/state/system.yaml"],
                },
                "verification_plan": ["python3 scripts/sync_omo_state.py --omo-dir .omo"],
                "rollback_plan": ["restore prior YAML snapshot"],
                "secret_refs": [],
                "trace_id": "trace-004",
            },
            now="2026-05-31T07:10:00Z",
        )


def test_list_truth_mutations_returns_status_summary(tmp_path: Path):
    propose_truth_mutation(
        tmp_path,
        {
            "id": "p-005",
            "title": "First proposal",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/state/system.yaml",
            },
            "changes": {"set": {"next_milestone": "Wave 1"}},
            "change_summary": ["seed milestone"],
            "impact": {"blast_radius": "low", "touches": [".omo/state/system.yaml"]},
            "verification_plan": ["sync state"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-005",
        },
        now="2026-05-31T07:15:00Z",
    )
    propose_truth_mutation(
        tmp_path,
        {
            "id": "p-006",
            "title": "Second proposal",
            "operation_level": "L3",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/goals/current.yaml",
            },
            "changes": {"set": {"current_wave": 2}},
            "change_summary": ["advance wave"],
            "impact": {"blast_radius": "high", "touches": [".omo/goals/current.yaml"]},
            "verification_plan": ["sync state"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-006",
        },
        now="2026-05-31T07:16:00Z",
    )

    rows = list_truth_mutations(tmp_path)

    assert rows == [
        {"id": "p-005", "status": "proposed", "operation_level": "L2", "target_ref": ".omo/state/system.yaml"},
        {"id": "p-006", "status": "proposed", "operation_level": "L3", "target_ref": ".omo/goals/current.yaml"},
    ]


def test_governance_cli_lists_proposals(tmp_path: Path, monkeypatch, capsys):
    propose_truth_mutation(
        tmp_path,
        {
            "id": "p-007",
            "title": "CLI proposal",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/state/system.yaml",
            },
            "changes": {"set": {"next_milestone": "Wave 1"}},
            "change_summary": ["seed milestone"],
            "impact": {"blast_radius": "low", "touches": [".omo/state/system.yaml"]},
            "verification_plan": ["sync state"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-007",
        },
        now="2026-05-31T07:20:00Z",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo-governance", "list"])

    assert omo_governance_main() == 0
    output = capsys.readouterr().out
    assert "p-007" in output
    assert "proposed" in output


def test_governance_cli_apply_executes_approved_proposal(tmp_path: Path, monkeypatch):
    target = tmp_path / ".omo" / "state" / "system.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("next_milestone: planning\n", encoding="utf-8")

    propose_truth_mutation(
        tmp_path,
        {
            "id": "p-008",
            "title": "CLI apply",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "plane": "truth",
                "kind": "yaml_file",
                "ref": ".omo/state/system.yaml",
            },
            "changes": {"set": {"next_milestone": "Phase 6 Wave 1 runtime core"}},
            "change_summary": ["advance milestone"],
            "impact": {"blast_radius": "low", "touches": [".omo/state/system.yaml"]},
            "verification_plan": ["sync state"],
            "rollback_plan": ["restore prior YAML snapshot"],
            "secret_refs": [],
            "trace_id": "trace-008",
        },
        now="2026-05-31T07:21:00Z",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo-governance", "approve", "p-008", "--approver", "copilot-cli", "--now", "2026-05-31T07:22:00Z"],
    )
    assert omo_governance_main() == 0

    monkeypatch.setattr(sys, "argv", ["omo-governance", "apply", "p-008", "--now", "2026-05-31T07:23:00Z"])
    assert omo_governance_main() == 0

    payload = _load_yaml(target)
    assert payload["next_milestone"] == "Phase 6 Wave 1 runtime core"
