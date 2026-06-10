from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase5_wave0_kickoff_is_recorded():
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    delivery_index = _read("_delivery/INDEX.md")
    plans_readme = _read("plans/README.md")

    assert "phase5_status: completed" in system

    for rel_path in [
        "plans/phase5-wave0-execution-plan.md",
        "plans/phase5-wave0-task-specs.md",
        "tasks/done/P5-w0-goal-task-seeding.yaml",
        "tasks/done/P5-w0-hermes-compatibility-contract.yaml",
        "tasks/done/P5-w0-landing-model-freeze.yaml",
        "tasks/done/P5-w0-proposal-model-freeze.yaml",
        "tasks/done/P5-w0-review-refresh-packet.yaml",
        "tasks/done/P5-w0-secrets-ownership-decision.yaml",
        "summaries/phase5-wave0-kickoff-retrospective.md",
        "summaries/phase5-wave0-closeout-retrospective.md",
        "evidence/handoffs/P5-W0-LANDING-MODEL-FREEZE.md",
        "evidence/handoffs/P5-W0-HERMES-COMPATIBILITY-CONTRACT.md",
        "evidence/handoffs/P5-W0-REVIEW-REFRESH-PACKET.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase5-wave0-execution-plan.md" in root_index
    assert "phase5-wave0-task-specs.md" in root_index
    assert "phase5-wave0-kickoff-retrospective.md" in process_index
    assert "phase5-wave0-closeout-retrospective.md" in process_index
    assert "P5-W0-LANDING-MODEL-FREEZE.md" in delivery_index
    assert "P5-W0-HERMES-COMPATIBILITY-CONTRACT.md" in delivery_index
    assert "P5-W0-REVIEW-REFRESH-PACKET.md" in delivery_index
    assert "phase5-wave0-execution-plan.md" in plans_readme
    assert "phase5-wave0-task-specs.md" in plans_readme
