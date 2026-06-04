from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_wave2_docs_define_canonical_status_vs_gate_facts():
    readme = _read("tasks/README.md")
    gate_model_path = OMO_ROOT / "standards/task-gate-model.md"

    assert gate_model_path.exists()

    gate_model = gate_model_path.read_text(encoding="utf-8")

    assert "task.status is the canonical truth-plane field" in readme
    assert "Gate facts are derived from task/run evidence" in gate_model
    assert "`dispatched` is not a task.status enum" in gate_model
    assert "Promotion to `done` requires review evidence" in gate_model


def test_phase4_wave2_closure_recorded_in_goals_state_and_indexes():
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    truth_index = _read("_truth/INDEX.md")
    delivery_index = _read("_delivery/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")

    assert "phase4_worker_collab_status: wave2_completed" in system
    assert "phase4_worker_collab_status: wave2_completed" in system

    for rel_path in [
        "tasks/done/P4-w2-lifecycle-gate-hardening.yaml",
        "tasks/done/P4-w2-divergence-triage.yaml",
        "tasks/done/P4-w2-worker-utilization-baseline.yaml",
        "tasks/done/P4-w2-handoff-index.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase6-wave1-execution-plan.md" in root_index
    assert "当前执行焦点" in root_index
    assert "当前状态快照" in control_index
    assert "task-gate-model.md" in truth_index
    assert "PILOT-WORKER-RECLAIM-HANDOFF-VALIDATION.md" in delivery_index
    assert "phase5-program-architecture.md" in design_index
    assert "p4-wave2-closure-retrospective.md" in process_index
