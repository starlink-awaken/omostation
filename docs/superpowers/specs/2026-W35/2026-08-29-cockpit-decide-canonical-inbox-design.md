---
schema_version: specification/v1
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-66
spec_version: 1.0.0
title: Cockpit decide canonical inbox convergence
type: ssot
last_updated: 2026-09-03
---

# T10-64: Cockpit decide canonical inbox convergence

## Context

`projects/cockpit/src/cockpit/commands/decide.py` is an old top-level
`cockpit decide` entry that directly creates and writes
`.omo/state/decision-inbox.json`. The active `cockpit scenario inbox` entry
already delegates decision-inbox persistence to the canonical
`bin/ssot/scene-card-decision-inbox.py` engine under `.omo/_inbox`. The two
paths are therefore competing storage/control surfaces, and the direct write
is correctly rejected by the `direct-omo-io` gate.

## Decision

Keep `cockpit decide` as a compatibility entry, but make it a thin adapter over
the existing canonical scenario-inbox engine. Preserve the five user actions
(`list`, `add`, `approve`, `reject`, `status`) and human-readable output while
mapping them to canonical scene/intent operations. `add` may create or reuse a
deterministic default scene and journey when none exists; approvals and
rejections update canonical intent status. No second JSON store is retained.

Add focused tests for the adapter and retain the existing direct-write
negative coverage. The canonical engine remains the sole persistence owner.

Add focused tests for the adapter and retain the existing direct-write
negative coverage. The canonical engine remains the sole persistence owner.

## Non-goals

- No new storage, broker, dispatcher, schema, capability, or authority plane.
- No change to the canonical scene-card engine's data model or write semantics.
- No Documents content, host schedule, runtime state, or submodule change
  outside `projects/cockpit`.
- No removal of the public `cockpit decide` command in this slice.

## Acceptance

1. `cockpit decide` contains no direct filesystem mutation of `.omo` or
   `spaces`.
2. The compatibility actions call the canonical scenario-inbox engine and
   preserve useful list/add/status/approve/reject behavior.
3. Cockpit focused tests and the root `direct-omo-io`/interface gate pass.
4. No legacy `decision-inbox.json` writer remains.

## Rollback

Restore the previous `decide.py` implementation and its child/root pointer.
No runtime or host rollback is needed.
