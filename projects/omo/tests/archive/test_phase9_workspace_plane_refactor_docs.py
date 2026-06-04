from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OMO_ROOT.parent


def _read_omo(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def _read_workspace(rel_path: str) -> str:
    return (WORKSPACE_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase9_workspace_plane_refactor_artifacts_exist() -> None:
    root_index = _read_omo("INDEX.md")
    design_index = _read_omo("_knowledge/design/INDEX.md")
    plans_readme = _read_omo("plans/README.md")
    projects_registry = _read_omo("PROJECTS.yaml")
    agents_guide = _read_workspace("AGENTS.md")

    for rel_path in [
        "plans/phase9-workspace-plane-refactor-plan.md",
        "../spaces/README.md",
        "../data/README.md",
        "../runtime/README.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase9-workspace-plane-refactor-plan.md" in root_index
    assert "phase9-workspace-plane-refactor-plan.md" in design_index
    assert "phase9-workspace-plane-refactor-plan.md" in plans_readme

    assert "workspace_roots:" in projects_registry
    assert "spaces:" in projects_registry
    assert "data:" in projects_registry
    assert "runtime:" in projects_registry

    assert "spaces/" in agents_guide
    assert "data/" in agents_guide
    assert "runtime/" in agents_guide


def test_phase9_first_migration_baseline_is_indexed() -> None:
    root_index = _read_omo("INDEX.md")
    process_index = _read_omo("_knowledge/process/INDEX.md")

    summary_path = OMO_ROOT / "summaries" / "phase9-first-migration-baseline.md"
    assert summary_path.exists()

    assert "phase9-first-migration-baseline.md" in root_index
    assert "phase9-first-migration-baseline.md" in process_index


def test_phase9_remaining_program_and_wave2_packet_are_seeded() -> None:
    root_index = _read_omo("INDEX.md")
    plans_index = _read_omo("plans/README.md")
    task_readme = _read_omo("tasks/README.md")

    program_plan = OMO_ROOT / "plans" / "phase9-program-plan.md"
    wave2_plan = OMO_ROOT / "plans" / "phase9-wave2-execution-plan.md"
    done_task = OMO_ROOT / "tasks" / "done" / "P9-W2-SPACE-REGISTRY-FOUNDATION.yaml"

    assert program_plan.exists()
    assert wave2_plan.exists()
    assert done_task.exists()

    assert "phase9-program-plan.md" in root_index
    assert "phase9-wave2-execution-plan.md" in root_index
    assert "phase9-program-plan.md" in plans_index
    assert "phase9-wave2-execution-plan.md" in plans_index
    assert "Phase 9" in task_readme


def test_phase9_wave2_closeout_is_recorded_and_archived() -> None:
    root_index = _read_omo("INDEX.md")
    process_index = _read_omo("_knowledge/process/INDEX.md")
    program_plan = _read_omo("plans/phase9-program-plan.md")

    closeout_summary = OMO_ROOT / "summaries" / "phase9-wave2-closeout.md"
    done_task = OMO_ROOT / "tasks" / "done" / "P9-W2-SPACE-REGISTRY-FOUNDATION.yaml"
    active_task = OMO_ROOT / "tasks" / "active" / "P9-W2-SPACE-REGISTRY-FOUNDATION.yaml"

    assert closeout_summary.exists()
    assert done_task.exists()
    assert not active_task.exists()

    done_task_text = done_task.read_text(encoding="utf-8")
    assert "status: done" in done_task_text
    assert "review_ref: .omo/summaries/phase9-wave2-closeout.md" in done_task_text
    assert "completed_at:" in done_task_text
    assert "completion_summary:" in done_task_text

    assert "phase9-wave2-closeout.md" in root_index
    assert "phase9-wave2-closeout.md" in process_index
    assert "phase9-wave2-closeout.md" in program_plan


def test_phase9_wave3_packet_is_seeded_with_membership_anchor() -> None:
    root_index = _read_omo("INDEX.md")
    plans_index = _read_omo("plans/README.md")
    control_index = _read_omo("_control/INDEX.md")
    task_readme = _read_omo("tasks/README.md")
    program_plan = _read_omo("plans/phase9-program-plan.md")

    wave3_plan_path = OMO_ROOT / "plans" / "phase9-wave3-execution-plan.md"
    done_task = OMO_ROOT / "tasks" / "done" / "P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml"

    assert wave3_plan_path.exists()
    assert done_task.exists()

    wave3_plan = wave3_plan_path.read_text(encoding="utf-8")
    done_task_text = done_task.read_text(encoding="utf-8")

    assert "phase9-wave3-execution-plan.md" in root_index
    assert "phase9-wave3-execution-plan.md" in plans_index
    assert "phase9-wave3-execution-plan.md" in program_plan
    assert "Wave 3" in control_index
    assert "Wave 3" in task_readme

    assert "actor + space membership" in wave3_plan
    assert "status: done" in done_task_text
    assert "run_ref: .omo/workers/runs/phase9-wave3-identity-admission-dispatch.yaml" in done_task_text
    assert "review_ref: .omo/summaries/phase9-wave3-closeout.md" in done_task_text
    assert "phase9-wave3-execution-plan.md" in done_task_text
    assert "phase9-wave2-closeout.md" in done_task_text


def test_phase9_wave3_closeout_is_recorded_and_archived() -> None:
    root_index = _read_omo("INDEX.md")
    process_index = _read_omo("_knowledge/process/INDEX.md")
    program_plan = _read_omo("plans/phase9-program-plan.md")

    closeout_summary = OMO_ROOT / "summaries" / "phase9-wave3-closeout.md"
    done_task = OMO_ROOT / "tasks" / "done" / "P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml"
    active_task = OMO_ROOT / "tasks" / "active" / "P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml"
    approval_record = OMO_ROOT / "workers" / "runs" / "phase9-wave3-identity-admission-approval.yaml"
    envelope = OMO_ROOT / "workers" / "runs" / "phase9-wave3-identity-admission-envelope.yaml"

    assert closeout_summary.exists()
    assert done_task.exists()
    assert not active_task.exists()
    assert approval_record.exists()
    assert envelope.exists()

    done_task_text = done_task.read_text(encoding="utf-8")
    approval_record_text = approval_record.read_text(encoding="utf-8")
    envelope_text = envelope.read_text(encoding="utf-8")
    assert "status: done" in done_task_text
    assert "review_ref: .omo/summaries/phase9-wave3-closeout.md" in done_task_text
    assert "approval_ref: .omo/workers/runs/phase9-wave3-identity-admission-approval.yaml" in done_task_text
    assert "completed_at:" in done_task_text
    assert "completion_summary:" in done_task_text
    assert ".omo/tasks/done/P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml" in approval_record_text
    assert ".omo/summaries/phase9-wave3-closeout.md" in approval_record_text
    assert ".omo/tasks/done/P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml" in envelope_text
    assert ".omo/tasks/active/P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml" not in approval_record_text
    assert ".omo/tasks/active/P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml" not in envelope_text

    assert "phase9-wave3-closeout.md" in root_index
    assert "phase9-wave3-closeout.md" in process_index
    assert "phase9-wave3-closeout.md" in program_plan
