---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-82
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents Guizi tools runtime quarantine

## Decision

Move only the three regular runtime files under
`~/Documents/@工作文档/规自委/tools` into a protected Workspace quarantine.
Retain their bytes and metadata in a rollback manifest, and do not change any
Documents content or reconstruct another runtime owner.

## Exact scope

- Source: `~/Documents/@工作文档/规自委/tools`.
- Selection: one stable L4 audit, exactly three `runtime` regular files and no
  symlinks or non-runtime artifacts.
- Target: `~/Workspace/runtime/quarantine/documents-guizi-tools-20260830`.
- The three files are the generic `controller.py`, `extract.py`, and
  `predictor.py` implementations; their byte hashes must remain unchanged.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. Preflight proves exactly three regular runtime files and no selected symlink.
2. The target is absent/empty and retention-protected.
3. The transaction records source hashes/modes and writes a hash-valid
   rollback manifest, restoring on any verification failure.
4. Postflight proves source absence, target hash/mode parity, manifest
   retention, and adjacent Documents content preservation.
5. The family remains `work-runtime: pending`; only this subset is appended to
   progress evidence.

## Non-goals

No movement outside this source directory, no regular runtime owner cutover,
no content/contract/cache/schedule/client/public-runtime change, and no
family-level retirement.
