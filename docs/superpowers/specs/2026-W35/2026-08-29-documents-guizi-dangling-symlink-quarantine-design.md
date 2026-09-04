---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-80
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents Guizi dangling-symlink quarantine

## Decision

Move only the 11 dangling symlink objects under
`~/Documents/@工作文档/规自委/_runtime` into a protected Workspace quarantine.
Preserve each link's literal target and metadata without following the link;
do not reconstruct the missing public-runtime targets.

## Exact scope

- Source: `~/Documents/@工作文档/规自委/_runtime`.
- Selection: one stable L4 audit, exactly 11 `runtime` symlinks, all dangling.
- Target: `~/Workspace/runtime/quarantine/documents-guizi-symlinks-20260830`.
- Keep the source content artifacts and every other source path unchanged.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. Preflight proves exactly 11 dangling symlinks and no selected regular file.
2. The target is absent/empty and retention-protected.
3. The no-follow transaction preserves link targets, modes, and hashes in a
   rollback manifest and restores on any verification failure.
4. Postflight proves source-link absence, target-link identity, manifest
   retention, and source content preservation.
5. The family remains `work-runtime: pending`; only this subset is appended to
   progress evidence.

## Non-goals

No public-runtime recovery, target restoration, regular runtime move, content
mutation, schedule/client change, permanent deletion, or family-level
retirement is allowed.
