---
schema_version: specification/v1
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-64
spec_version: 1.0.0
title: Cockpit decide write-boundary recovery
---

# T10-64: Cockpit decide write-boundary recovery

## Context

`projects/cockpit/src/cockpit/commands/decide.py` is an old top-level
`cockpit decide` entry that writes `.omo/state/decision-inbox.json`. The root
gitlink still points to child revision `37bf989`, where the write uses direct
`Path.mkdir` and `Path.write_text`, so the `direct-omo-io` gate rejects it.
Child `origin/main` already contains the reviewed fix `2d44b650`, which routes
the same compatibility write through OMO's sanctioned atomic helpers.

## Decision

Keep `cockpit decide` and its five existing actions (`list`, `add`, `approve`,
`reject`, `status`) for compatibility, and promote child `2d44b650` through
the root gitlink. That child change uses `ensure_parent_dir` and
`write_text_atomic` from the existing OMO I/O boundary, preserving the
legacy JSON shape and CLI behavior while clearing the direct filesystem gate.

The legacy JSON store is not migrated to the scenario-inbox data model in this
bounded slice. A future data-model convergence must be a separate accepted
BET because it changes persistence semantics and user-visible identifiers.

Add focused tests for the adapter and retain the existing direct-write
negative coverage. The canonical engine remains the sole persistence owner.

## Non-goals

- No new storage, broker, dispatcher, schema, capability, or authority plane.
- No change to task/decision JSON shape, public action names, or user-visible
  output semantics.
- No scenario-inbox data-model migration in this slice.
- No Documents content, host schedule, runtime state, or unrelated submodule
  change.

## Acceptance

1. The root `projects/cockpit` gitlink points to a child-main revision that
   contains the `2d44b650` atomic-helper fix.
2. The root direct-omo-io gate reports no violation in `cockpit decide`.
3. Cockpit focused tests and the root interface gate pass.
4. The legacy JSON writer uses only the sanctioned OMO atomic helpers; no
   direct `Path.mkdir`/`Path.write_text` remains in that module.

## Rollback

Restore the previous `decide.py` implementation and its child/root pointer.
No runtime or host rollback is needed.
