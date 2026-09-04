---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents cockpit runtime physical quarantine
bet_id: BET-Y1Q3-T10-70
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Documents cockpit runtime physical quarantine

## Intent

Remove the remaining executable cockpit runtime surface from Documents while
preserving all human-readable cockpit content and projections. The source is
`/Users/xiamingxing/Documents/@驾驶舱`; only the existing L4 auditor's
`runtime` artifacts are eligible.

## Transaction contract

- Run a stable scoped L4 audit and a fresh consumer audit before movement.
- Move exactly the selected regular runtime files into the protected
  `Workspace/runtime/quarantine/` namespace, retaining relative paths, modes,
  sizes, and SHA-256 values.
- Verify source absence, target equality, and manifest durability before
  changing registry state.
- Never move Markdown/content, projections, contracts, bridges, `.bak` files,
  or any other non-runtime artifact. Permanent deletion is disabled.

## Acceptance

- The cockpit runtime family has zero remaining L4 runtime/cache/invalid
  artifacts in Documents.
- Consumer evidence has zero forbidden executors and zero unmatched consumers.
- The quarantine manifest is present under a retention-protected path and is
  referenced by a repository-resolvable report for CI.
