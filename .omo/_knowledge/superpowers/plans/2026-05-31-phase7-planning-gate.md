# Phase 7 Planning Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ratify Phase 7 through a planning-gate packet that defines the new program, seeds exactly one execution-ready starter packet, and keeps residual governance debt explicit.

**Architecture:** Add a new Phase 7 documentation-and-control packet under `.omo/` that follows the same ratification pattern used in Phase 6: test the final control-plane state first, then create the planning/program/spec docs, seed one active starter packet, and update indexes plus live state together. Preserve the current `orphaned_tasks:1` as tracked follow-up metadata rather than hiding it.

**Tech Stack:** Markdown docs, YAML control/task state, Python pytest doc-regression tests, existing `.omo` automation scripts

---

### Task 1: Add the Phase 7 ratification regression

**Files:**
- Create: `.omo/tests/test_phase7_planning_gate_docs.py`
- Modify: `.omo/tests/test_phase6_completion_docs.py`
- Test: `.omo/tests/test_phase7_planning_gate_docs.py`

- [ ] **Step 1: Write the failing Phase 7 doc test**

```python
from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase7_planning_gate_is_ratified() -> None:
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    assert "phase: 7" in goals
    assert "status: in_progress" in goals
    assert "current_wave: 1" in goals
    assert "id: G7.1" in goals
    assert "id: G7.2" in goals
    assert "id: G7.3" in goals

    assert "current_phase: 7" in system
    assert "phase_status: in_progress" in system
    assert "next_milestone: Phase 7 Wave 1 user journey enablement" in system
    assert "active_tasks: 1" in system

    for rel_path in [
        "plans/phase7-planning-gate.md",
        "plans/phase7-program-plan.md",
        "plans/phase7-starter-packet-spec.md",
        "tasks/active/P7-w1-user-journey-enablement.yaml",
        "tasks/done/P7-r0-phase7-planning-gate.yaml",
        "summaries/phase7-planning-ratification.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase7-planning-gate.md" in root_index
    assert "phase7-program-plan.md" in control_index
    assert "phase7-planning-ratification.md" in process_index
    assert "phase7-program-plan.md" in design_index
    assert "phase7-starter-packet-spec.md" in plans_readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_phase7_planning_gate_docs.py -q`

Expected: FAIL because Phase 7 files and live state do not exist yet.

- [ ] **Step 3: Relax the old Phase 6 completion test into historical assertions only**

```python
def test_phase6_completion_is_recorded() -> None:
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")

    assert "plans/phase6-program-plan.md".split("/")[-1] in root_index
    assert "tasks/done/P6-g3-skill-federation-packet.yaml".split("/")[-1]
    assert "phase: 6" not in goals or "phase: 7" in goals
    assert "current_phase: 6" not in system or "current_phase: 7" in system
```

- [ ] **Step 4: Run both tests to verify the new failure is the only meaningful red**

Run: `python3 -m pytest .omo/tests/test_phase6_completion_docs.py .omo/tests/test_phase7_planning_gate_docs.py -q`

Expected: the Phase 7 test fails on missing Phase 7 artifacts/state; the historical Phase 6 test passes.

- [ ] **Step 5: Commit**

```bash
git add .omo/tests/test_phase6_completion_docs.py .omo/tests/test_phase7_planning_gate_docs.py
git commit -m "test(phase7): add planning gate ratification regression"
```

### Task 2: Write the Phase 7 planning-gate artifacts

**Files:**
- Create: `.omo/plans/phase7-planning-gate.md`
- Create: `.omo/plans/phase7-program-plan.md`
- Create: `.omo/plans/phase7-starter-packet-spec.md`
- Create: `.omo/summaries/phase7-planning-ratification.md`
- Modify: `.omo/plans/README.md`

- [ ] **Step 1: Write the planning-gate doc**

```md
# Phase 7 planning gate

## Goal

Turn Phase 7 into a ratifiable control packet without starting execution prematurely.

## Gate checklist

1. Program structure is explicit
2. Starter packet scope is explicit
3. `orphaned_tasks:1` is recorded as tracked follow-up
4. No more than one execution-ready packet may be seeded at ratification

## GO/NO-GO rule

GO only if the starter packet stays within D2 enablement scope and does not hide governance debt.
```

- [ ] **Step 2: Write the program plan**

```md
# Phase 7 program plan

## Waves

1. G7.1 / Wave 1 — user journey enablement
2. G7.2 / Wave 2 — resource accounting visibility
3. G7.3 / Wave 3 — freshness entropy automation

## Exit criteria

- D2 coverage lifted by landing the Wave 1 journey
- D9 visibility established by accounting artifacts
- D6 freshness automation structured and persisted
```

- [ ] **Step 3: Write the starter packet spec**

```md
# Phase 7 starter packet spec

Packet: `P7-W1-USER-JOURNEY-ENABLEMENT`

## Scope

1. Hermes self-context preload
2. TaskObject bridge for complex tasks
3. Consensus auto-marking on positive confirmation
4. First freshness report and D2 reassessment

## Follow-up constraint

`orphaned_tasks:1` must be triaged explicitly before Wave 1 closeout.
```

- [ ] **Step 4: Write the ratification summary**

```md
# Phase 7 planning ratification

## Verdict

**GO** — Phase 7 can enter Wave 1 with exactly one execution-ready packet.

## Residual governance note

`orphaned_tasks:1` is tracked follow-up, not silently cleared.
```

- [ ] **Step 5: Register the new plans in `.omo/plans/README.md`**

```md
| `phase7-planning-gate.md` | 7 | active | Phase 7 planning gate packet |
| `phase7-program-plan.md` | 7 | active | Phase 7 master program plan |
| `phase7-starter-packet-spec.md` | 7 | active | Phase 7 Wave 1 starter packet spec |
```

- [ ] **Step 6: Commit**

```bash
git add .omo/plans/phase7-planning-gate.md .omo/plans/phase7-program-plan.md .omo/plans/phase7-starter-packet-spec.md .omo/summaries/phase7-planning-ratification.md .omo/plans/README.md
git commit -m "docs(phase7): add planning gate artifacts"
```

### Task 3: Ratify Phase 7 in live control and seed one starter packet

**Files:**
- Create: `.omo/tasks/active/P7-w1-user-journey-enablement.yaml`
- Create: `.omo/tasks/done/P7-r0-phase7-planning-gate.yaml`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/_control/INDEX.md`
- Modify: `.omo/INDEX.md`
- Modify: `.omo/_knowledge/design/INDEX.md`
- Modify: `.omo/_knowledge/process/INDEX.md`

- [ ] **Step 1: Add the active starter packet**

```yaml
id: P7-W1-USER-JOURNEY-ENABLEMENT
phase: 7
milestone: W1
priority: P0
title: Land the Phase 7 Wave 1 user journey enablement packet
status: pending
assigned_to: null
dispatch_id: null
run_ref: null
approval_ref: null
review_ref: null
knowledge_refs: []
handoff_refs: []
source_docs:
  - .omo/plans/phase7-planning-gate.md
  - .omo/plans/phase7-program-plan.md
  - .omo/plans/phase7-starter-packet-spec.md
deliverables:
  - .omo/summaries/phase7-wave1-closeout.md
risk_level: L1
allowed_operation_level: L1
human_approval_required: false
entry_gate:
  - Phase 7 planning gate ratified
  - orphaned_tasks:1 triage decision recorded before closeout
evidence_required:
  - D2 journey gaps are mapped to concrete runtime seams
test_plan:
  - python3 scripts/omo_worker.py task validate --all-active
  - python3 scripts/sync_omo_state.py --omo-dir .omo
```

- [ ] **Step 2: Add the done ratification packet**

```yaml
id: P7-R0-PHASE7-PLANNING-GATE
phase: 7
milestone: R0
priority: P0
title: Ratify the Phase 7 planning gate and seed Wave 1 only
status: done
assigned_to: copilot-cli
dispatch_id: phase7-r0-planning-gate
run_ref: .omo/plans/phase7-program-plan.md
approval_ref: null
review_ref: .omo/summaries/phase7-planning-ratification.md
knowledge_refs: []
handoff_refs: []
source_docs:
  - .omo/plans/phase7-planning-gate.md
  - .omo/plans/phase7-program-plan.md
  - .omo/plans/phase7-starter-packet-spec.md
deliverables:
  - .omo/goals/current.yaml
  - .omo/state/system.yaml
  - .omo/_control/INDEX.md
  - .omo/summaries/phase7-planning-ratification.md
risk_level: L1
allowed_operation_level: L1
human_approval_required: false
entry_gate:
  - Phase 6 completed
  - Phase 7 planning artifacts approved
evidence_required:
  - live control/state points to Phase 7 Wave 1 only
  - one execution-ready packet is seeded in tasks/active
test_plan:
  - python3 scripts/omo_worker.py task validate --all-active
  - python3 scripts/sync_omo_state.py --omo-dir .omo
```

- [ ] **Step 3: Promote live control to Phase 7**

```yaml
# .omo/goals/current.yaml
phase: 7
status: in_progress
current_wave: 1
goals:
  - id: G7.1
    desc: "Wave 1 — user journey enablement"
    status: in_progress
    tasks: [P7-W1-USER-JOURNEY-ENABLEMENT]
  - id: G7.2
    desc: "Wave 2 — resource accounting visibility"
    status: gated
  - id: G7.3
    desc: "Wave 3 — freshness entropy automation"
    status: gated
```

```yaml
# .omo/state/system.yaml
current_phase: 7
phase_status: in_progress
current_wave: 1
next_milestone: Phase 7 Wave 1 user journey enablement
active_tasks: 1
phase7_status: in_progress
```

- [ ] **Step 4: Update the root/control/design/process indexes**

```md
- **当前完成 phase / next gate**: Phase 7（in_progress）
- **当前 Phase 7 program packet**: [phase7-program-plan.md](../plans/phase7-program-plan.md)
- **当前 Phase 7 execution packet**: [phase7-starter-packet-spec.md](../plans/phase7-starter-packet-spec.md)
- **下一 Gate**: P7-W1 exit judgment
```

- [ ] **Step 5: Run the ratification doc tests**

Run: `python3 -m pytest .omo/tests/test_phase6_completion_docs.py .omo/tests/test_phase7_planning_gate_docs.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .omo/goals/current.yaml .omo/state/system.yaml .omo/_control/INDEX.md .omo/INDEX.md .omo/_knowledge/design/INDEX.md .omo/_knowledge/process/INDEX.md .omo/tasks/active/P7-w1-user-journey-enablement.yaml .omo/tasks/done/P7-r0-phase7-planning-gate.yaml
git commit -m "feat(phase7): ratify planning gate and seed wave1"
```

### Task 4: Validate the whole control plane

**Files:**
- Verify only: `.omo/tests/`
- Verify only: `scripts/sync_omo_state.py`
- Verify only: `scripts/omo_worker.py`

- [ ] **Step 1: Sync the derived state**

Run: `python3 scripts/sync_omo_state.py --omo-dir .omo`

Expected: completes without errors and preserves `current_phase: 7`.

- [ ] **Step 2: Validate the active queue**

Run: `python3 scripts/omo_worker.py task validate --all-active`

Expected: no output, exit code 0.

- [ ] **Step 3: Run the full `.omo` regression**

Run: `python3 -m pytest .omo/tests -q`

Expected: all tests pass.

- [ ] **Step 4: Check worker status**

Run: `python3 scripts/omo_worker.py worker status`

Expected: shows no broken dispatch state and a coherent active queue snapshot.

- [ ] **Step 5: Commit any final fixes**

```bash
git add .omo scripts
git commit -m "test(phase7): verify planning gate control plane"
```
