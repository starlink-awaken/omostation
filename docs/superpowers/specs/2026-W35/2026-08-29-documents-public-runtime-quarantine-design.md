---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents public runtime physical quarantine
bet_id: BET-Y1Q3-T10-69
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Documents public runtime physical quarantine (T10-69)

## Intent

Complete the next physical-purification slice without treating historical
content references as active executors. The source is
`/Users/xiamingxing/Documents/@公共/_runtime`, including its `kems-v2`
subtree. Only files classified by the existing L4 content-plane auditor as
`runtime` may move.

## Transaction contract

- Preflight uses a stable scoped L4 audit and a fresh consumer receipt.
- The selected source set is immutable for the transaction: path, mode, size,
  and SHA-256 are recorded before movement.
- Each selected file is moved, not copied-and-deleted, into
  `Workspace/runtime/quarantine/documents-public-runtime-20260829/`, retaining
  its relative path and metadata.
- A manifest is written only after every target is hash-verified and every
  source is absent. Any failure restores already moved files.
- Markdown/content, contracts, projections, bridges, and non-selected runtime
  files are untouched. The quarantine is recoverable and permanent deletion is
  disabled.

## Acceptance

- The public runtime inventory is exactly the preflight inventory.
- Consumer evidence has zero forbidden executors and zero unmatched active
  consumers; content references remain classified as references.
- Postflight source absence, target equality, non-target stability, and replay
  rollback are all recorded.
- The registry uses a repository-resolvable evidence receipt for terminal
  status, while the physical manifest path remains recorded in the report.
