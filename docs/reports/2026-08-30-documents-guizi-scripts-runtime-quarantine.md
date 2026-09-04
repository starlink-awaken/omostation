---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-87
---

# Documents Guizi scripts runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/规自委/_scripts` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-guizi-scripts-20260830`.
- L4 command: `audit_content_plane(source, max_attempts=1)`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-87 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T20:49:03Z`.

## Preflight

- Scoped L4 audit: `stability_attempts=1`, `content=1`, `runtime=5`;
  `README.md` was the one content artifact and was excluded. All five selected
  artifacts were regular files; no symlink was selected.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly five regular files
(`build_djps_ledger.py`, `build_huabo_db.py`, `build_sqlite_index.py`,
`flatten_deep_dirs.py`, and `refresh_index.sh`) to Workspace quarantine. It
preserved file bytes and modes in a rollback manifest and did not touch the
README content.

- Files: `5`.
- Bytes: `30041`.
- Source and target fingerprint:
  `sha256:216880c682722355cbaa6d54f06f23079cdfb7b59b526d9eca13dc8e9a420881`.
- Manifest SHA-256:
  `sha256:7bd52420a07367d654ee0ea1afc33706d01bb1e9e7d43f762207075d0e5be15e`.
- Permanent deletion: `false`.

## Independent postflight

- Selected source paths are absent. The source L4 audit is stable with only
  `README.md` classified as content (`content=1`, `runtime=0`).
- Independent manifest verification found all five targets to be regular
  non-symlink files with matching hashes and modes.
- `README.md` remains present in Documents with `97` bytes.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

Only this Guizi scripts subset is complete. The family-level `work-runtime`
status remains `pending`; the registry appends this subset to progress evidence
and leaves the remaining cleanup script open.
