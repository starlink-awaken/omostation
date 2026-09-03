---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-84
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents root control tools runtime quarantine

## Decision

Move only the four regular runtime files under
`~/Documents/@工作文档/_control/tools` into a protected Workspace quarantine.
Retain their bytes and metadata in a rollback manifest, and do not change any
Documents control or content artifacts.

## Exact scope

- Source: `~/Documents/@工作文档/_control/tools`.
- Selection: one stable L4 audit, exactly four `runtime` regular files and no
  symlinks or non-runtime artifacts.
- Target: `~/Workspace/runtime/quarantine/documents-root-control-tools-20260830`.
- The selected files are `kems_extract.py`, `kems_fusion.py`, `ocr_batch.py`,
  and `ocr_generic.py`; their bytes and modes must remain unchanged.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. Preflight proves exactly four regular runtime files and no selected symlink.
2. The target is absent/empty and retention-protected.
3. The transaction records source hashes/modes and writes a hash-valid
   rollback manifest, restoring on any verification failure.
4. Postflight proves source absence, target hash/mode parity, manifest
   retention, and adjacent control/content preservation.
5. The family remains `work-runtime: pending`; only this subset is appended to
   progress evidence.

## Non-goals

No movement outside this source directory, no runtime owner cutover, no
content/contract/cache/schedule/client/public-runtime change, and no
family-level retirement.
