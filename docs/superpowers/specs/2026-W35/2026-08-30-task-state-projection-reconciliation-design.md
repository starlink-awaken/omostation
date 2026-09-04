---
schema_version: specification/v1
spec_version: 1.0.0
title: Task state projection reconciliation after planned-task reappearance
bet_id: BET-Y1Q3-T10-90
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Task state projection reconciliation

## Intent

Restore alignment between the tracked OMO task directories and the derived
Workspace task-state projection after a planned task reappeared on main.

## Contract

- Treat `.omo/tasks/{active,planned,blocked,archived/done}` as the task-count
  source of truth.
- Use the registered `omo state sync-tasks` broker, first in dry-run mode, to
  refresh `system.yaml` and the task registry index.
- Do not edit task content, the strategy ledger semantics, Documents, runtime
  payloads, client state, or submodule pointers.
- Re-run `current-state-coherence` and document the broker receipt after the
  projection is refreshed.

## Acceptance

1. Dry-run reports the projection delta from the task directories.
2. The broker writes only its registered task projection surfaces.
3. State/goals/tasks coherence passes on the resulting tree.
