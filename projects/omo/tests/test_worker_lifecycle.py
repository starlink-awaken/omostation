from __future__ import annotations

import sys
from pathlib import Path

import yaml
import pytest

# Ensure Workspace root is on sys.path for scripts.* imports
_ws_root = Path(__file__).resolve().parents[2]
if str(_ws_root) not in sys.path:
    sys.path.insert(0, str(_ws_root))

from scripts.sync_omo_state import sync_state
from omo.omo_handoff_index import write_handoff_index
from omo.omo_metrics import write_worker_utilization_summary
from omo.omo_worker import (
    dispatch_task,
    main as omo_worker_main,
    reclaim_task,
)
from omo.omo_worker_status import (
    collect_worker_status,
    scan_runtime_watchdog,
    update_dispatch_checkpoint,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def test_dispatch_task_rejects_invalid_task_schema_before_preclaim(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "bad.yaml",
        {
            "id": "TASK-BAD",
            "title": "Broken task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "entry_gate": ["approval required"],
            "evidence_required": ["approval record"],
            "test_plan": [".omo/tests/example.md"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="approval_ref is required for L2/L3 tasks"):
        dispatch_task(
            root,
            task_id="TASK-BAD",
            worker_id="mockworker",
            allowed_write_paths=["src/app.py"],
            launch=False,
        )


def test_dispatch_task_launch_handles_quoted_prompt_without_shell_breakage(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    captured = root / "captured.txt"

    _write_yaml(
        omo / "tasks" / "active" / "quoted.yaml",
        {
            "id": "TASK-QUOTED",
            "title": 'Worker "quoted" task',
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["captured prompt"],
            "test_plan": ["launch worker safely"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {
                            "command": f'python3 -c "import pathlib,sys; pathlib.Path(r\'{captured}\').write_text(sys.argv[1])" "{{prompt}}"'
                        }
                    },
                }
            ]
        },
    )

    dispatch_task(
        root,
        task_id="TASK-QUOTED",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=True,
    )

    assert captured.exists()
    assert 'Worker "quoted" task' in captured.read_text(encoding="utf-8")


def test_dispatch_prompt_includes_required_deliverables_when_task_declares_them(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "deliverable.yaml",
        {
            "id": "TASK-DELIVERABLE",
            "title": "Write roadmap",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/source.md"],
            "deliverables": [".omo/_knowledge/design/plans/output.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["roadmap written"],
            "test_plan": ["verify output file exists"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-DELIVERABLE",
        worker_id="mockworker",
        allowed_write_paths=[".omo/_knowledge/design/plans/"],
        launch=False,
    )

    prompt_text = (root / result["prompt_path"]).read_text(encoding="utf-8")
    envelope = yaml.safe_load((root / result["envelope_path"]).read_text(encoding="utf-8"))

    assert "- Required deliverable: `.omo/_knowledge/design/plans/output.md`" in prompt_text
    assert "Updating only the review note is not sufficient" in prompt_text
    assert envelope["outputs"]["required_deliverables"] == [".omo/_knowledge/design/plans/output.md"]


def test_dispatch_task_creates_checkpoint_and_reclaim_artifacts(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "checkpoint.yaml",
        {
            "id": "TASK-CHECKPOINT",
            "title": "Checkpoint task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint stub created"],
            "test_plan": ["inspect dispatch artifacts"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-CHECKPOINT",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=False,
    )

    dispatch = _load_yaml(root / result["dispatch_path"])
    task = _load_yaml(omo / "tasks" / "active" / "checkpoint.yaml")
    checkpoint_text = (root / result["checkpoint_path"]).read_text(encoding="utf-8")
    reclaim_text = (root / result["reclaim_path"]).read_text(encoding="utf-8")
    status = collect_worker_status(root)

    assert dispatch["execution"]["checkpoint_refs"] == [result["checkpoint_path"]]
    assert task["handoff_refs"][-2:] == [result["prompt_path"], result["checkpoint_path"]]
    assert "## Last completed step" in checkpoint_text
    assert "## Reclaim reason" in reclaim_text
    assert status["active_dispatches"] == 1
    assert status["runs"][0]["checkpoint_refs"] == [result["checkpoint_path"]]
    assert status["runs"][0]["reclaim_ref"] == result["reclaim_path"]
    assert status["runs"][0]["lease"]["warning_after_seconds"] == 900


def test_sync_state_flags_in_progress_tasks_missing_run_and_review_refs(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "a.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "run_ref": None,
            "review_ref": None,
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-A"]}]})

    sync_state(omo)

    state = _load_yaml(omo / "state" / "system.yaml")
    assert "active_task_missing_run_ref:TASK-A" in state["divergence_flags"]
    assert "active_task_missing_review_ref:TASK-A" in state["divergence_flags"]


def test_sync_state_derives_gate_facts_and_promotion_blockers(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "gate.yaml",
        {
            "id": "TASK-GATE",
            "title": "Gate task",
            "status": "in_progress",
            "assigned_to": "worker-a",
            "dispatch_id": "dispatch-1",
            "run_ref": ".omo/workers/runs/dispatch-1-dispatch.yaml",
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["review note"],
            "test_plan": ["sync state"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-GATE"]}]})
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-1-dispatch.yaml",
        {
            "task_id": "TASK-GATE",
            "worker_id": "worker-a",
            "dispatch_state": "reclaimed",
            "reclaim": {
                "required": True,
                "reason": "lease expired",
                "reclaimed_at": "2026-05-31T00:00:00Z",
                "successor_worker_id": "worker-b",
                "successor_dispatch_id": "dispatch-2",
                "note_ref": ".omo/workers/runs/dispatch-1-reclaim.md",
            },
        },
    )

    state = sync_state(omo)

    gate = state["task_gate_summary"]["TASK-GATE"]
    assert gate["canonical_status"] == "in_progress"
    assert gate["gate_facts"] == ["dispatched", "reclaimed"]
    assert state["promotion_blockers"]["TASK-GATE"] == ["missing_review_ref"]


def test_sync_state_dispatched_gate_requires_dispatch_id(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "dispatch.yaml",
        {
            "id": "TASK-DISPATCH",
            "title": "Dispatch task",
            "status": "in_progress",
            "assigned_to": "worker-a",
            "dispatch_id": None,
            "run_ref": ".omo/workers/runs/dispatch-dispatch.yaml",
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": [],
            "test_plan": ["sync state"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-DISPATCH"]}]})

    state = sync_state(omo)

    gate = state["task_gate_summary"]["TASK-DISPATCH"]
    assert "dispatched" not in gate["gate_facts"]


def test_sync_state_done_task_requires_completion_summary_before_acceptance(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "done.yaml",
        {
            "id": "TASK-DONE",
            "title": "Done task",
            "status": "done",
            "assigned_to": "worker-a",
            "dispatch_id": "dispatch-done",
            "run_ref": ".omo/workers/runs/dispatch-done-dispatch.yaml",
            "approval_ref": None,
            "review_ref": ".omo/workers/runs/dispatch-done-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["review note"],
            "test_plan": ["sync state"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-DONE"]}]})
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-done-dispatch.yaml",
        {
            "task_id": "TASK-DONE",
            "worker_id": "worker-a",
            "dispatch_state": "completed",
        },
    )
    (omo / "workers" / "runs" / "dispatch-done-review.md").parent.mkdir(parents=True, exist_ok=True)
    (omo / "workers" / "runs" / "dispatch-done-review.md").write_text(
        "# Review Note\n\ncompleted\n",
        encoding="utf-8",
    )

    state = sync_state(omo)

    gate = state["task_gate_summary"]["TASK-DONE"]
    assert "accepted" not in gate["gate_facts"]
    assert state["promotion_blockers"]["TASK-DONE"] == ["missing_completion_summary"]


def test_sync_state_joins_divergence_snapshot_with_triage_registry(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "a.yaml",
        {"id": "TASK-A", "phase": 6, "status": "in_progress", "run_ref": None, "review_ref": None},
    )
    _write_yaml(omo / "tasks" / "blocked" / "b.yaml", {"id": "TASK-B", "phase": 6})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 6, "goals": [{"id": "G1", "tasks": ["TASK-A"]}]})
    _write_yaml(
        omo / "standards" / "divergence-triage.yaml",
        {
            "rules": {
                "orphaned_tasks": {"severity": "medium", "owner": "truth", "disposition": "must_fix"},
                "active_task_missing_review_ref": {"severity": "high", "owner": "delivery", "disposition": "must_fix"},
            }
        },
    )

    state = sync_state(omo)

    triage = state["divergence_triage_summary"]
    assert triage["orphaned_tasks:1"]["severity"] == "medium"
    assert triage["active_task_missing_review_ref:TASK-A"]["owner"] == "delivery"
    assert triage["active_task_missing_run_ref:TASK-A"]["disposition"] == "monitor"


def test_worker_status_command_prints_checkpoint_summary(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "status.yaml",
        {
            "id": "TASK-STATUS",
            "title": "Status task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["status visible"],
            "test_plan": ["run worker status"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    dispatch_task(root, "TASK-STATUS", "mockworker", ["src/app.py"], launch=False)

    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["omo", "worker", "status"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    assert "TASK-STATUS" in output
    assert "mockworker" in output
    assert "checkpoints=1" in output


def test_update_dispatch_checkpoint_records_step_and_refreshes_lease(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "checkpoint.yaml",
        {
            "id": "TASK-CHECKPOINT",
            "title": "Checkpoint task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint stub created"],
            "test_plan": ["inspect dispatch artifacts"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {"workers": [{"id": "mockworker", "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}}}]},
    )

    dispatch = dispatch_task(root, "TASK-CHECKPOINT", "mockworker", ["src/app.py"], launch=False)

    result = update_dispatch_checkpoint(
        root,
        dispatch["dispatch_id"],
        completed_step="Implemented durable checkpoint refresh",
        changed_files=["scripts/omo_worker.py", ".omo/tests/test_omo_automation.py"],
        note="Checkpoint updated after writing runtime evidence.",
        now="2026-05-31T08:00:00Z",
    )

    dispatch_payload = _load_yaml(root / dispatch["dispatch_path"])
    checkpoint_text = (root / dispatch["checkpoint_path"]).read_text(encoding="utf-8")
    assert result["dispatch_state"] == "checkpointed"
    assert dispatch_payload["dispatch_state"] == "checkpointed"
    assert dispatch_payload["lease"]["last_checkpoint_at"] == "2026-05-31T08:00:00Z"
    assert dispatch_payload["lease"]["last_material_write_at"] == "2026-05-31T08:00:00Z"
    assert "Implemented durable checkpoint refresh" in checkpoint_text
    assert "- `scripts/omo_worker.py`" in checkpoint_text
    assert "Checkpoint updated after writing runtime evidence." in checkpoint_text


def test_scan_runtime_watchdog_classifies_warning_stale_and_reclaim_due(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "tasks" / "active" / "a.yaml",
        {"id": "TASK-A", "title": "A", "status": "in_progress", "run_ref": ".omo/workers/runs/a-dispatch.yaml"},
    )
    _write_yaml(
        omo / "tasks" / "active" / "b.yaml",
        {"id": "TASK-B", "title": "B", "status": "in_progress", "run_ref": ".omo/workers/runs/b-dispatch.yaml"},
    )
    _write_yaml(
        omo / "tasks" / "active" / "c.yaml",
        {"id": "TASK-C", "title": "C", "status": "in_progress", "run_ref": ".omo/workers/runs/c-dispatch.yaml"},
    )
    _write_yaml(
        omo / "workers" / "runs" / "a-dispatch.yaml",
        {
            "task_id": "TASK-A",
            "worker_id": "worker-a",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:58:30Z",
                "last_material_write_at": "2026-05-31T07:58:30Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/a-checkpoint.md"]},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "b-dispatch.yaml",
        {
            "task_id": "TASK-B",
            "worker_id": "worker-b",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:57:30Z",
                "last_material_write_at": "2026-05-31T07:57:30Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/b-checkpoint.md"]},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "c-dispatch.yaml",
        {
            "task_id": "TASK-C",
            "worker_id": "worker-c",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:54:00Z",
                "last_material_write_at": "2026-05-31T07:54:00Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/c-checkpoint.md"]},
        },
    )

    watchdog = scan_runtime_watchdog(root, now="2026-05-31T08:00:00Z")

    assert watchdog["counts"] == {"healthy": 0, "warning": 1, "stale": 1, "reclaim_due": 1}
    assert watchdog["runs"][0]["task_id"] == "TASK-A"
    assert watchdog["runs"][0]["health"] == "warning"
    assert watchdog["runs"][1]["task_id"] == "TASK-B"
    assert watchdog["runs"][1]["health"] == "stale"
    assert watchdog["runs"][2]["task_id"] == "TASK-C"
    assert watchdog["runs"][2]["health"] == "reclaim_due"


def test_worker_watchdog_command_prints_runtime_health(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "tasks" / "active" / "watch.yaml",
        {"id": "TASK-WATCH", "title": "Watch task", "status": "in_progress", "run_ref": ".omo/workers/runs/watch-dispatch.yaml"},
    )
    _write_yaml(
        omo / "workers" / "runs" / "watch-dispatch.yaml",
        {
            "task_id": "TASK-WATCH",
            "worker_id": "worker-a",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:54:00Z",
                "last_material_write_at": "2026-05-31T07:54:00Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/watch-checkpoint.md"]},
        },
    )

    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["omo", "worker", "watchdog", "--now", "2026-05-31T08:00:00Z"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    assert "reclaim_due=1" in output
    assert "TASK-WATCH" in output
    assert "health=reclaim_due" in output


def test_worker_admission_eval_command_prints_decision(monkeypatch, capsys):
    root = Path(__file__).resolve().parents[2]

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "admission-eval",
            ".omo/workers/runs/phase9/phase9-wave3-identity-admission-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "membership=system-governor-membership" in output
    assert "decision=conditional_approval" in output


def test_worker_admission_request_approval_command_writes_governance_artifacts(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / "spaces" / "contract.yaml",
        {
            "admission_matrix_ref": "spaces/matrix.yaml",
            "memberships": [
                {
                    "id": "governor-membership",
                    "actor_ref": "demo-actor",
                    "space_ref": "spaces/system-space.yaml",
                    "roles": ["governor"],
                }
            ],
            "capability_bindings": [
                {
                    "id": "governor-binding",
                    "membership_ref": "governor-membership",
                    "capabilities": ["project.dispatch"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "matrix.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_capabilities": ["project.dispatch"],
                    "decision": "conditional_approval",
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "run_ref": ".omo/workers/runs/example-dispatch.yaml",
            "task_yaml": ".omo/tasks/active/TASK-1.yaml",
            "handoff_refs": [".omo/workers/runs/example-review.md"],
            "gates": {"approval_ref": None},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "governor-membership",
                "action": "project.dispatch",
                "admission_contract_ref": "spaces/contract.yaml",
                "required_capabilities": ["project.dispatch"],
                "decision_mode": "conditional_approval",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "admission-request-approval",
            ".omo/workers/runs/example-envelope.yaml",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-05-31T12:31:00Z",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "proposal=example-approval-proposal" in output
    assert "approval_ref=.omo/workers/runs/example-approval.yaml" in output
    assert (tmp_path / ".omo" / "workers" / "runs" / "example-approval.yaml").exists()
    assert (
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "example-approval-proposal.yaml"
    ).exists()


def test_worker_rollout_eval_command_prints_allow_for_granted_approval(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / "spaces" / "rollout-policy.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_approval_status": "granted",
                    "required_evidence_refs": [
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                    ],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "runtime" / "runtime-boundary.yaml",
        {
            "allowed_runtime_roots": ["runtime/run-continuation", "runtime/logs"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-approval.yaml",
        {
            "approval_status": "granted",
            "release_scope": {"exact_action": "project.dispatch"},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "apply.yaml",
        {"status": "applied"},
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "verify.yaml",
        {"status": "verified"},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {"approval_ref": ".omo/workers/runs/example-approval.yaml"},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rollout_context": {
                "rollout_policy_ref": "spaces/rollout-policy.yaml",
                "runtime_boundary_ref": "runtime/runtime-boundary.yaml",
                "acceptance_evidence_refs": [
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                ],
                "runtime_residue_paths": [
                    "runtime/run-continuation/session-1",
                    "runtime/logs/dispatch.log",
                ],
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rollout-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "approval=granted" in output
    assert "decision=allow" in output


def test_worker_rollout_accept_command_writes_acceptance_record(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / "spaces" / "rollout-policy.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_approval_status": "granted",
                    "required_evidence_refs": [
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                    ],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "runtime" / "runtime-boundary.yaml",
        {
            "allowed_runtime_roots": ["runtime/run-continuation", "runtime/logs"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-approval.yaml",
        {
            "approval_status": "granted",
            "release_scope": {"exact_action": "project.dispatch"},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "apply.yaml",
        {"status": "applied"},
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "verify.yaml",
        {"status": "verified"},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "run_ref": ".omo/workers/runs/example-dispatch.yaml",
            "task_yaml": ".omo/tasks/active/TASK-1.yaml",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": None,
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rollout_context": {
                "rollout_policy_ref": "spaces/rollout-policy.yaml",
                "runtime_boundary_ref": "runtime/runtime-boundary.yaml",
                "acceptance_evidence_refs": [
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                ],
                "runtime_residue_paths": [
                    "runtime/run-continuation/session-1",
                    "runtime/logs/dispatch.log",
                ],
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rollout-accept",
            ".omo/workers/runs/example-envelope.yaml",
            "--accepted-by",
            "copilot-cli",
            "--now",
            "2026-05-31T20:45:00Z",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "acceptance_ref=.omo/workers/runs/example-acceptance.yaml" in output
    assert (tmp_path / ".omo" / "workers" / "runs" / "example-acceptance.yaml").exists()
    envelope = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml")
    assert envelope["gates"]["acceptance_ref"] == ".omo/workers/runs/example-acceptance.yaml"


def test_worker_rules_eval_command_prints_normalized_bundle_refs(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "project.dispatch",
                    "governance": {
                        "admission_contract_ref": "spaces/identity.yaml",
                        "rollout_policy_ref": "spaces/rollout-policy.yaml",
                    },
                    "data": {"policy_ref": "data/data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-boundary.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "data-policy.yaml",
        {"rules": [{"action": "project.dispatch", "allowed_roots": ["data"]}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rules-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "registry=spaces/cross-root-rules.yaml" in output
    assert "data_policy=data/data-policy.yaml" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-boundary.yaml" in output


def test_worker_rules_eval_command_prints_normalized_bundle_refs_for_wave3_packets(
    tmp_path: Path, monkeypatch, capsys
):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "project.dispatch",
                    "governance": {
                        "admission_contract_ref": "spaces/identity.yaml",
                        "rollout_policy_ref": "spaces/rollout-policy.yaml",
                    },
                    "data": {"policy_ref": "data/data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-boundary.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "data-policy.yaml",
        {"rules": [{"action": "project.dispatch", "allowed_roots": ["data"]}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W3-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rules-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "registry=spaces/cross-root-rules.yaml" in output
    assert "data_policy=data/data-policy.yaml" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-boundary.yaml" in output


def test_worker_rules_eval_command_prints_normalized_bundle_refs_for_cross_space_packets(
    tmp_path: Path, monkeypatch, capsys
):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/runtime-space.yaml",
                    "action": "runtime.observe",
                    "governance": {
                        "admission_contract_ref": "spaces/runtime-identity.yaml",
                        "rollout_policy_ref": "spaces/runtime-rollout-policy.yaml",
                    },
                    "data": {"policy_ref": "data/runtime-data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-space-boundary.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "runtime-data-policy.yaml",
        {"rules": [{"action": "runtime.observe", "allowed_roots": []}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W4-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/runtime-space.yaml",
                "membership_ref": "runtime-space-observer-membership",
                "action": "runtime.observe",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rules-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=runtime.observe" in output
    assert "registry=spaces/cross-root-rules.yaml" in output
    assert "data_policy=data/runtime-data-policy.yaml" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-space-boundary.yaml" in output


def test_write_worker_utilization_summary_aggregates_runs(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "workers" / "runs" / "one-dispatch.yaml",
        {
            "task_id": "TASK-1",
            "worker_id": "worker-a",
            "dispatch_state": "completed",
            "launched_at": "2026-05-30T10:00:00Z",
            "handoff": {"output_summary_ref": ".omo/workers/runs/one-review.md"},
            "reclaim": {"successor_dispatch_id": "two", "successor_worker_id": "worker-b"},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "two-dispatch.yaml",
        {
            "task_id": "TASK-2",
            "worker_id": "worker-a",
            "dispatch_state": "reclaimed",
            "launched_at": "2026-05-31T10:00:00Z",
            "handoff": {"output_summary_ref": ".omo/workers/runs/two-review.md"},
            "reclaim": {"successor_dispatch_id": None, "successor_worker_id": None},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "three-dispatch.yaml",
        {
            "task_id": "TASK-3",
            "worker_id": "worker-b",
            "dispatch_state": "completed",
            "launched_at": "2026-05-31T12:00:00Z",
            "handoff": {"output_summary_ref": ".omo/workers/runs/three-review.md"},
            "reclaim": {"successor_dispatch_id": None, "successor_worker_id": None},
        },
    )

    summary_path = write_worker_utilization_summary(root)
    text = (root / summary_path).read_text(encoding="utf-8")

    assert "period_start: 2026-05-30T10:00:00Z" in text
    assert "period_end: 2026-05-31T12:00:00Z" in text
    assert "worker-a" in text
    assert "dispatches: 2" in text
    assert "reclaims: 1" in text
    assert "review_notes: 2" in text
    assert "handoffs_out: 1" in text
    assert "average_handoffs_per_dispatch: 0.5" in text


def test_reclaim_task_reassigns_from_checkpoint_context(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "reclaim.yaml",
        {
            "id": "TASK-RECLAIM",
            "title": "Reclaim task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint reclaim drill completed"],
            "test_plan": ["run reclaim flow"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {
                    "id": "worker-a",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                },
                {
                    "id": "worker-b",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                },
            ]
        },
    )

    first = dispatch_task(root, "TASK-RECLAIM", "worker-a", ["src/app.py"], launch=False)
    (root / first["checkpoint_path"]).write_text(
        "# Checkpoint Note\n\n## Last completed step\n\nImplemented the parser.\n",
        encoding="utf-8",
    )

    second = reclaim_task(
        root,
        task_id="TASK-RECLAIM",
        successor_worker_id="worker-b",
        allowed_write_paths=["src/app.py"],
        reason="lease expired",
        launch=False,
    )

    first_dispatch = _load_yaml(root / first["dispatch_path"])
    second_dispatch = _load_yaml(root / second["dispatch_path"])
    second_envelope = _load_yaml(root / second["envelope_path"])
    second_prompt = (root / second["prompt_path"]).read_text(encoding="utf-8")
    reclaim_note = (root / first["reclaim_path"]).read_text(encoding="utf-8")
    task = _load_yaml(omo / "tasks" / "active" / "reclaim.yaml")

    assert first_dispatch["dispatch_state"] == "reclaimed"
    assert first_dispatch["reclaim"]["required"] is True
    assert first_dispatch["reclaim"]["reason"] == "lease expired"
    assert first_dispatch["reclaim"]["successor_worker_id"] == "worker-b"
    assert first_dispatch["reclaim"]["successor_dispatch_id"] == second["dispatch_id"]
    assert task["assigned_to"] == "worker-b"
    assert task["run_ref"] == second["dispatch_path"]
    assert first["checkpoint_path"] in second_prompt
    assert first["reclaim_path"] in second_prompt
    assert second_envelope["inputs"]["prior_evidence"] == [first["checkpoint_path"], first["reclaim_path"]]
    assert "lease expired" in reclaim_note
    assert second_dispatch["task_id"] == "TASK-RECLAIM"


def test_write_handoff_index_links_dispatch_checkpoint_reclaim_and_review(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "tasks" / "active" / "reclaim.yaml",
        {
            "id": "TASK-RECLAIM",
            "title": "Reclaim task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/_knowledge/design/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint reclaim drill completed"],
            "test_plan": ["run reclaim flow"],
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "workers.yaml",
        {
            "workers": [
                {"id": "worker-a", "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}}},
                {"id": "worker-b", "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}}},
            ]
        },
    )

    dispatch = dispatch_task(root, "TASK-RECLAIM", "worker-a", ["src/app.py"], launch=False)
    reclaim = reclaim_task(root, "TASK-RECLAIM", "worker-b", ["src/app.py"], reason="lease expired", launch=False)

    task = _load_yaml(omo / "tasks" / "active" / "reclaim.yaml")
    task["review_ref"] = dispatch["review_path"]
    task["completion_summary"] = "Recovered via reclaim and closed with a successor worker."
    _write_yaml(omo / "tasks" / "active" / "reclaim.yaml", task)

    index_path = write_handoff_index(root, "TASK-RECLAIM")
    text = (root / index_path).read_text(encoding="utf-8")

    assert dispatch["dispatch_path"] in text
    assert dispatch["checkpoint_path"] in text
    assert dispatch["reclaim_path"] in text
    assert dispatch["review_path"] in text
    assert reclaim["dispatch_path"] in text
    assert "Recovered via reclaim and closed with a successor worker." in text
