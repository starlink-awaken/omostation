---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-77
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents work-runtime regular quarantine

## Decision

Move only the stable L4 `runtime` regular-file inventory under
`@工作文档/卫健委/_runtime` into a retention-protected Workspace quarantine.
The transaction must use `lib/documents_runtime_quarantine.py`, preserve hash,
size, mode, and rollback metadata, and never follow or reconstruct symlinks.

## Exact scope

- Source: `~/Documents/@工作文档/卫健委/_runtime`.
- Selection: one stable L4 audit, exactly the 17 regular files classified as
  `runtime`.
- Target: `~/Workspace/runtime/quarantine/documents-weijian-runtime-20260830`.
- Keep all content, contract, projection, cache, invalid-archive, directory,
  and symlink artifacts in Documents.
- The consumer audit must be fresh and report `status=ok`,
  `forbidden_executors=0`, and `unmatched=0` before moving anything.

## Acceptance criteria

1. Preflight proves the exact 17-file inventory is stable and regular-only.
2. The protected target is absent or empty and the quarantine package is
   ignored by ordinary cleanup.
3. The transaction moves exactly the selected files and writes a hash-valid
   manifest; on any verification error it restores the source set.
4. Postflight proves all selected sources are absent, all targets match, and
   non-runtime Documents artifacts remain present.
5. The migration registry records `work-runtime` as retired only after the
   manifest and consumer evidence are independently rechecked.

## Non-goals and rollback

No permanent deletion, schedule change, client configuration change, target
restoration, public-runtime repair, or other migration-family status change is
allowed. Rollback is a manifest-driven move back to the recorded source paths
after target hash and source absence checks.
