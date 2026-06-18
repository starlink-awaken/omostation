from __future__ import annotations

import json
import subprocess
import sys
import yaml
from pathlib import Path

import pytest

from omo.omo_ingress import create_goal, create_planned_task, remove_debt_item, upsert_debt_item


OMO_SRC = Path(__file__).resolve().parents[1] / "src"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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
        tmp_path / ".omo" / "_delivery" / "ingress" / "goals" / "BET-1234.yaml"
    )
    assert artifact["kind"] == "goal_created"
    assert artifact["ingress_plane"] == "projects/c2g"
    audit_log = tmp_path / ".omo" / "_delivery" / "ingress" / "ingress-audit.jsonl"
    assert audit_log.exists()


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
        tmp_path / ".omo" / "_delivery" / "ingress" / "tasks" / "IMPORTED-123456.yaml"
    )
    assert artifact["kind"] == "planned_task_created"
    assert artifact["task_ref"] == ".omo/tasks/planned/IMPORTED-123456.yaml"


def test_create_planned_task_rejects_invalid_planned_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid planned task"):
        create_planned_task(
            tmp_path / ".omo",
            task_data={"id": "BAD-1", "title": "bad"},
            ingress_plane="projects/c2g",
        )


def test_create_goal_is_idempotent_for_same_payload_and_source_ref(tmp_path: Path) -> None:
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
    registry = _load_yaml(tmp_path / ".omo" / "_delivery" / "ingress" / "registry.yaml")
    assert registry["goals"]["by_source_ref"]["c2g:bet:BET-2001"] == "BET-2001"


def test_create_goal_rejects_source_ref_reuse_for_different_goal(tmp_path: Path) -> None:
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
    registry = _load_yaml(tmp_path / ".omo" / "_delivery" / "ingress" / "registry.yaml")
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
    registry = _load_yaml(tmp_path / ".omo" / "_delivery" / "ingress" / "registry.yaml")
    artifact = _load_yaml(
        tmp_path / ".omo" / "_delivery" / "ingress" / "debts" / "DEBT-OPC-P4-BUDGET-DEMO.yaml"
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
    assert registry["debts"]["by_source_ref"]["aetherforge:budget:demo"] == "DEBT-OPC-P4-BUDGET-DEMO"
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
        tmp_path / ".omo" / "_delivery" / "ingress" / "debts" / "DEBT-REMOVE-1.yaml"
    ).exists()
    registry = _load_yaml(tmp_path / ".omo" / "_delivery" / "ingress" / "registry.yaml")
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
            tmp_path / ".omo" / "_delivery" / "ingress" / "ingress-audit.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
