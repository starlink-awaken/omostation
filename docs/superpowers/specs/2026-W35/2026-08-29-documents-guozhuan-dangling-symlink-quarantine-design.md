---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-79
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents Guozhuan dangling-symlink quarantine

## Decision

Move only the 12 dangling symlink objects under
`~/Documents/@工作文档/国转中心/_runtime` into a protected Workspace
quarantine. Preserve each link's literal target and metadata without following
the link. The missing public-runtime targets are not reconstructed.

## Exact scope

- Source: `~/Documents/@工作文档/国转中心/_runtime`.
- Selection: one stable L4 audit, exactly 12 `runtime` symlinks, all dangling.
- Target: `~/Workspace/runtime/quarantine/documents-guozhuan-symlinks-20260830`.
- Keep the 5 content artifacts and 4 contract artifacts in the source tree.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. Preflight proves the exact 12 links are dangling and no regular file is
   selected.
2. The target is absent/empty and retention-protected.
3. The no-follow transaction preserves every link target, mode, and receipt
   hash, and rolls back on any manifest or verification failure.
4. Postflight proves source-link absence, target-link identity, manifest
   retention, and content/contract preservation.
5. The family remains `work-runtime: pending`; only this completed subset is
   appended to progress evidence.

## Non-goals

No public-runtime payload recovery, target restoration, regular runtime move,
content/contract mutation, schedule/client change, permanent deletion, or
family-level retirement is allowed.
