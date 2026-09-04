---
schema_version: specification/v1
spec_version: 1.0.0
title: Workspace quarantine retention guard
bet_id: BET-Y1Q3-T10-68
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Workspace quarantine retention guard

## Intent

Protect recoverable physical-migration packages under
`runtime/quarantine/` from ordinary repository cleanup. A quarantine package
is runtime evidence, not disposable build output; losing it after a successful
postflight invalidates rollback and terminal migration claims.

## Contract

- The repository ignores every child directory under `runtime/quarantine/`.
- The rule does not ignore source Documents paths and does not authorize
  permanent deletion.
- A regression test checks the canonical `git check-ignore` behavior for a
  manifest path.
- Existing quarantine contents are not recreated or changed by this slice.
