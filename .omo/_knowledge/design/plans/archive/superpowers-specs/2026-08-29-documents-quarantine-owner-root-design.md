---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents quarantine owner root anchor
bet_id: BET-Y1Q3-T10-71
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
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
