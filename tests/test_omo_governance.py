from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml
from omo.omo_governance import (
    apply_truth_mutation,
    approve_truth_mutation,
    list_truth_mutations,
    propose_truth_mutation,
)
from omo.omo_governance import (
    main as omo_governance_main,
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
    proposal_path = (
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "p-001.yaml"
    )
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


def test_approved_truth_mutation_applies_yaml_patch_and_writes_audit_artifacts(
    tmp_path: Path,
):
    target = tmp_path / ".omo" / "state" / "system.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "next_milestone: planning\nphase_status: pending\n", encoding="utf-8"
    )

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

    apply_artifact = (
        tmp_path
        / ".omo"
        / "_delivery"
        / "task-center"
        / "proposals"
        / "p-003"
        / "apply.yaml"
    )
    verify_artifact = (
        tmp_path
        / ".omo"
        / "_delivery"
        / "task-center"
        / "proposals"
        / "p-003"
        / "verify.yaml"
    )
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
                "verification_plan": [
                    "python3 scripts/sync_omo_state.py --omo-dir .omo"
                ],
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
        {
            "id": "p-005",
            "status": "proposed",
            "operation_level": "L2",
            "target_ref": ".omo/state/system.yaml",
        },
        {
            "id": "p-006",
            "status": "proposed",
            "operation_level": "L3",
            "target_ref": ".omo/goals/current.yaml",
        },
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
        [
            "omo-governance",
            "approve",
            "p-008",
            "--approver",
            "copilot-cli",
            "--now",
            "2026-05-31T07:22:00Z",
        ],
    )
    assert omo_governance_main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        ["omo-governance", "apply", "p-008", "--now", "2026-05-31T07:23:00Z"],
    )
    assert omo_governance_main() == 0

    payload = _load_yaml(target)
    assert payload["next_milestone"] == "Phase 6 Wave 1 runtime core"


def test_governance_cli_propose_accepts_multi_document_yaml_file(
    tmp_path: Path, monkeypatch
):
    target = tmp_path / ".omo" / "state" / "system.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("next_milestone: planning\n", encoding="utf-8")
    proposal_file = tmp_path / "proposal.yaml"
    proposal_file.write_text(
        "---\nstatus: draft\nowner: governance\n---\n---\n"
        "id: p-008b\n"
        "title: CLI multi doc\n"
        "operation_level: L2\n"
        "requested_by: copilot-cli\n"
        "target:\n"
        "  plane: truth\n"
        "  kind: yaml_file\n"
        "  ref: .omo/state/system.yaml\n"
        "changes:\n"
        "  set:\n"
        "    next_milestone: Phase 6 Wave 1 runtime core\n"
        "change_summary:\n"
        "  - advance milestone\n"
        "impact:\n"
        "  blast_radius: low\n"
        "  touches:\n"
        "    - .omo/state/system.yaml\n"
        "verification_plan:\n"
        "  - sync state\n"
        "rollback_plan:\n"
        "  - restore prior YAML snapshot\n"
        "secret_refs: []\n"
        "trace_id: trace-008b\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo-governance",
            "propose",
            str(proposal_file),
            "--now",
            "2026-05-31T07:21:00Z",
        ],
    )

    assert omo_governance_main() == 0
    payload = _load_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "p-008b.yaml"
    )
    assert payload["status"] == "proposed"
    assert payload["target"]["ref"] == ".omo/state/system.yaml"


def test_governance_cli_ingress_goal_writes_goal_and_artifact(
    tmp_path: Path, monkeypatch, capsys
):
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text("phase: 44\ngoals: []\n", encoding="utf-8")

    extra_file = tmp_path / "goal-extra.yaml"
    extra_file.write_text("vector: V2\nappetite: 1 week\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    rc = omo_governance_main(
        [
            "ingress-goal",
            "BET-9001",
            "统一持久化 broker",
            "Bet: 统一持久化 broker (Appetite: 1 week)",
            "--ingress-plane",
            "projects/c2g",
            "--source-ref",
            "c2g:bet:BET-9001",
            "--extra-file",
            str(extra_file),
            "--now",
            "2026-06-18T03:00:00Z",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "ingress goal created BET-9001" in captured.out
    payload = _load_yaml(goals_file)
    assert any(goal["id"] == "BET-9001" for goal in payload["goals"])
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "goals"
        / "BET-9001.yaml"
    )
    assert artifact["ingress_plane"] == "projects/c2g"


def test_governance_cli_ingress_task_writes_planned_task_and_artifact(
    tmp_path: Path, monkeypatch, capsys
):
    (tmp_path / ".omo").mkdir(parents=True, exist_ok=True)
    task_file = tmp_path / "task.yaml"
    task_file.write_text(
        yaml.dump(
            {
                "id": "IMPORTED-CLI-1",
                "title": "CLI broker 落任务",
                "status": "candidate",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码", "测试"],
                "imported_via": "projects/c2g",
                "context_uri": "bos://memory/specs/spec.md#IMPORTED-CLI-1",
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "governance_refs": [
                    ".omo/standards/omo-governance-surfaces.md",
                ],
                "entry_gate": [],
                "evidence_required": ["pytest"],
                "test_plan": ["uv run pytest"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    rc = omo_governance_main(
        [
            "ingress-task",
            str(task_file),
            "--ingress-plane",
            "projects/c2g",
            "--source-ref",
            "c2g:bridge-import:IMPORTED-CLI-1",
            "--now",
            "2026-06-18T03:01:00Z",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "ingress task created IMPORTED-CLI-1" in captured.out
    payload = _load_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "IMPORTED-CLI-1.yaml"
    )
    assert payload["metadata"]["broker"] == "projects/omo/src/omo/omo_ingress.py"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "IMPORTED-CLI-1.yaml"
    )
    assert artifact["task_ref"] == ".omo/tasks/planned/IMPORTED-CLI-1.yaml"


def test_governance_cli_ingress_debt_upserts_debt_and_artifact(
    tmp_path: Path, monkeypatch, capsys
):
    (tmp_path / ".omo").mkdir(parents=True, exist_ok=True)
    debt_file = tmp_path / "debt.yaml"
    debt_file.write_text(
        yaml.dump(
            {
                "id": "DEBT-CLI-1",
                "title": "broker debt",
                "description": "from governance cli",
                "severity": "medium",
                "source": "aetherforge-gateway",
                "remediation": "fix it",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    rc = omo_governance_main(
        [
            "ingress-debt",
            str(debt_file),
            "--ingress-plane",
            "projects/aetherforge",
            "--source-ref",
            "aetherforge:budget:cli-1",
            "--now",
            "2026-06-18T03:02:00Z",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "ingress debt upserted DEBT-CLI-1" in captured.out
    payload = _load_yaml(tmp_path / ".omo" / "debt" / "items" / "DEBT-CLI-1.yaml")
    assert payload["lifecycle_state"] == "identified"
    assert payload["occurrence_count"] == 1
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "debts"
        / "DEBT-CLI-1.yaml"
    )
    assert artifact["debt_ref"] == ".omo/debt/items/DEBT-CLI-1.yaml"


def test_governance_cli_ingress_uses_workspace_root_not_subrepo_cwd(
    tmp_path: Path, monkeypatch, capsys
):
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text("phase: 44\ngoals: []\n", encoding="utf-8")
    subrepo = tmp_path / "projects" / "omo"
    subrepo.mkdir(parents=True, exist_ok=True)

    monkeypatch.chdir(subrepo)
    rc = omo_governance_main(
        [
            "ingress-goal",
            "BET-ROOT-1",
            "root write",
            "Bet: write to workspace root",
            "--ingress-plane",
            "projects/c2g",
            "--source-ref",
            "c2g:bet:BET-ROOT-1",
            "--now",
            "2026-06-18T03:03:00Z",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "ingress goal created BET-ROOT-1" in captured.out
    payload = _load_yaml(goals_file)
    assert any(goal["id"] == "BET-ROOT-1" for goal in payload["goals"])
    assert not (subrepo / ".omo" / "_delivery" / "ingress" / "registry.yaml").exists()
