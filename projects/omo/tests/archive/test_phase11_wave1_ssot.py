from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-system-consistency.sh"


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _seed_active_task(omo: Path) -> None:
    _write_yaml(
        omo / "tasks" / "active" / "p11-w1.yaml",
        {
            "id": "P11-W1-SSOT-BASELINE",
            "phase": 11,
            "milestone": "W1",
            "priority": "P0",
            "title": "Start Phase 11 with SSOT repair and baseline inventory",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/phase11-wave1-execution-plan.md"],
            "deliverables": [],
            "depends_on": [],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "entry_gate": ["Phase 10 closeout recorded"],
            "evidence_required": ["Wave 1 kickoff packet exists"],
            "test_plan": ["python3 scripts/check-system-consistency.sh"],
        },
    )


def test_check_system_consistency_script_refreshes_freshness_and_control(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 11,
            "status": "in_progress",
            "current_wave": 1,
            "goals": [{"id": "G11.1", "status": "in_progress", "tasks": ["P11-W1-SSOT-BASELINE"]}],
        },
    )
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "current_phase": 11,
            "phase_status": "active",
            "current_wave": 1,
            "phase11_status": "in_progress",
            "completed_tasks": 100,
            "blocked_tasks": 0,
            "active_tasks": 1,
            "updated_at": "2026-06-01T00:00:00Z",
            "divergence_flags": [],
        },
    )
    (omo / "plans").mkdir(parents=True, exist_ok=True)
    (omo / "plans" / "README.md").write_text(
        "phase11-program-plan.md\nphase11-wave1-execution-plan.md\n",
        encoding="utf-8",
    )
    _seed_active_task(omo)

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        env={**os.environ, "OMO_ROOT": str(tmp_path), "OMO_NOW": "2026-06-01T00:00:00Z"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    freshness = yaml.safe_load((omo / "_delivery" / "task-center" / "freshness" / "current.yaml").read_text(encoding="utf-8"))
    control = yaml.safe_load((omo / "_delivery" / "task-center" / "control" / "current.yaml").read_text(encoding="utf-8"))
    assert freshness["freshness_score"] == 100
    assert freshness["stale_items"] == []
    assert control["decision"] == "allow"
    assert control["freshness_score"] == 100


def test_check_system_consistency_script_fails_when_plans_readme_misses_current_wave(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 11,
            "status": "in_progress",
            "current_wave": 1,
            "goals": [{"id": "G11.1", "status": "in_progress", "tasks": ["P11-W1-SSOT-BASELINE"]}],
        },
    )
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "current_phase": 11,
            "phase_status": "active",
            "current_wave": 1,
            "phase11_status": "in_progress",
            "updated_at": "2026-06-01T00:00:00Z",
            "divergence_flags": [],
        },
    )
    (omo / "plans").mkdir(parents=True, exist_ok=True)
    (omo / "plans" / "README.md").write_text("phase11-program-plan.md\n", encoding="utf-8")
    _seed_active_task(omo)

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        env={**os.environ, "OMO_ROOT": str(tmp_path), "OMO_NOW": "2026-06-01T00:00:00Z"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "plans/README.md missing phase11-wave1-execution-plan.md" in (result.stdout + result.stderr)


def test_check_system_consistency_script_recomputes_state_before_alignment(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 11,
            "status": "active",
            "current_wave": 1,
            "goals": [{"id": "G11.1", "status": "active", "tasks": ["P11-W1-SSOT-BASELINE"]}],
        },
    )
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "current_phase": 11,
            "phase_status": "active",
            "current_wave": 1,
            "phase11_status": "wave1_active",
            "updated_at": "2026-06-01T00:30:00Z",
            "divergence_flags": ["stale_dispatch:P11-W1-SSOT-BASELINE"],
        },
    )
    (omo / "plans").mkdir(parents=True, exist_ok=True)
    (omo / "plans" / "README.md").write_text(
        "phase11-program-plan.md\nphase11-wave1-execution-plan.md\n",
        encoding="utf-8",
    )
    _write_yaml(
        omo / "tasks" / "active" / "p11-w1.yaml",
        {
            "id": "P11-W1-SSOT-BASELINE",
            "phase": 11,
            "status": "in_progress",
            "dispatch_id": "phase11-wave1-ssot-baseline",
            "run_ref": ".omo/workers/runs/phase11-wave1-ssot-baseline-dispatch.yaml",
            "review_ref": ".omo/workers/runs/phase11-wave1-ssot-baseline-review.md",
            "assigned_to": "worker-1",
            "knowledge_refs": [],
            "handoff_refs": [],
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "phase11-wave1-ssot-baseline-dispatch.yaml",
        {
            "task_id": "P11-W1-SSOT-BASELINE",
            "dispatch_state": "active",
            "launched_at": "2026-06-01T00:00:00Z",
            "lease": {
                "lease_expired_after_seconds": 1200,
                "last_checkpoint_at": "2026-06-01T00:00:00Z",
                "last_material_write_at": "2026-06-01T00:00:00Z",
            },
        },
    )
    (omo / "workers" / "runs" / "phase11-wave1-ssot-baseline-review.md").write_text("# review\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        env={**os.environ, "OMO_ROOT": str(tmp_path), "OMO_NOW": "2026-06-01T00:00:00Z"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
