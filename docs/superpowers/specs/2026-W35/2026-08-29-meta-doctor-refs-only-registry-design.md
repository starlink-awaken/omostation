---
schema_version: specification/v1
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-61
spec_version: 1.0.0
title: Registry-driven meta-doctor refs-only CI binding
type: ssot
last_updated: 2026-09-03
---

# T10-61: Registry-driven meta-doctor refs-only binding

## Context

`governance-check.yml` runs `bin/gac/meta-doctor.py --refs-only` for the CI
checkout. The CI-surface registry also describes this surface as the M2
reference-activity check, but its entry omits the argument. The generic
`ci-check-runner.py` already consumes an optional surface-level `args` list.
As a result, the registry-driven runner invokes the default M1+M2 mode and
fails on stale checkout projections even though the intended CI contract is
reference-only.

## Decision

Add `args: [--refs-only]` to the canonical
`bin-gac-meta-doctor-py` entry in
`.omo/_truth/registry/ci-surfaces.yaml`. Add a regression test that loads the
registry and verifies the selected command includes the exact argument.

The runner implementation remains unchanged: the registry is already the
single execution source, and the argument plumbing is already generic.

## Non-goals

- No change to meta-doctor rules, exit semantics, M1 heartbeat logic, or M2
  reference scanning.
- No change to the GitHub workflow, scheduler, runtime state, or host files.
- No new registry, dispatcher, cache, or parallel governance path.
- No Documents content, migration-family, or capability ownership change.

## Acceptance

1. The registry entry remains active, gated, and bound to
   `governance-check.yml`.
2. The runner contract test proves the selected meta-doctor command contains
   `--refs-only`.
3. `ci-check-runner.py --workflow governance-check.yml --json` exits zero in
   the current checkout.
4. The focused CI-surface tests and the local governance gate pass.

## Rollback

Remove the single `args` field from the same registry entry. No runtime or
host mutation is involved.
