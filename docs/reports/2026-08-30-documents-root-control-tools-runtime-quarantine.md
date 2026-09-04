---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-84
---

# Documents root control tools runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/_control/tools` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-root-control-tools-20260830`.
- L4 command: `audit_content_plane(source, max_attempts=1)`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-84 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T20:04:48Z`.

## Preflight

- Scoped L4 audit: `stability_attempts=1`, `content=0`, `runtime=4`,
  `contract=0`; the four selected artifacts were regular files and no
  symlink was selected.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly the four regular
files (`kems_extract.py`, `kems_fusion.py`, `ocr_batch.py`, and
`ocr_generic.py`) to the Workspace quarantine. It preserved file bytes and
modes in a rollback manifest and did not touch any path outside the source
directory.

- Files: `4`.
- Bytes: `22701`.
- Source and target fingerprint:
  `sha256:c6b180fc56b26bd1bdb2fefc4764d0d79f417fd8e111e00a7d003866a2b8c14f`.
- Manifest SHA-256:
  `sha256:2bf9e58ea1e4b269bd957b3656c52773af44ed02ccafe380d381c058e9a7a8fb`.
- Permanent deletion: `false`.

## Independent postflight

- Source `tools` directory is empty and its L4 audit is stable with no
  artifacts.
- Independent manifest verification found all four targets to be regular
  non-symlink files with matching hashes and modes; source paths are absent.
- The parent `_control` surface remains valid: L4 reports `content=11`,
  `projection=2`, `runtime=0`; `STATUS.md`, `STATE.md`, and `INDEX.md` remain
  present.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

Only this root control-tools subset is complete. The family-level
`work-runtime` status remains `pending`; the registry appends this subset to
progress evidence and leaves all other work-runtime globs open.
