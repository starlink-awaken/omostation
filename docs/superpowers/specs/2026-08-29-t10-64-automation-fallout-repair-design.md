---
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-64
spec_version: 1.0.0
title: T10-58 Automation Fallout Repair — Design
type: doc
---

# T10-58 Automation Fallout Repair — Design

Date: 2026-08-29 · Bet: BET-Y1Q3-T10-64 · Risk: L1 · Appetite: 0.5 day

## Problem

Three fallout classes from the 2026-08-29 unattended automation activity:

1. **omo import breakage (red-line toolchain down).** The local omo child
   branch carries committed god-module extractions that do not import:
   `workflow/diagnostics_p74.py` used a sibling-relative import for
   package-root `omo_shared` and referenced `datetime`/`UTC` without
   importing them (broke `bin/agent-workflow.py` since 09:35); `omo_audit.py`
   ↔ `omo_audit_checks.py` form a top-level import cycle (checks-first import
   fails).
2. **Resident decision-inbox noise.** `resident/decision.py` writes a draft
   for every `WorkflowFailed`/`StepFailed`/`StepTimeout` event; events without
   trace/event provenance produce unactionable "?" placeholder drafts and
   retries append near-identical files. Root cause of the 100+ accumulated
   drafts: `tests/unit/test_resident_decision.py` isolates `PROPOSAL_DIR` but
   not `INBOX_DIR`, so every pytest run of that file leaked its five fixture
   drafts (trace-abc / evt-fallback / event / trace-StepFailed /
   trace-StepTimeout — exact filename match) into the real inbox during
   unattended test cycles.
3. **chore(state) commit-reset churn on local main.** Automation commits
   state-sync snapshots directly on local main; branch protection rejects the
   push; a later step resets main to origin/main; the cycle repeats and
   orphans the commits (designed path is worktree+PR, e.g. #2519).

## Design

### 1. Import repairs (fix-forward, no behavior change)

- `diagnostics_p74.py`: parent-relative `from ..omo_shared import load_yaml`,
  add `from datetime import UTC, datetime`, drop unused `Path` import.
- `omo_audit.py`: move the `governance_check_*` import into
  `run_governance_audit` (function-level) and re-export via PEP 562
  `__getattr__` so both import orders and the `__all__` API keep working.
- Both repairs were applied to the diverged local child branch as commits
  `34b0eaa7` / `cb9c8f59` during triage (documented, not pushed).

### 2. Resident decision guard

In `resident/decision.py::_decide`:

- Drop trigger events with no `trace_id` and no `event_id`: without
  provenance the draft is unreadable and the raw event remains in the event
  stream.
- At most one draft per `(event_type, trace_id)` per UTC day: skip when a
  `decision-<today>-*-{slug}.json` already exists in the JSON proposal dir.
- Tests: fix the leaky fixture (isolate `INBOX_DIR` alongside
  `PROPOSAL_DIR`), flip the empty-trace contract test to expect the drop,
  and add a same-day dedupe test.

### 3. commit-msg guard against chore(state)-on-main

New `.githooks/commit-msg`: when the current branch is `main` and the message
starts with `chore(state)`, reject with guidance to use the worktree+PR path
(`gac-worktree.sh`), unless `SWARM_ESCAPE_ID` is set (D4 escape hatch).
Installed via the existing `make install-hooks` copy step. Source of truth
stays the tracked `.githooks/` file.

### 4. Disposition of accumulated noise

Delete the accumulated empty-template `decision-…-event.md` /
`-evt-fallback.md` / `-trace-*.md` drafts (placeholder content, empty
trace_id) from `.omo/_knowledge/decision-proposals/`; count before/after in
the closeout report.

## Non-goals

- No rebase/push of the diverged local omo child branch while the unattended
  extraction session is active (follow-up, resume trigger recorded in retro).
- No change to T1-12 evidence, T4-02 scope, or any launchd/host runtime.

## Rollback

Revert the single commit per surface: hook file, decision.py + tests, ledger
entry. All changes are additive guards; no schema or data migration.
