---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-76
---

# System task projection reconciliation — implementation evidence

> **2026-08-30 spec correction note**: The original spec direction
> ("planned 7→6, total 299→298") was the inverse of filesystem truth.
> The spec was amended this run to describe the actual broker delta
> ("planned rises from 6 to 7, total rises from 298 to 299"). This
> report was refreshed in the same commit so that the evidence,
> spec, and ledger agree.

## Scope

The stale task counters in `.omo/state/system.yaml` were rebuilt through the
canonical OMO `state sync-tasks` broker. No task YAML/YML source file, goal,
Documents content, runtime payload, schedule, or user configuration was
changed.

## Evidence

- Dry-run: `completed 290→290`, `planned 6→7`, `active 1→1`,
  `blocked 1→1`, `total 298→299`.
- Live broker: `uv run --project projects/omo omo state sync-tasks` exited `0`
  and produced exactly that delta.
- Aggregate hash of task YAML/YML sources remained
  `a6eb794fce3e3853c9beb6bed89a8683b6014bbe0c7426d941bfbad5ac6ab6b4` before
  and after.
- `system.yaml` changed from
  `3d16031d675bcc18600d17d6b23d3f35dcec4df29088b7350077886e0cc50ba8` to
  `68182869232492c9eef961706bd370bb0068873f6f2b88b8be906dfc0580b318`.
- The broker regenerated the derived `.omo/tasks/registry/INDEX.md` to remove
  the stale event-loop-dead-loop planned row and update its counts.
- `current-state-coherence.py` exited `0` with `planned=7`, `total=299`.
- `ssot-guardian.py` exited `0`.

## Boundary

The OMO state broker is the only writer used. Documents and runtime payloads
were not touched; this repair only restores projection truth from the existing
task source files.
