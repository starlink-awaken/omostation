from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase12_completion_and_phase13_plus_backlog_boundaries_are_registered() -> None:
    plans_readme = _read("plans/README.md")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    management_index = _read("_knowledge/management/INDEX.md")
    review = _read("_knowledge/management/phase12-13-cross-review-2026-06-01.md")
    review_1214 = _read("_knowledge/management/phase12-14-cross-review-2026-06-01.md")
    review_15 = _read("_knowledge/management/phase15-cross-review-2026-05-31.md")
    architecture_1214 = _read("_knowledge/design/phase12-14-architecture-design.md")
    architecture_15 = _read("_knowledge/design/phase15-autonomous-governance-design.md")
    phase12 = _read("plans/phase12-planning-gate.md")
    phase12_program = _read("plans/phase12-program-plan.md")
    phase12_wave3 = _read("plans/phase12-wave3-execution-plan.md")
    phase12_wave4 = _read("plans/phase12-wave4-execution-plan.md")
    phase12_wave5 = _read("plans/phase12-wave5-execution-plan.md")
    phase13 = _read("plans/phase13-metacognition-preplanning.md")
    phase14 = _read("plans/phase14-deferred-ecosystem-backlog.md")
    phase15 = _read("plans/phase15-autonomous-governance-preplanning.md")
    wave4 = _read("plans/phase11-wave4-execution-plan.md")

    assert "phase12-planning-gate.md" in plans_readme
    assert "phase12-program-plan.md" in plans_readme
    assert "phase14-deferred-ecosystem-backlog.md" in plans_readme
    assert "phase15-autonomous-governance-preplanning.md" in plans_readme
    assert "phase13-metacognition-preplanning.md" in plans_readme
    assert "Phase 12" in root_index
    assert "phase12-planning-gate.md" in control_index
    assert "phase12-program-plan.md" in design_index
    assert "phase12-14-architecture-design.md" in design_index
    assert "phase15-autonomous-governance-design.md" in design_index
    assert "phase12-14-cross-review-2026-06-01.md" in management_index
    assert "phase15-cross-review-2026-05-31.md" in management_index
    assert "phase13-metacognition-preplanning.md" in design_index
    assert "phase14-deferred-ecosystem-backlog.md" in design_index
    assert "phase15-autonomous-governance-preplanning.md" in design_index

    assert "Status: completed" in phase12
    assert "Canonical program: `phase12-program-plan.md`" in phase12
    assert "Entry gate: Phase 11 Wave 4 closeout GO" in phase12
    assert "Phase 12 task packets have not been added to `tasks/active/` before human approval" in phase12
    assert "one fusion pilot" in phase12

    assert "Canonical: yes" in phase12_program
    assert "状态: completed" in phase12_program
    assert "Wave 4 — 架构验证 + 红队 + P13/P14 交接" in phase12_program
    assert "Phase 14 deferred backlog 已登记" in phase12_program
    assert "状态: completed" in phase12_wave3
    assert "状态: completed" in phase12_wave4
    assert "单一融合 pilot" in phase12_wave3
    assert "Phase 14 backlog" in phase12_wave3
    assert "P13/P14 交接" in phase12_wave4
    assert "Status: merged_into_wave4" in phase12_wave5
    assert "Do not create `P12-W5-AUDIT-CLOSEOUT` as an active task" in phase12_wave5

    assert "Status: completed" in phase13
    assert "Entry gate: Phase 12 closeout GO + explicit human approval" in phase13
    assert "Supersedes as planning source: `archive/phase13-metacognition.md`" in phase13
    assert "Auto-apply remains disabled by default" in phase13
    assert "capability registry, scenario trace, one fusion pilot" in phase13
    assert ".omo/evidence/phase13/metacognition-baseline.yaml" in phase13
    assert ".omo/summaries/phase13-closeout.md" in phase13

    assert "Status: completed" in phase14
    assert "Multi-project deep absorption" in phase14
    assert "Architecture pattern absorption" in phase14

    assert "Status: completed" in phase15
    assert "Entry gate: Phase 14 closeout GO + explicit human approval" in phase15
    assert "Governance evidence ledger" in phase15
    assert "Policy-as-tests" in phase15
    assert "Proposal-to-task compiler" in phase15
    assert "Do not create Phase 15 active tasks" in phase15
    assert "project health and a governed user-value loop" in phase15

    assert "Phase 12/13 are not execution-ready" in review
    assert "phase14-deferred-ecosystem-backlog.md" in review
    assert "Phase 12 capability ecosystem foundation" in architecture_1214
    assert "Promotion envelope" in architecture_1214
    assert "Mutation gate" in architecture_1214
    assert "Phase 15 supervised autonomous governance loop" in architecture_15
    assert "Compilation is not activation" in architecture_15
    assert "Proposal-to-task compiler output must be inactive by construction" in architecture_15
    assert "Auto-apply remains disabled by default" in architecture_15
    assert "Deferred scope ledger" in review_1214
    assert "Do not create Phase 12, 13, or 14 active tasks" in review_1214
    assert "Do not create Phase 15 active tasks" in review_15
    assert "Inactive task draft envelope" in review_15
    assert "phase12-planning-gate.md" in wave4
    assert "phase13-metacognition-preplanning.md" in wave4
