---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-90
---

# Task state projection reconciliation — implementation evidence

## Finding

The current main tree contained a tracked candidate task
`.omo/tasks/planned/event-loop-dead-loop.yaml`, while the derived task counters
in `.omo/state/system.yaml` were stale. The state-goals gate independently
reported the same mismatch on main and on dependent pull requests.

## Preflight

The registered OMO `sync-tasks` broker dry-run identified a planned-task and
total-task delta from the task directories. A regular `uv run --project
projects/omo` invocation was unavailable in this clean clone because its
editable `aetherforge` dependency lacked package metadata; the same broker was
therefore invoked with Python 3.13 and the declared runtime dependencies via
`uv run --no-project`, without changing the project graph.

## Transaction

The broker command was:

```text
PYTHONPATH=projects/omo/src uv run --no-project --with pyyaml --with pydantic --with httpx --with gitpython --with fastmcp --python 3.13 python -m omo.cli state sync-tasks
```

It recomputed the counters and `next_planned_tasks` from the tracked task
directories, then rebuilt the corresponding `tasks/registry/INDEX.md` view.
The broker emitted its runtime receipt under
`runtime/omo/_delivery/ingress/state/`; no task YAML content was edited.

## Postflight

`python3 bin/ssot/current-state-coherence.py --json` returned `ok=true` with
empty computed and stored divergence flags. The only tracked projection files
changed by the broker were `.omo/state/system.yaml` and
`.omo/tasks/registry/INDEX.md`; the task source directory, Documents tree,
client state, runtime payloads, and submodule pointers were not changed.

## Boundary

This is a state-projection repair, not a task-resolution or Documents
migration. The `event-loop-dead-loop` candidate remains planned until its
separate human-approved consumer repair is delivered.
