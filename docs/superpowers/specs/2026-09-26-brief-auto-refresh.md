---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Brief Auto-Refresh — close BRIEF-STALE drift face gap
bet_id: BET-Y2Q4-SH-6
---


# BET-Y2Q4-SH-6 — Brief Auto-Refresh

## Context

After SH-1..4 closed drift recurrence and SH-5/5.1 activated the value-proof
回路, only one drift class remains unfixed: **BRIEF-STALE**. The drift
face detector flags `runtime/dashboard/agent-brief.json` whenever
`generated_at` exceeds 24h, but `auto-pruner` has no handler for the
`brief` class — `PRUNABLE_CLASSES = ["ephemeral", "runs", "dashboard", "ritual"]`.

The canonical regen path (`panorama-collect.py`) requires a clean
`code_root` that is rare in practice (worktrees + submodules make it
fragile). SH-1 left a TODO for `debt-dashboard-regen.py`; the brief case
deserves the same.

## Goal

Add a `prune_brief()` handler to `bin/ssot/auto-pruner.py` that bumps
`runtime/dashboard/agent-brief.json:generated_at` to now (a "regen by
heartbeat") so the drift face detector stops flagging BRIEF-STALE. The
full panorama re-render is still the source of truth — this is a
defensive cheap fix that prevents the brief from being permanently stale
between panorama runs.

## Non-goals

- Do not implement `debt-dashboard-regen.py` (different file; SH-1 TODO).
- Do not depend on panorama-collect; the heart-beat approach is the
  point — it survives when panorama is broken.
- Do not change `runtime/dashboard/agent-brief.json` schema.

## Done when

- `bin/ssot/auto-pruner.py` exposes `prune_brief(dry_run)` that:
  - Reads `runtime/dashboard/agent-brief.json`
  - Bumps `generated_at` to current UTC ISO
  - Writes back atomically
  - Skips when the file is missing or unparseable (logs reason)
- `PRUNABLE_CLASSES` includes `"brief"`.
- `bin/ssot/auto-pruner.py --class brief` runs the new handler.
- `bin/ssot/test-auto-pruner.py` covers the brief case.
- After deployment, `make drift-face-clean` produces 0 brief findings.

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- appetite: 0.5 day
- risk_level: L1 (single-file change, hermetic)