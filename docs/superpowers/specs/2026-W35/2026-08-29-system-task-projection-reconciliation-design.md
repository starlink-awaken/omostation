---
schema_version: specification/v1
spec_version: 1.1.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-76
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# System task projection reconciliation

## Decision

Rebuild the high-churn task counters in `.omo/state/system.yaml` through the
canonical OMO `state sync-tasks` broker. The task files under `.omo/tasks/` are
the source of truth; this slice does not add, delete, rename, or reclassify a
task.

## Scope

- Correct only the stale projection counters: bring `planned` and `total`
  in line with the task filesystem truth (`planned` rises from `6` to `7`,
  `total` rises from `298` to `299` while other counters stay unchanged).
- Preserve completed, active, and blocked counts.
- Record before/after hashes and current-state-coherence evidence under
  Workspace evidence.
- Do not mutate Documents, runtime payloads, task files, goals, or unrelated
  projections.

## Acceptance criteria

1. The broker dry-run reports the exact expected counter delta.
2. The live broker sync writes the projection and leaves task-file counts
   unchanged.
3. `current-state-coherence.py` and `ssot-guardian.py` pass after the sync.
4. The change is recorded with a root-resolvable report and five-question
   retro.

## Rollback

Restore the broker-captured `system.yaml` backup only through the OMO state
broker after verifying its hash. No direct file edit or task-file rollback is
allowed.
