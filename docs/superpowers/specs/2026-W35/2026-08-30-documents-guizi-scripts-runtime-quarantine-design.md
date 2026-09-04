---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-87
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents Guizi scripts runtime quarantine

## Decision

Move only the five regular runtime files under
`~/Documents/@工作文档/规自委/_scripts` into a protected Workspace quarantine.
Retain their bytes and metadata in a rollback manifest, and keep the directory
README content in Documents.

## Exact scope

- Source: `~/Documents/@工作文档/规自委/_scripts`.
- Selection: one stable L4 audit, exactly five `runtime` regular files; the
  README content artifact is excluded.
- Target: `~/Workspace/runtime/quarantine/documents-guizi-scripts-20260830`.
- The selected files are `build_djps_ledger.py`, `build_huabo_db.py`,
  `build_sqlite_index.py`, `flatten_deep_dirs.py`, and `refresh_index.sh`; their
  bytes and modes must remain unchanged.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. Preflight proves exactly five regular runtime files and excludes README.
2. The target is absent/empty and retention-protected.
3. The transaction records source hashes/modes and writes a hash-valid
   rollback manifest, restoring on any verification failure.
4. Postflight proves source runtime absence, target hash/mode parity, manifest
   retention, and README/content preservation.
5. The family remains `work-runtime: pending`; only this subset is appended to
   progress evidence.

## Non-goals

No movement outside this source directory, no README/content/cache/schedule/
client/public-runtime change, no runtime owner cutover, and no family-level
retirement.
