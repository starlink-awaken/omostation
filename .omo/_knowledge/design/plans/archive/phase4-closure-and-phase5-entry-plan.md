# Phase 4 Closure and Phase 5 Entry Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Phase 4 Wave 2 hardening work, produce the Phase 4 retrospective, and leave a clean entry gate for Phase 5 without starting Phase 5 runtime implementation.

**Architecture:** Keep Phase 4 focused on execution-governance hardening inside the current `.omo` surface: tighten lifecycle semantics, turn divergence into structured artifacts, generate real delivery evidence, and close the Wave 2 tasks. In parallel, write the entry architecture that constrains how Phase 5 can begin, but do not start Task Center runtime features yet.

**Tech Stack:** Python 3, YAML, markdown docs, existing `.omo` scripts, pytest

---

## File structure

- Create: `.omo/_knowledge/design/phase5-entry-architecture.md` — bridge design between current Phase 4 reality and Phase 5 requirements
- Create: `.omo/summaries/p4-wave2-closure-retrospective.md` — closeout retrospective and Phase 5 entry judgment
- Modify: `scripts/sync_omo_state.py` — compact structured divergence outputs instead of blob-only flags
- Modify: `scripts/omo_metrics.py` — richer utilization metrics and reporting period
- Modify: `scripts/omo_handoff_index.py` — deeper chase path across dispatch/reclaim/review/summary evidence
- Modify: `.omo/tests/test_omo_automation.py` — TDD coverage for divergence artifactization, richer utilization, and handoff chain indexing
- Modify: `.omo/tasks/active/P4-w2-*.yaml` and matching done files — close the four Wave 2 tasks with summaries/evidence
- Modify: `.omo/goals/current.yaml`, `.omo/state/system.yaml`, `.omo/_knowledge/design/INDEX.md`, `.omo/_knowledge/process/INDEX.md`, `.omo/_delivery/INDEX.md` — reflect closure and entry state

## Task 1: Freeze the Phase 5 entry boundary

**Files:**
- Create: `.omo/_knowledge/design/phase5-entry-architecture.md`
- Modify: `.omo/_knowledge/design/INDEX.md`

- [ ] **Step 1: Write the bridge design**
- [ ] **Step 2: Link it from the design index**
- [ ] **Step 3: Verify the design doc is internally consistent**

## Task 2: Turn orphaned task drift into a structured artifact

**Files:**
- Modify: `scripts/sync_omo_state.py`
- Modify: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing test for orphaned task artifactization**
- [ ] **Step 2: Run the focused test and watch it fail**
- [ ] **Step 3: Write the minimal sync-state implementation**
- [ ] **Step 4: Re-run the focused test**
- [ ] **Step 5: Re-run `.omo/tests/test_omo_automation.py`**

## Task 3: Upgrade the utilization baseline from snapshot to decision signal

**Files:**
- Modify: `scripts/omo_metrics.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/summaries/worker-utilization-baseline.md`

- [ ] **Step 1: Write the failing utilization test for period/review/handoff metrics**
- [ ] **Step 2: Run the focused test and watch it fail**
- [ ] **Step 3: Implement the richer metric aggregation**
- [ ] **Step 4: Regenerate the markdown artifact**
- [ ] **Step 5: Re-run the focused and broader tests**

## Task 4: Materialize a real handoff evidence corpus

**Files:**
- Modify: `scripts/omo_handoff_index.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Create/refresh: `.omo/evidence/handoffs/*.md`

- [ ] **Step 1: Write the failing handoff-chain test**
- [ ] **Step 2: Run the focused test and watch it fail**
- [ ] **Step 3: Implement chain chasing across dispatch, reclaim, successor, review, and completion summary**
- [ ] **Step 4: Generate at least one real handoff index artifact from existing pilot evidence**
- [ ] **Step 5: Re-run the focused and broader tests**

## Task 5: Close the Wave 2 tasks and write the retrospective

**Files:**
- Modify: `.omo/tasks/active/P4-w2-*.yaml`
- Create or move to done: `.omo/tasks/done/P4-w2-*.yaml`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/_delivery/INDEX.md`
- Modify: `.omo/_knowledge/process/INDEX.md`
- Create: `.omo/summaries/p4-wave2-closure-retrospective.md`

- [ ] **Step 1: Update each Wave 2 task with completion evidence and move it to done**
- [ ] **Step 2: Mark `G4.2` complete and update Phase 4 state**
- [ ] **Step 3: Write the retrospective with outcomes, misses, and Phase 5 entry conditions**
- [ ] **Step 4: Link the retrospective from process/delivery indexes**
- [ ] **Step 5: Run `python3 -m pytest .omo/tests -q`**
