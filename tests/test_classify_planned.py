from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin" / "classify_planned.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("classify_planned_module", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_classify_planned_splits_pending_vs_granted_blocked(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    workspace_root = tmp_path
    planned_dir = workspace_root / ".omo" / "tasks" / "planned"
    approval_queue_path = workspace_root / ".omo" / "workers" / "promotion" / "approval-queue" / "current.yaml"

    _write_yaml(
        planned_dir / "SELF.yaml",
        {
            "id": "SELF",
            "title": "Self evolution",
            "status": "candidate",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/SELF-approval.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "entry_gate": ["human_review"],
            "evidence_required": ["demo"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "depends_on": [],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        planned_dir / "OPT.yaml",
        {
            "id": "OPT",
            "title": "Gateway",
            "status": "candidate",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/OPT-approval.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "entry_gate": ["human_review"],
            "evidence_required": ["demo"],
            "risk_level": "L3",
            "allowed_operation_level": "L3",
            "human_approval_required": True,
            "depends_on": [],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        planned_dir / "TASK.yaml",
        {
            "id": "TASK",
            "title": "Normal",
            "status": "candidate",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "entry_gate": ["demo"],
            "evidence_required": ["demo"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "depends_on": [],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        approval_queue_path,
        {
            "generated_at": "2026-06-21T00:00:00Z",
            "task_count": 2,
            "tasks": [
                {
                    "task_id": "SELF",
                    "approval_status": "granted",
                    "proposal_status": "verified",
                    "eligible": False,
                    "blockers": ["task_policy_blocked"],
                    "next_action": "resolve_blockers",
                },
                {
                    "task_id": "OPT",
                    "approval_status": None,
                    "proposal_status": None,
                    "eligible": False,
                    "blockers": ["approval_missing"],
                    "next_action": "materialize_queue_status",
                },
            ],
        },
    )

    monkeypatch.setattr(module, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(module, "PLANNED_DIR", planned_dir)
    monkeypatch.setattr(module, "APPROVAL_QUEUE_PATH", approval_queue_path)

    result = module.classify()

    assert result["summary"]["valid"] == 3
    assert result["summary"]["approval_required"] == 2
    assert result["summary"]["approval_pending"] == 1
    assert result["summary"]["approval_granted_blocked"] == 1
    assert result["summary"]["approval_ready_to_promote"] == 0
    assert [entry["task_id"] for entry in result["approval_pending_queue"]] == ["OPT"]
    assert [entry["task_id"] for entry in result["approval_granted_blocked_queue"]] == ["SELF"]
    assert [entry["task_id"] for entry in result["approval_queue"]] == ["OPT"]
    assert [entry["task_id"] for entry in result["approval_required_backlog"]] == ["OPT", "SELF"]
    assert "python3 scripts/omo/omo_worker.py task approval-queue-status --omo-dir .omo" in result["next_actions"]
