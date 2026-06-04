# Phase 5 Wave 0 Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start Phase 5 through a real G5.0 / Wave 0 kickoff: seed the execution-ready task queue, dispatch bounded worker tasks, validate the worker mechanism, and record the first Wave 0 retrospective.

**Architecture:** This plan treats Wave 0 as a control-plane and knowledge-plane execution packet, not runtime feature delivery. The coordinator seeds `G5.0`, creates execution-grade task YAMLs, dispatches two bounded L1 documentation tasks to external workers, then reviews outputs and closes the kickoff with validation and retrospective evidence.

**Tech Stack:** Markdown, YAML, Python 3, `scripts/omo_worker.py`, `scripts/sync_omo_state.py`, pytest

---

## File structure

- Create: `.omo/plans/phase5-wave0-task-specs.md` — Wave 0 task specification source
- Create: `.omo/plans/phase5-wave0-execution-plan.md` — this execution plan
- Create: `.omo/tasks/active/P5-w0-landing-model-freeze.yaml`
- Create: `.omo/tasks/active/P5-w0-secrets-ownership-decision.yaml`
- Create: `.omo/tasks/active/P5-w0-hermes-compatibility-contract.yaml`
- Create: `.omo/tasks/active/P5-w0-proposal-model-freeze.yaml`
- Create: `.omo/tasks/active/P5-w0-review-refresh-packet.yaml`
- Create: `.omo/tasks/done/P5-w0-goal-task-seeding.yaml`
- Create: `.omo/_knowledge/design/phase5-hermes-contract.md`
- Create: `.omo/_knowledge/management/phase5-review-refresh-2026-05-31.md`
- Create: `.omo/summaries/phase5-wave0-kickoff-retrospective.md`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/INDEX.md`
- Modify: `.omo/_control/INDEX.md`
- Modify: `.omo/plans/README.md`
- Test: `.omo/tests/test_phase5_wave0_docs.py`

### Task 1: Seed G5.0 control state

**Files:**
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/_control/INDEX.md`
- Modify: `.omo/INDEX.md`
- Test: `.omo/tests/test_phase5_wave0_docs.py`

- [ ] **Step 1: Write the failing test**

```python
def test_phase5_wave0_kickoff_is_recorded():
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    assert "phase: 5" in goals
    assert "id: G5.0" in goals
    assert "current_phase: 5" in system
    assert "phase5_status: wave0_in_progress" in system
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_phase5_wave0_docs.py -q`
Expected: FAIL because Phase 4 is still current and the Wave 0 plan files do not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
# .omo/goals/current.yaml
phase: 5
status: in_progress
current_wave: 0
goals:
  - id: G5.0
    desc: "Wave 0 — entry gate and landing model freeze"
    kpi: "6 Wave 0 kickoff tasks seeded; 2 worker dispatches launched; kickoff validation and retrospective recorded"
    progress: 1
    status: in_progress
```

```yaml
# .omo/state/system.yaml
current_phase: 5
phase_status: in_progress
current_wave: 0
next_milestone: Phase 5 Wave 0 entry gate
phase5_status: wave0_in_progress
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest .omo/tests/test_phase5_wave0_docs.py -q`
Expected: PASS once the kickoff state and linked docs exist.

- [ ] **Step 5: Commit**

```bash
git add .omo/goals/current.yaml .omo/state/system.yaml .omo/_control/INDEX.md .omo/INDEX.md .omo/tests/test_phase5_wave0_docs.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): kick off phase5 wave0 controls"
```

### Task 2: Create Wave 0 task specifications and task YAMLs

**Files:**
- Create: `.omo/plans/phase5-wave0-task-specs.md`
- Create: `.omo/tasks/active/P5-w0-landing-model-freeze.yaml`
- Create: `.omo/tasks/active/P5-w0-secrets-ownership-decision.yaml`
- Create: `.omo/tasks/active/P5-w0-hermes-compatibility-contract.yaml`
- Create: `.omo/tasks/active/P5-w0-proposal-model-freeze.yaml`
- Create: `.omo/tasks/active/P5-w0-review-refresh-packet.yaml`
- Create: `.omo/tasks/done/P5-w0-goal-task-seeding.yaml`
- Modify: `.omo/plans/README.md`
- Test: `.omo/tests/test_phase5_wave0_docs.py`

- [ ] **Step 1: Extend the failing test with task-spec expectations**

```python
for rel_path in [
    "plans/phase5-wave0-execution-plan.md",
    "plans/phase5-wave0-task-specs.md",
    "tasks/active/P5-w0-landing-model-freeze.yaml",
    "tasks/active/P5-w0-secrets-ownership-decision.yaml",
    "tasks/active/P5-w0-hermes-compatibility-contract.yaml",
    "tasks/active/P5-w0-proposal-model-freeze.yaml",
    "tasks/active/P5-w0-review-refresh-packet.yaml",
    "tasks/done/P5-w0-goal-task-seeding.yaml",
]:
    assert (OMO_ROOT / rel_path).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_phase5_wave0_docs.py -q`
Expected: FAIL because the Wave 0 specs and task YAMLs are missing.

- [ ] **Step 3: Write minimal implementation**

```yaml
# .omo/tasks/active/P5-w0-hermes-compatibility-contract.yaml
id: P5-W0-HERMES-COMPATIBILITY-CONTRACT
phase: 5
milestone: W0
priority: P0
title: Freeze Hermes ingress and memory contract for Phase 5
status: pending
deliverables:
  - .omo/_knowledge/design/phase5-hermes-contract.md
```

```markdown
# .omo/plans/phase5-wave0-task-specs.md
## Wave 0 task catalog
1. P5-W0-LANDING-MODEL-FREEZE
2. P5-W0-SECRETS-OWNERSHIP-DECISION
3. P5-W0-HERMES-COMPATIBILITY-CONTRACT
4. P5-W0-PROPOSAL-MODEL-FREEZE
5. P5-W0-REVIEW-REFRESH-PACKET
6. P5-W0-GOAL-TASK-SEEDING
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest .omo/tests/test_phase5_wave0_docs.py -q`
Expected: PASS with the task spec and YAML packet present.

- [ ] **Step 5: Commit**

```bash
git add .omo/plans/phase5-wave0-task-specs.md .omo/tasks/active/P5-w0-*.yaml .omo/tasks/done/P5-w0-goal-task-seeding.yaml .omo/plans/README.md
git -c core.hooksPath=/dev/null commit -m "feat(omo): seed phase5 wave0 task packet"
```

### Task 3: Dispatch two bounded worker tasks

**Files:**
- Modify: `.omo/tasks/active/P5-w0-hermes-compatibility-contract.yaml`
- Modify: `.omo/tasks/active/P5-w0-review-refresh-packet.yaml`
- Create: `.omo/workers/runs/*`
- Create: `.omo/_knowledge/design/phase5-hermes-contract.md`
- Create: `.omo/_knowledge/management/phase5-review-refresh-2026-05-31.md`

- [ ] **Step 1: Validate active task schema before dispatch**

Run: `python3 scripts/omo_worker.py task validate --all-active`
Expected: PASS with no schema errors for the Wave 0 packet.

- [ ] **Step 2: Dispatch Hermes contract to codebuddy**

Run:

```bash
python3 scripts/omo_worker.py worker dispatch P5-W0-HERMES-COMPATIBILITY-CONTRACT \
  --worker codebuddy \
  --write-path .omo/_knowledge/design/phase5-hermes-contract.md \
  --launch
```

Expected: task preclaimed to `codebuddy`, dispatch artifact bundle created, worker launched.

- [ ] **Step 3: Dispatch review refresh to reasonix**

Run:

```bash
python3 scripts/omo_worker.py worker dispatch P5-W0-REVIEW-REFRESH-PACKET \
  --worker reasonix \
  --write-path .omo/_knowledge/management/phase5-review-refresh-2026-05-31.md \
  --launch
```

Expected: task preclaimed to `reasonix`, dispatch artifact bundle created, worker launched.

- [ ] **Step 4: Inspect outputs and move each worker task to review or reclaim**

Run:

```bash
python3 scripts/omo_worker.py worker status
```

Expected: both tasks appear with `dispatch_state`, checkpoint/review refs, and evidence paths suitable for coordinator review.

- [ ] **Step 5: Commit**

```bash
git add .omo/tasks/active/P5-w0-hermes-compatibility-contract.yaml .omo/tasks/active/P5-w0-review-refresh-packet.yaml .omo/workers/runs .omo/_knowledge/design/phase5-hermes-contract.md .omo/_knowledge/management/phase5-review-refresh-2026-05-31.md
git -c core.hooksPath=/dev/null commit -m "feat(omo): launch phase5 wave0 worker probes"
```

### Task 4: Validate kickoff state and sync runtime view

**Files:**
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/tasks/active/*.yaml`
- Test: `.omo/tests/test_phase5_wave0_docs.py`

- [ ] **Step 1: Run the kickoff docs test again**

Run: `python3 -m pytest .omo/tests/test_phase5_wave0_docs.py -q`
Expected: PASS.

- [ ] **Step 2: Sync OMO runtime state**

Run: `python3 scripts/sync_omo_state.py --omo-dir .omo`
Expected: `state/system.yaml` refreshed with active queue, divergence flags, and task gate summary for Wave 0.

- [ ] **Step 3: Run the OMO regression suite**

Run: `python3 -m pytest .omo/tests -q`
Expected: PASS with all governance/doc tests green.

- [ ] **Step 4: Review worker outputs and add completion summaries where ready**

```yaml
review_ref: .omo/workers/runs/<dispatch-id>-review.md
completion_summary: "Coordinator reviewed kickoff worker output and accepted the deliverable for Wave 0 use."
```

- [ ] **Step 5: Commit**

```bash
git add .omo/state/system.yaml .omo/goals/current.yaml .omo/tasks/active .omo/tasks/done .omo/tests
git -c core.hooksPath=/dev/null commit -m "test(omo): validate phase5 wave0 kickoff"
```

### Task 5: Record retrospective and next iteration

**Files:**
- Create: `.omo/summaries/phase5-wave0-kickoff-retrospective.md`
- Modify: `.omo/_knowledge/process/INDEX.md`
- Modify: `.omo/_delivery/INDEX.md`

- [ ] **Step 1: Write the kickoff retrospective**

```markdown
# Phase 5 Wave 0 kickoff retrospective
## What started
## What worker dispatch proved
## What remains blocked
## Iteration adjustments
```

- [ ] **Step 2: Link the retrospective from process and delivery indexes**

```markdown
| [phase5-wave0-kickoff-retrospective.md](../../summaries/phase5-wave0-kickoff-retrospective.md) | Phase 5 Wave 0 kickoff validation and iteration summary |
```

- [ ] **Step 3: Re-run full OMO tests**

Run: `python3 -m pytest .omo/tests -q`
Expected: PASS.

- [ ] **Step 4: Confirm the next step**

Expected: G5.0 stays in progress with a live active queue and a recorded iteration packet; Wave 1 remains gated.

- [ ] **Step 5: Commit**

```bash
git add .omo/summaries/phase5-wave0-kickoff-retrospective.md .omo/_knowledge/process/INDEX.md .omo/_delivery/INDEX.md
git -c core.hooksPath=/dev/null commit -m "docs(omo): record phase5 wave0 kickoff retrospective"
```
