---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-86
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents Weijian control runtime quarantine

## Decision

Move only the five regular runtime files under
`~/Documents/@工作文档/卫健委/_control` into a protected Workspace quarantine.
Retain their bytes and metadata in a rollback manifest, and do not change the
health control content, projection, contract, or symlink surfaces.

## Exact scope

- Source: `~/Documents/@工作文档/卫健委/_control`.
- Selection: one stable L4 audit, exactly five `runtime` regular files; no
  symlink, content, projection, or contract artifact is selected.
- Target: `~/Workspace/runtime/quarantine/documents-weijian-control-20260830`.
- The selected files are `controller.py`, `predictor.py`,
  `tools/dedup_pdfs.sh`, `tools/dedup_pdfs_symlink.sh`, and
  `tools/ocr_index.py`; their bytes and modes must remain unchanged.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. Preflight proves exactly five regular runtime files and no selected symlink.
2. The target is absent/empty and retention-protected.
3. The transaction records source hashes/modes and writes a hash-valid
   rollback manifest, restoring on any verification failure.
4. Postflight proves source runtime absence, target hash/mode parity, manifest
   retention, and adjacent health-control preservation.
5. The family remains `work-runtime: pending`; only this subset is appended to
   progress evidence.

## Non-goals

No movement outside this source directory, no symlink/content/projection/
contract/cache/schedule/client/public-runtime change, no runtime owner cutover,
and no family-level retirement.
