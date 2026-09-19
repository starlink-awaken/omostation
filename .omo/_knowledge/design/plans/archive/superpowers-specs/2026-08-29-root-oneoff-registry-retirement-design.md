---
schema_version: specification/v1
spec_version: 1.0.0
title: Root one-off migration registry retirement
bet_id: BET-Y1Q3-T10-59
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Root one-off migration registry retirement

## Intent

Reconcile the Documents migration registry with the already-verified physical
quarantine of the `root-oneoff-assets` family. This slice changes only the
family's registry status and evidence; it performs no second physical move.

## Evidence boundary

The authoritative physical receipt is
`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-oneoff-20260829/manifest.json`.
It records eight exact source paths, source/target hashes, source absence, and
`permanent_deletion: false`. The repository report mirrors the receipt hash and
postflight results.

## Constraints

- Update only `root-oneoff-assets` status and its terminal evidence fields in
  `documents-content-plane-migrations.yaml`.
- Do not change any other migration family, source glob, owner, replacement,
  or confirmation gate.
- Do not delete the quarantine package or any Documents content.
- Do not re-run a physical move; revalidate the existing manifest and source
  absence only.
- Keep content references classified as references; they are not execution
  consumers.

## Acceptance

- `root-oneoff-assets.status` is `retired` with all required evidence fields.
- The eight source paths remain absent and the quarantine manifest remains
  complete/hash-valid.
- Consumer audit remains `0 forbidden_executors` and `0 unmatched`; remaining
  migration families remain non-terminal.
- Migration registry validation passes and no other family changes.
