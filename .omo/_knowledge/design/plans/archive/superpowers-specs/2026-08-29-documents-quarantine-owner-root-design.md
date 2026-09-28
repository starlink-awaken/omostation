---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
type: ssot
last-reviewed: 2026-08-29
title: Documents quarantine owner root anchor
created: 2026-08-29
last_updated: 2026-09-03
bet_id: BET-Y1Q3-T10-71
---
# Documents quarantine owner root anchor

## Intent

Keep the reusable Documents quarantine transaction bound to the Workspace root
after moving its implementation from `bin/gac` into the existing `lib` owner
layer.

## Contract

- The owner module resolves `ROOT` to the repository root from its `lib` path.
- L4 imports, repository-relative evidence, and CLI behavior work from a clean
  clone without relying on the caller's current directory.
- A regression test fails if the owner resolves one directory too high.
- No physical Documents or runtime payload is read for mutation by this BET.
