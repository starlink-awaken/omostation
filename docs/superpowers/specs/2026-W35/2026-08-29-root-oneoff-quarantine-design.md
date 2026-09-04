---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents root one-off runtime quarantine
bet_id: BET-Y1Q3-T10-59
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Documents root one-off runtime quarantine

## Intent

Remove only the eight already-identified, non-content one-off runtime/cache
objects from the Documents execution plane by moving them to a recoverable
Workspace quarantine. This is the first physical-purification slice; it does
not touch the rest of `_inbox` or any domain content.

## Exact physical targets

- `Documents/_inbox/2026-08-02-cleanup-gz-artifacts.sh`
- `Documents/_inbox/2026-08-03-kems-repair.py`
- `Documents/_inbox/2026-08-03-老化知识处理脚本.sh`
- `Documents/cron-service-db-fix.py`
- `Documents/cron-service-error-reset.py`
- `Documents/cron-service-fix.sh`
- `Documents/kos-index.sqlite`
- `Documents/index-BYqQMscj.js`

The target quarantine is
`Workspace/runtime/quarantine/documents-root-oneoff-20260829/`, with a
machine-readable manifest containing source path, target path, size, mode, and
SHA-256 for every object.

## Safety gates

- Reconfirm every source exists, is a regular file, has no open process, and
  has no active executable/config consumer immediately before the move.
- Copy with metadata preservation, compare bytes and SHA-256, then remove only
  the exact source path; never use recursive deletion.
- Verify all sources are absent, all quarantine bytes match, and the manifest
  is complete. On any mismatch, restore from the quarantine package and fail.
- Preserve all other `_inbox` content and all domain files byte-for-byte.
- Do not permanently delete the quarantine package; a later human-gated BET
  must handle permanent deletion.

## Acceptance

- Exactly eight source objects move and no other Documents object changes.
- Workspace quarantine and rollback manifest are complete and hash-verified.
- L4 family audit no longer reports these eight objects as Documents runtime or
  cache candidates; unresolved families remain unresolved.
- Consumer audit still reports no forbidden executable and all content inputs
  remain read-only references.
