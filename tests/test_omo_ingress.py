from __future__ import annotations

import json
import subprocess
import sys
import time
from types import SimpleNamespace
import yaml
from pathlib import Path

import pytest

from omo.omo_ingress import (
    archive_done_task,
    complete_task,
    create_goal,
    create_audit_report,
    create_blocked_task,
    create_knowledge_doc,
    create_planned_task,
    create_skill_manifest,
    create_standard_doc,
    execute_controlled_task,
    get_controlled_process_status,
    restart_controlled_task,
    normalize_legacy_planned_task,
    promote_task_to_active,
    record_task_contract_request,
    record_task_consensus,
    remove_debt_item,
    repair_task_promotion_approval,
    revert_task_to_planned,
    request_task_promotion_approval,
    route_self_evolution_to_remediation,
    start_controlled_task,
    stop_controlled_task,
    update_done_task_evidence_paths,
    update_governance_overlay_state,
    update_goal_progress,
    upsert_debt_item,
    write_capability_registry_bundle,
    write_system_projection_fields,
    write_manual_capabilities,
    write_discovery_registry,
    write_task_center_control_decision,
    write_task_center_freshness,
    write_usage_accounting,
    yield_task_to_planned,
)


OMO_SRC = Path(__file__).resolve().parents[1] / "src"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_create_goal_writes_current_goal_and_delivery_artifact(tmp_path: Path) -> None:
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text(
        yaml.dump({"phase": 44, "goals": []}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    created = create_goal(
        tmp_path / ".omo",
        goal_id="BET-1234",
        title="治理入口收敛",
        description="Bet: 治理入口收敛 (Appetite: 1 week)",
        ingress_plane="projects/c2g",
        source_ref="c2g:bet:BET-1234",
        extra_fields={"vector": "V2", "appetite": "1 week"},
        now="2026-06-18T02:00:00Z",
    )

    payload = _load_yaml(goals_file)
    assert created["id"] == "BET-1234"
    assert any(goal["id"] == "BET-1234" for goal in payload["goals"])
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "goals"
        / "BET-1234.yaml"
    )
    assert artifact["kind"] == "goal_created"
    assert artifact["ingress_plane"] == "projects/c2g"
    assert (
        artifact["artifact_ref"] == "runtime/omo/_delivery/ingress/goals/BET-1234.yaml"
    )
    assert artifact["broker_ref"] == "projects/omo/src/omo/omo_ingress.py"
    assert artifact["retention_mode"] == "manual_archive"
    assert artifact["lifecycle_state"] == "active"
    audit_log = (
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "ingress-audit.jsonl"
    )
    assert audit_log.exists()
    mutation_log = tmp_path / "runtime" / "omo" / "change-log" / "mutations.jsonl"
    mutation = _load_jsonl(mutation_log)[0]
    assert mutation["action"] == "create_goal"
    assert mutation["target"] == ".omo/goals/current.yaml#BET-1234"
    assert (
        mutation["artifact_ref"] == "runtime/omo/_delivery/ingress/goals/BET-1234.yaml"
    )


def test_create_planned_task_validates_and_writes_artifacts(tmp_path: Path) -> None:
    task_data = {
        "id": "IMPORTED-123456",
        "title": "收敛 broker 入口",
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": ["pitch.md"],
        "deliverables": ["代码", "测试"],
        "imported_via": "projects/c2g",
        "context_uri": "bos://memory/pitches/pitch.md#IMPORTED-123456",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
        "entry_gate": [],
        "evidence_required": ["pytest"],
        "test_plan": ["uv run pytest"],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "metadata": {},
    }

    created = create_planned_task(
        tmp_path / ".omo",
        task_data=task_data,
        ingress_plane="projects/c2g",
        source_ref="c2g:bridge-import:IMPORTED-123456",
        now="2026-06-18T02:01:00Z",
    )

    task_file = tmp_path / ".omo" / "tasks" / "planned" / "IMPORTED-123456.yaml"
    assert task_file.exists()
    payload = _load_yaml(task_file)
    assert created["id"] == "IMPORTED-123456"
    assert payload["metadata"]["broker"] == "projects/omo/src/omo/omo_ingress.py"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "IMPORTED-123456.yaml"
    )
    assert artifact["kind"] == "planned_task_created"
    assert artifact["task_ref"] == ".omo/tasks/planned/IMPORTED-123456.yaml"
    assert (
        artifact["artifact_ref"]
        == "runtime/omo/_delivery/ingress/tasks/IMPORTED-123456.yaml"
    )
    assert artifact["broker_ref"] == "projects/omo/src/omo/omo_ingress.py"
    assert artifact["retention_mode"] == "manual_archive"
    assert artifact["lifecycle_state"] == "active"
    mutation_log = tmp_path / "runtime" / "omo" / "change-log" / "mutations.jsonl"
    mutation = _load_jsonl(mutation_log)[0]
    assert mutation["action"] == "create_planned_task"
    assert mutation["target"] == ".omo/tasks/planned/IMPORTED-123456.yaml"
    assert (
        mutation["artifact_ref"]
        == "runtime/omo/_delivery/ingress/tasks/IMPORTED-123456.yaml"
    )


def test_create_planned_task_rejects_invalid_planned_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid planned task"):
        create_planned_task(
            tmp_path / ".omo",
            task_data={"id": "BAD-1", "title": "bad"},
            ingress_plane="projects/c2g",
        )


def test_write_capability_registry_bundle_writes_bundle_and_artifact(
    tmp_path: Path,
) -> None:
    artifact = write_capability_registry_bundle(
        tmp_path / ".omo",
        bundle={
            "index_content": "# Capability registry\n",
            "registries": {
                "projects-capabilities.yaml": {"capabilities": [{"id": "demo.cap"}]},
                "system-packages.yaml": {"packages": [{"id": "demo"}]},
            },
        },
        actor="projects/omo/tests",
        source_ref="tests:capability:bundle",
        now="2026-06-22T03:00:00Z",
    )

    assert (tmp_path / ".omo" / "capabilities" / "INDEX.md").exists()
    assert (tmp_path / ".omo" / "capabilities" / "projects-capabilities.yaml").exists()
    assert artifact["kind"] == "capability_registry_bundle_written"
    assert ".omo/capabilities/INDEX.md" in artifact["registry_refs"]
    bundle_artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "capabilities"
        / "bundle-2026-06-22T03-00-00Z.yaml"
    )
    assert bundle_artifact["kind"] == "capability_registry_bundle_written"
    assert bundle_artifact["actor"] == "projects/omo/tests"


def test_write_manual_capabilities_writes_registry_and_artifact(tmp_path: Path) -> None:
    payload = {
        "capabilities": [
            {
                "id": "manual.demo",
                "type": "tool",
                "protocol": "cli",
                "entrypoint": "bin/demo",
                "lifecycle": "active",
                "metadata": {
                    "description": "demo",
                    "tags": ["demo"],
                    "scenario_tags": ["demo"],
                },
            }
        ]
    }

    written = write_manual_capabilities(
        tmp_path / ".omo",
        payload=payload,
        actor="projects/omo/tests",
        source_ref="tests:capability:manual",
        now="2026-06-22T03:01:00Z",
    )

    assert written["capabilities"][0]["id"] == "manual.demo"
    registry = _load_yaml(
        tmp_path / ".omo" / "capabilities" / "manual-capabilities.yaml"
    )
    assert registry["capabilities"][0]["id"] == "manual.demo"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "capabilities"
        / "manual-capabilities-2026-06-22T03-01-00Z.yaml"
    )
    assert artifact["kind"] == "manual_capabilities_written"
    assert artifact["registry_ref"] == ".omo/capabilities/manual-capabilities.yaml"


def test_write_system_projection_fields_updates_system_and_artifact(
    tmp_path: Path,
) -> None:
    system_path = tmp_path / ".omo" / "state" / "system.yaml"
    system_path.parent.mkdir(parents=True, exist_ok=True)
    system_path.write_text(
        yaml.safe_dump({"current_phase": 42, "completed_tasks": 0}, allow_unicode=True),
        encoding="utf-8",
    )

    written = write_system_projection_fields(
        tmp_path / ".omo",
        updates={"completed_tasks": 3, "updated_at": "2026-06-22T08:00:00Z"},
        actor="projects/omo/tests",
        source_ref="tests:state:projection",
        now="2026-06-22T08:00:00Z",
        allowed_fields={"completed_tasks", "updated_at"},
    )

    assert written["current_phase"] == 42
    assert written["completed_tasks"] == 3
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "state"
        / "system-projection-2026-06-22T08-00-00Z.yaml"
    )
    assert artifact["kind"] == "system_projection_fields_written"
    assert artifact["updated_fields"] == ["completed_tasks", "updated_at"]


def test_update_done_task_evidence_paths_writes_artifact(tmp_path: Path) -> None:
    done_path = tmp_path / ".omo" / "tasks" / "done" / "TASK-DONE-2.yaml"
    done_path.parent.mkdir(parents=True, exist_ok=True)
    done_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-DONE-2",
                "title": "refresh",
                "status": "done",
                "evidence_paths": ["old.md"],
                "metadata": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = update_done_task_evidence_paths(
        tmp_path / ".omo",
        task_id="TASK-DONE-2",
        evidence_paths=["new.md", "report.md"],
        actor="projects/omo/tests",
        source_ref="tests:done:evidence-refresh",
        now="2026-06-22T03:02:00Z",
    )

    assert payload["evidence_paths"] == ["new.md", "report.md"]
    persisted = _load_yaml(done_path)
    assert persisted["metadata"]["evidence_paths_refreshed_by"] == "projects/omo/tests"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-DONE-2-evidence-refresh-2026-06-22T03-02-00Z.yaml"
    )
    assert artifact["kind"] == "done_task_evidence_paths_updated"
    assert artifact["task_ref"] == ".omo/tasks/done/TASK-DONE-2.yaml"


def test_repair_task_promotion_approval_rehydrates_missing_runtime_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "remediation" / "TASK-R.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-R",
                "title": "repair approval",
                "status": "review",
                "task_type": "governance",
                "risk_level": "L2",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["doc"],
                "assigned_to": "codex",
                "dispatch_id": "dispatch-1",
                "run_ref": "runtime/omo/_delivery/ingress/tasks/TASK-R-route.yaml",
                "approval_ref": ".omo/workers/runs/TASK-R-promotion-approval-2026-06-23T00-00-00Z.yaml",
                "review_ref": ".omo/tasks/remediation-notes/TASK-R-review.md",
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": ["gate-a"],
                "evidence_required": ["human approval"],
                "test_plan": ["uv run pytest"],
                "allowed_operation_level": "L2",
                "human_approval_required": True,
                "approval_required": True,
                "approval_state": "granted",
                "created_at": "2026-06-23T00:00:00Z",
                "started_at": "2026-06-23T00:10:00Z",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = repair_task_promotion_approval(
        tmp_path / ".omo",
        task_id="TASK-R",
        actor="projects/omo/tests",
        source_ref="tests:repair-approval",
        now="2026-06-23T01:00:00Z",
    )

    approval = _load_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-R-promotion-approval-2026-06-23T00-00-00Z.yaml"
    )
    assert (
        payload["approval_ref"]
        == ".omo/workers/runs/TASK-R-promotion-approval-2026-06-23T00-00-00Z.yaml"
    )
    assert approval["task_id"] == "TASK-R"
    assert approval["approval_status"] == "granted"
    assert approval["refs"]["task_ref"] == ".omo/tasks/remediation/TASK-R.yaml"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-R-approval-repair-2026-06-23T01-00-00Z.yaml"
    )
    assert artifact["kind"] == "task_promotion_approval_repaired"


def test_complete_task_moves_active_task_to_done_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-DONE-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text("# done evidence\n", encoding="utf-8")
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-DONE-1",
                "title": "收口 done broker",
                "status": "review",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码"],
                "assigned_to": "agent:test",
                "dispatch_id": "dispatch-1",
                "run_ref": ".omo/workers/runs/dispatch-1.yaml",
                "approval_ref": None,
                "review_ref": ".omo/workers/runs/review-1.md",
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["pytest -q"],
                "evidence_paths": ["evidence.md"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
                "started_at": "2026-06-21T06:00:00Z",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    completed = complete_task(
        tmp_path / ".omo",
        task_id="TASK-DONE-1",
        actor="projects/omo/tests",
        source_ref="tests:task:done:TASK-DONE-1",
        now="2026-06-20T03:00:00Z",
    )

    done_path = tmp_path / ".omo" / "tasks" / "done" / "TASK-DONE-1.yaml"
    assert completed["status"] == "done"
    assert completed["completed_at"] == "2026-06-20T03:00:00Z"
    assert done_path.exists()
    assert not task_path.exists()
    payload = _load_yaml(done_path)
    assert payload["metadata"]["completed_via"] == "omo task done"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-DONE-1-done-2026-06-20T03-00-00Z.yaml"
    )
    assert artifact["kind"] == "task_completed"
    assert artifact["task_ref_before"] == ".omo/tasks/active/TASK-DONE-1.yaml"
    assert artifact["task_ref_after"] == ".omo/tasks/done/TASK-DONE-1.yaml"


def test_complete_task_hydrates_missing_top_level_completed_at_from_metadata(
    tmp_path: Path,
) -> None:
    done_path = tmp_path / ".omo" / "tasks" / "done" / "TASK-DONE-HYDRATE.yaml"
    done_path.parent.mkdir(parents=True, exist_ok=True)
    done_path.write_text(
        yaml.dump(
            {
                "id": "TASK-DONE-HYDRATE",
                "title": "hydrate completion marker",
                "status": "done",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码"],
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": [],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {
                    "completed_at": "2026-06-20T07:10:00Z",
                    "completed_via": "omo task done",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    completed = complete_task(
        tmp_path / ".omo",
        task_id="TASK-DONE-HYDRATE",
        actor="projects/omo/tests",
        source_ref="tests:task:hydrate:TASK-DONE-HYDRATE",
        now="2026-06-20T07:11:00Z",
    )

    payload = _load_yaml(done_path)
    assert completed["completed_at"] == "2026-06-20T07:10:00Z"
    assert payload["completed_at"] == "2026-06-20T07:10:00Z"
    assert payload["metadata"]["completed_at"] == "2026-06-20T07:10:00Z"


def test_complete_task_rejects_invalid_done_packet(tmp_path: Path) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-BAD-DONE.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {"id": "TASK-BAD-DONE", "title": "bad", "status": "candidate"},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid completed task"):
        complete_task(
            tmp_path / ".omo",
            task_id="TASK-BAD-DONE",
            actor="projects/omo/tests",
            now="2026-06-20T03:01:00Z",
        )


def test_promote_task_to_active_moves_planned_task_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-PROMOTE-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-PROMOTE-1",
                "title": "收口 promote broker",
                "status": "pending",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码"],
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["pytest -q"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
                "started_at": "2026-06-21T06:00:00Z",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    promoted = promote_task_to_active(
        tmp_path / ".omo",
        task_id="TASK-PROMOTE-1",
        actor="projects/omo/tests",
        handoff_ref=".omo/workers/runs/TASK-PROMOTE-1-promotion-2026-06-20T04-00-00Z.yaml",
        source_ref="tests:task:promote:TASK-PROMOTE-1",
        now="2026-06-20T04:00:00Z",
    )

    active_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-PROMOTE-1.yaml"
    assert promoted["handoff_refs"] == [
        ".omo/workers/runs/TASK-PROMOTE-1-promotion-2026-06-20T04-00-00Z.yaml"
    ]
    assert active_path.exists()
    assert not task_path.exists()
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-PROMOTE-1-promote-2026-06-20T04-00-00Z.yaml"
    )
    assert artifact["kind"] == "task_promoted_to_active"
    assert artifact["task_ref_before"] == ".omo/tasks/planned/TASK-PROMOTE-1.yaml"


def test_revert_task_to_planned_moves_active_task_back_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-REVERT-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-REVERT-1",
                "title": "回滚 promote broker",
                "status": "pending",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码"],
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["pytest -q"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
                "started_at": "2026-06-21T06:00:00Z",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    reverted = revert_task_to_planned(
        tmp_path / ".omo",
        task_id="TASK-REVERT-1",
        actor="projects/omo/tests",
        source_ref="tests:task:revert:TASK-REVERT-1",
        now="2026-06-20T04:01:00Z",
    )

    planned_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-REVERT-1.yaml"
    assert reverted["id"] == "TASK-REVERT-1"
    assert planned_path.exists()
    assert not task_path.exists()
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-REVERT-1-revert-2026-06-20T04-01-00Z.yaml"
    )
    assert artifact["kind"] == "task_reverted_to_planned"
    assert artifact["task_ref_after"] == ".omo/tasks/planned/TASK-REVERT-1.yaml"


def test_create_blocked_task_writes_packet_and_ingress_artifact(tmp_path: Path) -> None:
    blocked = create_blocked_task(
        tmp_path / ".omo",
        task_data={
            "id": "TASK-BLOCKED-1",
            "title": "blocked bridge",
            "status": "blocked",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["spec.md"],
            "deliverables": ["triage packet"],
            "entry_gate": ["triage"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["triage note"],
            "test_plan": ["ratify packet"],
        },
        actor="projects/omo/tests",
        source_ref="tests:blocked:TASK-BLOCKED-1",
        now="2026-06-21T08:00:00Z",
    )

    task_path = tmp_path / ".omo" / "tasks" / "blocked" / "task-blocked-1.yaml"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-BLOCKED-1-blocked-2026-06-21T08-00-00Z.yaml"
    )
    assert blocked["id"] == "TASK-BLOCKED-1"
    assert task_path.exists()
    assert artifact["kind"] == "blocked_task_created"
    assert artifact["task_ref"] == ".omo/tasks/blocked/task-blocked-1.yaml"


def test_record_task_consensus_updates_task_handoff_refs_and_artifacts(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-CONSENSUS-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-CONSENSUS-1",
                "title": "consensus broker",
                "status": "pending",
                "task_type": "feature",
                "risk_level": "L1",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["code"],
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["user confirmation"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "metadata": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    artifact = record_task_consensus(
        tmp_path / ".omo",
        task_id="TASK-CONSENSUS-1",
        actor="projects/omo/tests",
        message="继续推进",
        source_ref="tests:consensus:TASK-CONSENSUS-1",
        now="2026-06-21T08:10:00Z",
    )

    payload = _load_yaml(task_path)
    evidence = _load_yaml(tmp_path / str(artifact["evidence_ref"]))
    assert artifact["kind"] == "task_consensus_recorded"
    assert evidence["message"] == "继续推进"
    assert str(artifact["evidence_ref"]) in payload["handoff_refs"]


def test_execute_controlled_task_runs_project_verification_and_records_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "projects" / "demo"
    project_path.mkdir(parents=True)
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-VERIFY-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-VERIFY-1",
                "title": "controlled verification",
                "description": "verify",
                "status": "in_progress",
                "task_type": "operations",
                "risk_level": "L1",
                "source_docs": ["projects/demo/README.md"],
                "deliverables": ["verification result"],
                "assigned_to": "operator",
                "dispatch_id": "dispatch-1",
                "run_ref": "runtime/dispatch-1.yaml",
                "approval_ref": None,
                "review_ref": "runtime/review-1.yaml",
                "started_at": "2026-07-15T00:00:00Z",
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["execution log"],
                "test_plan": ["printf hello"],
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "metadata": {
                    "command": f'cd "{project_path}" && printf hello',
                    "action_id": "copy-verify-command",
                    "controlled_execution": True,
                    "cockpit_only": True,
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    calls = []
    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.subprocess.run",
        lambda *args, **kwargs: (
            calls.append(kwargs)
            or SimpleNamespace(returncode=0, stdout="hello", stderr="")
        ),
    )
    artifact = execute_controlled_task(
        tmp_path / ".omo",
        task_id="TASK-VERIFY-1",
        actor="projects/omo/tests",
        timeout_seconds=1200,
        command_override=f'cd "{project_path}" && printf override',
        source_ref="tests:execute:TASK-VERIFY-1",
    )

    assert artifact["exit_code"] == 0
    assert calls[0]["timeout"] == 900
    assert artifact["log_ref"].startswith(
        "runtime/omo/_delivery/ingress/task-execution/"
    )
    assert (tmp_path / artifact["log_ref"]).read_text(encoding="utf-8") == "hello"
    payload = _load_yaml(task_path)
    assert payload["metadata"]["execution_audit"]["exit_code"] == 0
    assert (
        payload["metadata"]["execution_audit"]["command"]
        == f'cd "{project_path}" && printf override'
    )
    assert artifact["execution_ref"] in payload["handoff_refs"]


def test_execute_controlled_task_allows_configured_external_ui_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external_ui = tmp_path.parent / f"{tmp_path.name}-cockpit-ui"
    external_ui.mkdir()
    monkeypatch.setenv("COCKPIT_UI_ROOT", str(external_ui))
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-UI-VERIFY-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    command = f'cd "{external_ui}" && bun run build'
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-UI-VERIFY-1",
                "title": "external UI verification",
                "status": "in_progress",
                "task_type": "operations",
                "risk_level": "L1",
                "source_docs": ["cockpit-ui:package.json"],
                "deliverables": ["build result"],
                "assigned_to": "operator",
                "dispatch_id": "dispatch-ui-verify-1",
                "run_ref": "runtime/dispatch-ui-verify-1.yaml",
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["execution log"],
                "test_plan": [command],
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "started_at": "2026-07-28T06:00:00Z",
                "metadata": {
                    "command": command,
                    "action_id": "copy-verify-command",
                    "controlled_execution": True,
                    "cockpit_only": True,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.subprocess.run",
        lambda *args, **kwargs: (
            calls.append(kwargs)
            or SimpleNamespace(returncode=0, stdout="built", stderr="")
        ),
    )

    artifact = execute_controlled_task(
        tmp_path / ".omo",
        task_id="TASK-UI-VERIFY-1",
        actor="projects/omo/tests",
        source_ref="tests:execute:TASK-UI-VERIFY-1",
    )

    assert artifact["exit_code"] == 0
    assert calls[0]["cwd"] == external_ui.resolve()


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX-only")
def test_controlled_process_start_status_and_stop_are_audited(tmp_path: Path) -> None:
    project_path = tmp_path / "projects" / "demo"
    project_path.mkdir(parents=True)
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-START-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-START-1",
                "title": "controlled start",
                "description": "start",
                "status": "in_progress",
                "task_type": "operations",
                "risk_level": "L2",
                "source_docs": ["projects/demo/README.md"],
                "deliverables": ["service"],
                "assigned_to": "operator",
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": "approval.yaml",
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["process log"],
                "test_plan": ["sleep 30"],
                "allowed_operation_level": "L2",
                "human_approval_required": True,
                "metadata": {
                    "command": f'cd "{project_path}" && sleep 30',
                    "action_id": "copy-start-command",
                    "controlled_process": True,
                    "cockpit_only": True,
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "approval.yaml").write_text(
        "approval_status: granted\n", encoding="utf-8"
    )

    started = start_controlled_task(
        tmp_path / ".omo",
        task_id="TASK-START-1",
        actor="projects/omo/tests",
        source_ref="tests:start:TASK-START-1",
    )
    try:
        assert started["status"] == "started"
        assert (
            get_controlled_process_status(tmp_path / ".omo", task_id="TASK-START-1")[
                "status"
            ]
            == "running"
        )
        restarted = restart_controlled_task(
            tmp_path / ".omo",
            task_id="TASK-START-1",
            actor="projects/omo/tests",
            source_ref="tests:restart:TASK-START-1",
        )
        assert restarted["status"] == "started"
        assert restarted["pid"] != started["pid"]
    finally:
        stopped = stop_controlled_task(
            tmp_path / ".omo",
            task_id="TASK-START-1",
            actor="projects/omo/tests",
            source_ref="tests:stop:TASK-START-1",
        )
    assert stopped["status"] == "stopped"
    assert (
        _load_yaml(task_path)["metadata"]["execution_process"]["stopped_by"]
        == "projects/omo/tests"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX-only")
def test_controlled_process_exit_code_is_archived(tmp_path: Path) -> None:
    project_path = tmp_path / "projects" / "demo"
    project_path.mkdir(parents=True)
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-EXIT-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-EXIT-1",
                "title": "controlled exit",
                "description": "exit",
                "status": "in_progress",
                "task_type": "operations",
                "risk_level": "L1",
                "source_docs": ["projects/demo/README.md"],
                "deliverables": ["exit evidence"],
                "assigned_to": "operator",
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["exit code"],
                "test_plan": ["exit 7"],
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "metadata": {
                    "command": f'cd "{project_path}" && python -c "raise SystemExit(7)"',
                    "action_id": "copy-start-command",
                    "controlled_process": True,
                    "cockpit_only": True,
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    started = start_controlled_task(
        tmp_path / ".omo",
        task_id="TASK-EXIT-1",
        actor="projects/omo/tests",
        source_ref="tests:start:TASK-EXIT-1",
    )
    deadline = time.monotonic() + 5
    payload = _load_yaml(task_path)
    while time.monotonic() < deadline:
        payload = _load_yaml(task_path)
        process_record = payload["metadata"].get("execution_process", {})
        if process_record.get("exit_code") == 7:
            break
        time.sleep(0.05)

    assert payload["metadata"]["execution_process"]["exit_code"] == 7
    assert payload["metadata"]["execution_process"]["status"] == "exited"
    assert started["execution_ref"] in payload["handoff_refs"]


def test_execute_controlled_task_runs_structured_runtime_port_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-RUNTIME-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-RUNTIME-1",
                "title": "runtime port probe",
                "description": "probe",
                "status": "in_progress",
                "task_type": "operations",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "assigned_to": "operator",
                "dispatch_id": "dispatch-runtime-1",
                "run_ref": "runtime/dispatch-runtime-1.yaml",
                "approval_ref": None,
                "review_ref": "runtime/review-runtime-1.yaml",
                "started_at": "2026-07-15T00:00:00Z",
                "source_docs": ["projects/demo/README.md"],
                "knowledge_refs": [],
                "entry_gate": [],
                "evidence_required": ["execution log"],
                "test_plan": ["probe ports"],
                "metadata": {
                    "command": "for port in 7437 7438; do lsof ...; done",
                    "action_id": "runtime-check-ports",
                    "probe_ports": [7437, 7438],
                    "controlled_execution": True,
                    "cockpit_only": True,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(
            returncode=0 if args[2].split(":", 1)[1] == "7437" else 1,
            stdout=f"LISTEN {args[2]}" if args[2].split(":", 1)[1] == "7437" else "",
            stderr="" if args[2].split(":", 1)[1] == "7437" else "not listening",
        ),
    )
    artifact = execute_controlled_task(
        tmp_path / ".omo",
        task_id="TASK-RUNTIME-1",
        actor="projects/omo/tests",
        source_ref="tests:execute:TASK-RUNTIME-1",
    )

    assert artifact["exit_code"] == 0
    log = (tmp_path / artifact["log_ref"]).read_text(encoding="utf-8")
    assert "port=7437" in log
    assert "port=7438" in log
    assert "status=listening" in log
    assert "status=not_listening" in log


def test_write_task_center_runtime_artifacts_go_through_ingress(tmp_path: Path) -> None:
    usage = write_usage_accounting(
        tmp_path / ".omo",
        registry={
            "generated_at": "2026-06-21T08:20:00Z",
            "dispatches": {"total": 0, "workers": {}},
            "cost_by_org": [],
        },
        actor="projects/omo/tests",
        source_ref="tests:usage",
        now="2026-06-21T08:20:00Z",
    )
    freshness = write_task_center_freshness(
        tmp_path / ".omo",
        report={
            "generated_at": "2026-06-21T08:21:00Z",
            "freshness_score": 100,
            "stale_items": [],
        },
        actor="projects/omo/tests",
        source_ref="tests:freshness",
        now="2026-06-21T08:21:00Z",
    )
    control = write_task_center_control_decision(
        tmp_path / ".omo",
        artifact={
            "generated_at": "2026-06-21T08:22:00Z",
            "decision": "allow",
            "reasons": ["within_budget_and_fresh"],
        },
        actor="projects/omo/tests",
        source_ref="tests:control",
        now="2026-06-21T08:22:00Z",
    )

    assert usage["kind"] == "task_center_usage_accounting_written"
    assert freshness["kind"] == "task_center_freshness_written"
    assert control["kind"] == "task_center_control_decision_written"
    assert (
        tmp_path / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml"
    ).exists()
    assert (
        tmp_path / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml"
    ).exists()
    assert (
        tmp_path / ".omo" / "_delivery" / "task-center" / "control" / "current.yaml"
    ).exists()


def test_update_governance_overlay_state_writes_truth_control_and_artifact(
    tmp_path: Path,
) -> None:
    artifact = update_governance_overlay_state(
        tmp_path / ".omo",
        roadmap={"items": [{"id": "GOV-M1", "status": "in_progress"}]},
        control={"current_milestone": "GOV-M1", "next_milestone": None},
        actor="projects/omo/tests",
        source_ref="tests:overlay",
        now="2026-06-21T08:30:00Z",
    )

    assert artifact["kind"] == "governance_overlay_state_updated"
    assert (
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml"
    ).exists()
    assert (
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml"
    ).exists()


def test_create_skill_manifest_writes_truth_and_ingress_artifact(
    tmp_path: Path,
) -> None:
    manifest = create_skill_manifest(
        tmp_path / ".omo",
        manifest={
            "id": "skill.review.refresh",
            "title": "Review refresh skill",
            "worker_bridge": "mockworker",
            "source_docs": ["spec.md"],
            "deliverables": ["artifact.md"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
        },
        actor="projects/omo/tests",
        source_ref="tests:skill-manifest",
        now="2026-06-21T09:00:00Z",
    )

    assert manifest["id"] == "skill.review.refresh"
    assert (
        tmp_path
        / ".omo"
        / "_truth"
        / "task-center"
        / "skills"
        / "skill.review.refresh.yaml"
    ).exists()
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "task-center"
        / "skills"
        / "skill.review.refresh.yaml"
    )
    assert artifact["kind"] == "skill_manifest_written"


def test_write_discovery_registry_writes_truth_and_ingress_artifact(
    tmp_path: Path,
) -> None:
    registry = write_discovery_registry(
        tmp_path / ".omo",
        registry={
            "entries": [{"blueprint_id": "BP-ALPHA", "title": "Alpha"}],
            "blueprints": {"BP-ALPHA": {"title": "Alpha"}},
        },
        actor="projects/omo/tests",
        source_ref="tests:discovery-registry",
        now="2026-06-21T09:10:00Z",
    )

    assert registry["entries"][0]["blueprint_id"] == "BP-ALPHA"
    assert (
        tmp_path / ".omo" / "_truth" / "task-center" / "discovery-registry.yaml"
    ).exists()
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "task-center"
        / "discovery"
        / "discovery-registry-2026-06-21T09-10-00Z.yaml"
    )
    assert artifact["kind"] == "discovery_registry_written"


def test_request_task_promotion_approval_updates_planned_task_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-APPROVAL-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-APPROVAL-1",
                "title": "promotion approval broker",
                "status": "candidate",
                "task_type": "feature",
                "risk_level": "L1",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["code"],
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": ["human_review"],
                "evidence_required": ["pytest -q"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L1",
                "human_approval_required": True,
                "metadata": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    updated = request_task_promotion_approval(
        tmp_path / ".omo",
        task_id="TASK-APPROVAL-1",
        actor="projects/omo/tests",
        approval_ref=".omo/workers/runs/TASK-APPROVAL-1-promotion-approval-2026-06-21T06-00-00Z.yaml",
        approval_record={
            "approval_id": "TASK-APPROVAL-1-promotion-approval-2026-06-21T06-00-00Z",
            "task_id": "TASK-APPROVAL-1",
            "approval_status": "requested",
            "approval_scope": "task.promote_apply",
        },
        proposal_ref=".omo/_truth/task-center/proposals/TASK-APPROVAL-1-promotion-approval-2026-06-21T06-00-00Z-proposal.yaml",
        source_ref="tests:task:promotion-approval:TASK-APPROVAL-1",
        now="2026-06-21T06:00:00Z",
    )

    payload = _load_yaml(task_path)
    assert (
        updated["approval_ref"]
        == ".omo/workers/runs/TASK-APPROVAL-1-promotion-approval-2026-06-21T06-00-00Z.yaml"
    )
    assert payload["approval_ref"] == updated["approval_ref"]
    approval = _load_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-APPROVAL-1-promotion-approval-2026-06-21T06-00-00Z.yaml"
    )
    assert approval["approval_status"] == "requested"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-APPROVAL-1-promotion-approval-2026-06-21T06-00-00Z.yaml"
    )
    assert artifact["kind"] == "task_promotion_approval_requested"


def test_record_task_contract_request_updates_active_task_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-CONTRACT-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-CONTRACT-1",
                "title": "contract request broker",
                "status": "in_progress",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["code"],
                "assigned_to": "agent:test",
                "dispatch_id": "dispatch-contract-1",
                "run_ref": ".omo/workers/runs/dispatch-contract-1.yaml",
                "approval_ref": None,
                "review_ref": ".omo/workers/runs/review-contract-1.md",
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["pytest -q"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
                "started_at": "2026-06-21T06:00:00Z",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    updated = record_task_contract_request(
        tmp_path / ".omo",
        task_id="TASK-CONTRACT-1",
        actor="projects/omo/tests",
        request_ref=".omo/workers/runs/TASK-CONTRACT-1-contract-request-2026-06-21T06-10-00Z.yaml",
        request_record={
            "request_id": "TASK-CONTRACT-1-contract-request-2026-06-21T06-10-00Z",
            "task_id": "TASK-CONTRACT-1",
            "deliverables": ["code", "docs"],
        },
        proposal_ref=".omo/_truth/task-center/proposals/TASK-CONTRACT-1-contract-request-2026-06-21T06-10-00Z-proposal.yaml",
        source_ref="tests:task:contract-request:TASK-CONTRACT-1",
        now="2026-06-21T06:10:00Z",
    )

    payload = _load_yaml(task_path)
    assert (
        ".omo/workers/runs/TASK-CONTRACT-1-contract-request-2026-06-21T06-10-00Z.yaml"
        in updated["handoff_refs"]
    )
    assert payload["handoff_refs"] == updated["handoff_refs"]
    request = _load_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-CONTRACT-1-contract-request-2026-06-21T06-10-00Z.yaml"
    )
    assert request["task_id"] == "TASK-CONTRACT-1"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-CONTRACT-1-contract-request-2026-06-21T06-10-00Z.yaml"
    )
    assert artifact["kind"] == "task_contract_request_recorded"


def test_route_self_evolution_to_remediation_moves_packet_and_writes_note(
    tmp_path: Path,
) -> None:
    planned_path = (
        tmp_path / ".omo" / "tasks" / "planned" / "OPC-P6-SELF-EVOLUTION-demo.yaml"
    )
    planned_path.parent.mkdir(parents=True, exist_ok=True)
    planned_path.write_text(
        yaml.dump(
            {
                "id": "OPC-P6-SELF-EVOLUTION-demo",
                "title": "Self evolution demo",
                "status": "candidate",
                "task_type": "governance",
                "risk_level": "L1",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["review note"],
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": ".omo/workers/runs/OPC-P6-SELF-EVOLUTION-demo-promotion-approval.yaml",
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": ["human_review"],
                "evidence_required": ["approval granted"],
                "test_plan": [
                    "python3 scripts/omo/omo_worker.py task approval-queue-status --omo-dir .omo"
                ],
                "allowed_operation_level": "L1",
                "human_approval_required": True,
                "approval_required": True,
                "approval_state": "awaiting_human",
                "metadata": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    routed = route_self_evolution_to_remediation(
        tmp_path / ".omo",
        task_id="OPC-P6-SELF-EVOLUTION-demo",
        actor="projects/omo/tests",
        review_note_body="# review\n\nroute to remediation\n",
        source_ref="tests:self-evolution-route:OPC-P6-SELF-EVOLUTION-demo",
        now="2026-06-21T01:00:00Z",
    )

    remediation_path = (
        tmp_path / ".omo" / "tasks" / "remediation" / "OPC-P6-SELF-EVOLUTION-demo.yaml"
    )
    review_note_path = (
        tmp_path
        / ".omo"
        / "tasks"
        / "remediation-notes"
        / "OPC-P6-SELF-EVOLUTION-demo-review.md"
    )
    artifact_path = (
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "OPC-P6-SELF-EVOLUTION-demo-route-self-evolution-2026-06-21T01-00-00Z.yaml"
    )

    assert routed["status"] == "review"
    assert remediation_path.exists()
    assert review_note_path.exists()
    assert not planned_path.exists()
    payload = _load_yaml(remediation_path)
    assert payload["assigned_to"] == "projects/omo/tests"
    assert (
        payload["review_note"]
        == ".omo/tasks/remediation-notes/OPC-P6-SELF-EVOLUTION-demo-review.md"
    )
    assert payload["approval_state"] == "granted"
    artifact = _load_yaml(artifact_path)
    assert artifact["kind"] == "self_evolution_routed_to_remediation"
    assert (
        artifact["task_ref_after"]
        == ".omo/tasks/remediation/OPC-P6-SELF-EVOLUTION-demo.yaml"
    )


def test_yield_task_to_planned_moves_active_task_back_to_candidate_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-YIELD-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-YIELD-1",
                "title": "收口 yield broker",
                "status": "in_progress",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码"],
                "assigned_to": "agent:test",
                "dispatch_id": "dispatch-yield-1",
                "run_ref": ".omo/workers/runs/dispatch-yield-1.yaml",
                "approval_ref": None,
                "review_ref": ".omo/workers/runs/review-yield-1.md",
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": ["pytest -q"],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    yielded = yield_task_to_planned(
        tmp_path / ".omo",
        task_id="TASK-YIELD-1",
        actor="projects/omo/tests",
        reason="need ideation reset",
        source_ref="tests:task:yield:TASK-YIELD-1",
        now="2026-06-20T05:00:00Z",
    )

    planned_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-YIELD-1.yaml"
    assert yielded["status"] == "candidate"
    assert planned_path.exists()
    assert not task_path.exists()
    payload = _load_yaml(planned_path)
    assert payload["assigned_to"] is None
    assert payload["dispatch_id"] is None
    assert payload["run_ref"] is None
    assert payload["review_ref"] is None
    assert payload["metadata"]["yield_reason"] == "need ideation reset"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-YIELD-1-yield-2026-06-20T05-00-00Z.yaml"
    )
    assert artifact["kind"] == "task_yielded_to_planned"
    assert artifact["task_ref_before"] == ".omo/tasks/active/TASK-YIELD-1.yaml"
    assert artifact["task_ref_after"] == ".omo/tasks/planned/TASK-YIELD-1.yaml"


def test_archive_done_task_moves_done_task_to_archived_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "done" / "TASK-ARCHIVE-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-ARCHIVE-1",
                "title": "收口 archive broker",
                "status": "done",
                "task_type": "feature",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": ["spec.md"],
                "deliverables": ["代码"],
                "assigned_to": "agent:test",
                "dispatch_id": "dispatch-archive-1",
                "run_ref": ".omo/workers/runs/dispatch-archive-1.yaml",
                "approval_ref": None,
                "review_ref": ".omo/workers/runs/review-archive-1.md",
                "knowledge_refs": [],
                "handoff_refs": [],
                "entry_gate": [],
                "evidence_required": [],
                "test_plan": ["pytest -q"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {},
                "completed_at": "2026-06-20T04:59:00Z",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    archived = archive_done_task(
        tmp_path / ".omo",
        task_id="TASK-ARCHIVE-1",
        actor="projects/omo/tests",
        source_ref="tests:task:archive:TASK-ARCHIVE-1",
        now="2026-06-20T05:10:00Z",
    )

    archived_path = tmp_path / ".omo" / "tasks" / "archived" / "TASK-ARCHIVE-1.yaml"
    assert archived["status"] == "archived"
    assert archived_path.exists()
    assert not task_path.exists()
    payload = _load_yaml(archived_path)
    assert payload["archived_at"] == "2026-06-20T05:10:00Z"
    assert payload["archived_by"] == "projects/omo/tests"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-ARCHIVE-1-archive-2026-06-20T05-10-00Z.yaml"
    )
    assert artifact["kind"] == "task_archived_from_done"


def test_record_task_execution_updates_archived_done_task(tmp_path: Path) -> None:
    from omo.omo_ingress_task_lifecycle import record_task_execution

    task_path = tmp_path / ".omo" / "tasks" / "archived" / "done" / "TASK-CLOSEOUT-1.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-CLOSEOUT-1",
                "title": "归档任务 closeout",
                "status": "done",
                "task_type": "operations",
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "source_docs": ["cockpit:SystemMap"],
                "entry_gate": [],
                "evidence_required": ["log"],
                "evidence_paths": ["runtime/omo/closeout.log"],
                "deliverables": ["closeout"],
                "test_plan": ["pytest"],
                "metadata": {"command": "printf ok"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    artifact = record_task_execution(
        tmp_path / ".omo",
        task_id="TASK-CLOSEOUT-1",
        actor="projects/omo/tests",
        command="printf ok",
        exit_code=0,
        log_ref="runtime/omo/closeout.log",
        closeout_ref=".omo/_delivery/agent-workflows/runs/closeout.yaml",
        source_ref="tests:task:closeout:TASK-CLOSEOUT-1",
    )

    assert artifact["task_id"] == "TASK-CLOSEOUT-1"
    assert _load_yaml(task_path)["metadata"]["execution_audit"]["closeout_ref"] == (
        ".omo/_delivery/agent-workflows/runs/closeout.yaml"
    )
    assert artifact["task_ref"] == ".omo/tasks/archived/done/TASK-CLOSEOUT-1.yaml"


def test_create_audit_report_writes_doc_and_artifact(tmp_path: Path) -> None:
    artifact = create_audit_report(
        tmp_path / ".omo",
        filename="Fast-Track-Compaction-2026-06-20T05-20-00Z",
        title="微小价值交付聚变报告 (2026-06-20T05-20-00Z)",
        content="| Task ID | 标题 | 锚点 | 归档时间 |\n|---|---|---|---|",
        actor="projects/omo/tests",
        source_ref="tests:audit:fast-track",
        now="2026-06-20T05:20:00Z",
    )

    report_path = (
        tmp_path
        / ".omo"
        / "_knowledge"
        / "audits"
        / "Fast-Track-Compaction-2026-06-20T05-20-00Z.md"
    )
    assert report_path.exists()
    assert "微小价值交付聚变报告" in report_path.read_text(encoding="utf-8")
    assert artifact["kind"] == "audit_report_created"
    assert (
        artifact["report_ref"]
        == ".omo/_knowledge/audits/Fast-Track-Compaction-2026-06-20T05-20-00Z.md"
    )
    delivery = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "audits"
        / "Fast-Track-Compaction-2026-06-20T05-20-00Z-2026-06-20T05-20-00Z.yaml"
    )
    assert delivery["kind"] == "audit_report_created"


def test_normalize_legacy_planned_task_fills_missing_fields_and_writes_artifact(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-LEGACY-NORMALIZE.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-LEGACY-NORMALIZE",
                "title": "legacy planned packet",
                "status": "planned",
                "priority": "P2",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = normalize_legacy_planned_task(
        tmp_path / ".omo",
        task_id="TASK-LEGACY-NORMALIZE",
        actor="projects/omo/tests",
        source_ref="tests:task:legacy-normalize",
        now="2026-06-20T06:30:00Z",
    )

    payload = _load_yaml(task_path)
    assert result["action"] == "normalized"
    assert payload["status"] == "candidate"
    assert payload["assigned_to"] is None
    assert payload["dispatch_id"] is None
    assert payload["source_docs"] == [
        ".omo/tasks/planned/TASK-LEGACY-NORMALIZE.yaml#legacy-normalized"
    ]
    assert payload["test_plan"] == [
        "python3 scripts/omo_worker.py task validate --all-planned"
    ]
    assert payload["metadata"]["legacy_status"] == "planned"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-LEGACY-NORMALIZE-legacy-normalize-2026-06-20T06-30-00Z.yaml"
    )
    assert artifact["kind"] == "planned_task_legacy_normalized"


def test_normalize_legacy_planned_task_archives_terminal_packet_from_planned(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "TASK-LEGACY-DONE.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.dump(
            {
                "id": "TASK-LEGACY-DONE",
                "title": "legacy done packet",
                "status": "done",
                "completed_at": "2026-06-20T06:00:00Z",
                "priority": "P1",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = normalize_legacy_planned_task(
        tmp_path / ".omo",
        task_id="TASK-LEGACY-DONE",
        actor="projects/omo/tests",
        source_ref="tests:task:legacy-archive",
        now="2026-06-20T06:31:00Z",
    )

    archived_path = (
        tmp_path
        / ".omo"
        / "tasks"
        / "archived"
        / "legacy-normalized"
        / "TASK-LEGACY-DONE.yaml"
    )
    assert result["action"] == "archived"
    assert archived_path.exists()
    assert not task_path.exists()
    archived = _load_yaml(archived_path)
    assert archived["status"] == "archived"
    assert archived["archived_at"] == "2026-06-20T06:31:00Z"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-LEGACY-DONE-legacy-archive-2026-06-20T06-31-00Z.yaml"
    )
    assert artifact["kind"] == "planned_task_legacy_archived"


def test_create_goal_is_idempotent_for_same_payload_and_source_ref(
    tmp_path: Path,
) -> None:
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text("phase: 44\ngoals: []\n", encoding="utf-8")

    first = create_goal(
        tmp_path / ".omo",
        goal_id="BET-2001",
        title="统一治理入口",
        description="Bet: 统一治理入口",
        ingress_plane="projects/c2g",
        source_ref="c2g:bet:BET-2001",
        extra_fields={"vector": "V2"},
        now="2026-06-18T05:00:00Z",
    )
    second = create_goal(
        tmp_path / ".omo",
        goal_id="BET-2001",
        title="统一治理入口",
        description="Bet: 统一治理入口",
        ingress_plane="projects/c2g",
        source_ref="c2g:bet:BET-2001",
        extra_fields={"vector": "V2"},
        now="2026-06-18T05:01:00Z",
    )

    payload = _load_yaml(goals_file)
    assert len(payload["goals"]) == 1
    assert first["id"] == second["id"] == "BET-2001"
    registry = _load_yaml(
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
    )
    assert registry["goals"]["by_source_ref"]["c2g:bet:BET-2001"] == "BET-2001"


def test_create_goal_rejects_source_ref_reuse_for_different_goal(
    tmp_path: Path,
) -> None:
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text("phase: 44\ngoals: []\n", encoding="utf-8")

    create_goal(
        tmp_path / ".omo",
        goal_id="BET-2002",
        title="统一治理入口",
        description="Bet: 统一治理入口",
        ingress_plane="projects/c2g",
        source_ref="c2g:bet:SAME",
        now="2026-06-18T05:02:00Z",
    )

    with pytest.raises(ValueError, match="source_ref already mapped"):
        create_goal(
            tmp_path / ".omo",
            goal_id="BET-2003",
            title="另一个 goal",
            description="Bet: 另一个 goal",
            ingress_plane="projects/c2g",
            source_ref="c2g:bet:SAME",
            now="2026-06-18T05:03:00Z",
        )


def test_update_goal_progress_writes_artifact_and_audit(tmp_path: Path) -> None:
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text(
        yaml.dump(
            {
                "phase": 44,
                "goals": [
                    {
                        "id": "BET-3001",
                        "desc": "统一治理入口",
                        "progress": 0.0,
                        "status": "pending",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    updated = update_goal_progress(
        tmp_path / ".omo",
        goal_id="BET-3001",
        progress=75.0,
        actor="projects/omo",
        source_ref="omo:goal:progress:BET-3001:75",
        now="2026-06-19T03:00:00Z",
    )

    payload = _load_yaml(goals_file)
    assert updated["progress"] == 75.0
    assert updated["status"] == "active"
    assert payload["goals"][0]["progress"] == 75.0
    assert payload["goals"][0]["status"] == "active"
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "goals"
        / "BET-3001-progress-2026-06-19T03-00-00Z.yaml"
    )
    assert artifact["kind"] == "goal_progress_updated"
    assert artifact["previous_progress"] == 0.0
    assert artifact["status"] == "active"
    assert (
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "ingress-audit.jsonl"
    ).exists()


def test_update_goal_progress_rejects_missing_goal(tmp_path: Path) -> None:
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text("phase: 44\ngoals: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="goal not found"):
        update_goal_progress(
            tmp_path / ".omo",
            goal_id="BET-404",
            progress=50.0,
            actor="projects/omo",
        )


def test_create_knowledge_doc_writes_doc_and_artifact(tmp_path: Path) -> None:
    artifact = create_knowledge_doc(
        tmp_path / ".omo",
        plane="design",
        title="My Doc",
        content="Hello world",
        actor="projects/omo",
        source_ref="omo:knowledge:add:design:My Doc",
        now="2026-06-19T04:00:00Z",
    )
    doc = tmp_path / ".omo" / "_knowledge" / "design" / "my-doc.md"
    assert doc.exists()
    assert "Hello world" in doc.read_text(encoding="utf-8")
    assert artifact["doc_ref"] == ".omo/_knowledge/design/my-doc.md"
    assert (
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "knowledge"
        / "design-my-doc-2026-06-19T04-00-00Z.yaml"
    ).exists()


def test_create_standard_doc_writes_doc_and_artifact(tmp_path: Path) -> None:
    artifact = create_standard_doc(
        tmp_path / ".omo",
        title="New Standard",
        content="This is the content.",
        actor="projects/omo",
        source_ref="omo:standard:add:New Standard",
        now="2026-06-19T04:01:00Z",
    )
    doc = tmp_path / ".omo" / "standards" / "new-standard.md"
    assert doc.exists()
    assert "# New Standard" in doc.read_text(encoding="utf-8")
    assert artifact["doc_ref"] == ".omo/standards/new-standard.md"
    assert (
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "standards"
        / "new-standard-2026-06-19T04-01-00Z.yaml"
    ).exists()


def test_create_planned_task_is_idempotent_for_same_payload_and_source_ref(
    tmp_path: Path,
) -> None:
    task_data = {
        "id": "IMPORTED-2001",
        "title": "收敛 broker 入口",
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": ["pitch.md"],
        "deliverables": ["代码", "测试"],
        "imported_via": "projects/c2g",
        "context_uri": "bos://memory/pitches/pitch.md#IMPORTED-2001",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
        "entry_gate": [],
        "evidence_required": ["pytest"],
        "test_plan": ["uv run pytest"],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "metadata": {},
    }

    first = create_planned_task(
        tmp_path / ".omo",
        task_data=task_data,
        ingress_plane="projects/c2g",
        source_ref="c2g:bridge-import:IMPORTED-2001",
        now="2026-06-18T05:04:00Z",
    )
    second = create_planned_task(
        tmp_path / ".omo",
        task_data=task_data,
        ingress_plane="projects/c2g",
        source_ref="c2g:bridge-import:IMPORTED-2001",
        now="2026-06-18T05:05:00Z",
    )

    assert first["id"] == second["id"] == "IMPORTED-2001"
    registry = _load_yaml(
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
    )
    assert (
        registry["tasks"]["by_source_ref"]["c2g:bridge-import:IMPORTED-2001"]
        == "IMPORTED-2001"
    )


def test_create_planned_task_rejects_same_id_different_payload(tmp_path: Path) -> None:
    task_data = {
        "id": "IMPORTED-2002",
        "title": "收敛 broker 入口",
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": ["pitch.md"],
        "deliverables": ["代码", "测试"],
        "imported_via": "projects/c2g",
        "context_uri": "bos://memory/pitches/pitch.md#IMPORTED-2002",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
        "entry_gate": [],
        "evidence_required": ["pytest"],
        "test_plan": ["uv run pytest"],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "metadata": {},
    }
    create_planned_task(
        tmp_path / ".omo",
        task_data=task_data,
        ingress_plane="projects/c2g",
        source_ref="c2g:bridge-import:IMPORTED-2002",
    )

    conflict = dict(task_data)
    conflict["title"] = "冲突标题"
    with pytest.raises(ValueError, match="different payload"):
        create_planned_task(
            tmp_path / ".omo",
            task_data=conflict,
            ingress_plane="projects/c2g",
            source_ref="c2g:bridge-import:IMPORTED-2002",
        )


def test_create_planned_task_rejects_source_ref_reuse_for_different_task(
    tmp_path: Path,
) -> None:
    task_data = {
        "id": "IMPORTED-2003",
        "title": "收敛 broker 入口",
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": ["pitch.md"],
        "deliverables": ["代码", "测试"],
        "imported_via": "projects/c2g",
        "context_uri": "bos://memory/pitches/pitch.md#IMPORTED-2003",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
        "entry_gate": [],
        "evidence_required": ["pytest"],
        "test_plan": ["uv run pytest"],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "metadata": {},
    }
    create_planned_task(
        tmp_path / ".omo",
        task_data=task_data,
        ingress_plane="projects/c2g",
        source_ref="c2g:bridge-import:SAME",
    )

    other = dict(task_data)
    other["id"] = "IMPORTED-2004"
    other["context_uri"] = "bos://memory/pitches/pitch.md#IMPORTED-2004"
    with pytest.raises(ValueError, match="source_ref already mapped"):
        create_planned_task(
            tmp_path / ".omo",
            task_data=other,
            ingress_plane="projects/c2g",
            source_ref="c2g:bridge-import:SAME",
        )


def test_upsert_debt_item_writes_artifacts_and_reuses_same_file(tmp_path: Path) -> None:
    debt_data = {
        "id": "DEBT-OPC-P4-BUDGET-DEMO",
        "title": "budget rejected",
        "description": "blocked by budget",
        "severity": "medium",
        "source": "aetherforge-gateway",
        "remediation": "pick a cheaper model",
    }

    first = upsert_debt_item(
        tmp_path / ".omo",
        debt_data=debt_data,
        ingress_plane="projects/aetherforge",
        source_ref="aetherforge:budget:demo",
        now="2026-06-18T06:00:00Z",
    )
    second = upsert_debt_item(
        tmp_path / ".omo",
        debt_data=debt_data,
        ingress_plane="projects/aetherforge",
        source_ref="aetherforge:budget:demo",
        now="2026-06-18T06:01:00Z",
    )

    debt_file = tmp_path / ".omo" / "debt" / "items" / "DEBT-OPC-P4-BUDGET-DEMO.yaml"
    payload = _load_yaml(debt_file)
    registry = _load_yaml(
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
    )
    artifact = _load_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "debts"
        / "DEBT-OPC-P4-BUDGET-DEMO.yaml"
    )
    debt_registry = _load_yaml(tmp_path / ".omo" / "_truth" / "registry" / "debt.yaml")

    assert first["id"] == second["id"] == "DEBT-OPC-P4-BUDGET-DEMO"
    assert payload["occurrence_count"] == 2
    assert payload["first_seen_at"] == "2026-06-18T06:00:00Z"
    assert payload["last_seen_at"] == "2026-06-18T06:01:00Z"
    assert payload["lifecycle_state"] == "identified"
    assert payload["status"] == "open"
    assert artifact["kind"] == "debt_upserted"
    assert artifact["occurrence_count"] == 2
    assert (
        artifact["artifact_ref"]
        == "runtime/omo/_delivery/ingress/debts/DEBT-OPC-P4-BUDGET-DEMO.yaml"
    )
    assert artifact["broker_ref"] == "projects/omo/src/omo/omo_ingress.py"
    assert artifact["retention_mode"] == "manual_archive"
    assert (
        registry["debts"]["by_source_ref"]["aetherforge:budget:demo"]
        == "DEBT-OPC-P4-BUDGET-DEMO"
    )
    assert ".omo/debt/items/DEBT-OPC-P4-BUDGET-DEMO.yaml" in debt_registry["seed_items"]


def test_remove_debt_item_cleans_registry_and_artifacts(tmp_path: Path) -> None:
    upsert_debt_item(
        tmp_path / ".omo",
        debt_data={
            "id": "DEBT-REMOVE-1",
            "title": "Remove me",
            "description": "cleanup",
            "severity": "low",
        },
        ingress_plane="projects/omo/tests",
        source_ref="tests:debt:remove-1",
        now="2026-06-18T11:30:00Z",
    )

    removed = remove_debt_item(
        tmp_path / ".omo",
        debt_id="DEBT-REMOVE-1",
        actor="projects/omo/tests",
        source_ref="tests:debt:remove-1",
        now="2026-06-18T11:31:00Z",
    )

    assert removed is True
    assert not (tmp_path / ".omo" / "debt" / "items" / "DEBT-REMOVE-1.yaml").exists()
    assert not (
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "debts"
        / "DEBT-REMOVE-1.yaml"
    ).exists()
    registry = _load_yaml(
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
    )
    assert "DEBT-REMOVE-1" not in registry["debts"]["by_id"]
    assert "tests:debt:remove-1" not in registry["debts"]["by_source_ref"]
    debt_registry = _load_yaml(tmp_path / ".omo" / "_truth" / "registry" / "debt.yaml")
    assert ".omo/debt/items/DEBT-REMOVE-1.yaml" not in debt_registry["seed_items"]


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl is POSIX-only")
def test_create_goal_cross_process_lock_keeps_single_goal_entry(tmp_path: Path) -> None:
    goals_file = tmp_path / ".omo" / "goals" / "current.yaml"
    goals_file.parent.mkdir(parents=True, exist_ok=True)
    goals_file.write_text("phase: 44\ngoals: []\n", encoding="utf-8")

    script = f"""
import sys
sys.path.insert(0, {repr(str(OMO_SRC))})
from pathlib import Path
from omo.omo_ingress import create_goal

create_goal(
    Path({repr(str(tmp_path / ".omo"))}),
    goal_id="BET-LOCK-1",
    title="并发 goal",
    description="Bet: 并发 goal",
    ingress_plane="projects/c2g",
    source_ref="c2g:bet:BET-LOCK-1",
    extra_fields={{"vector": "V2"}},
)
"""
    procs = [subprocess.Popen([sys.executable, "-c", script]) for _ in range(2)]
    for proc in procs:
        assert proc.wait(timeout=30) == 0

    payload = _load_yaml(goals_file)
    assert len(payload["goals"]) == 1
    assert payload["goals"][0]["id"] == "BET-LOCK-1"
    records = [
        json.loads(line)
        for line in (
            tmp_path
            / "runtime"
            / "omo"
            / "_delivery"
            / "ingress"
            / "ingress-audit.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(records) == 1
