---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-83
---

# Documents root tools runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/tools` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-root-tools-20260830`.
- L4 command: `audit_content_plane(source, max_attempts=1)`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-83 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T19:48:31Z`.

## Preflight

- Scoped L4 audit: `stability_attempts=1`, `content=0`, `runtime=4`,
  `contract=0`; the four selected artifacts were regular files and no
  symlink was selected.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- `controller.py`, `extract.py`, and `predictor.py` match the corresponding
  copies already quarantined from the Guozhuan and Guizi domain directories;
  `domain_controller.py` is the root-only implementation.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly the four regular
files (`controller.py`, `domain_controller.py`, `extract.py`, and
`predictor.py`) to the Workspace quarantine. It preserved file bytes and modes
in a rollback manifest and did not touch any path outside the source directory.

- Files: `4`.
- Bytes: `19848`.
- Source and target fingerprint:
  `sha256:fd72729d88ec969a9c0d1550da738abd2d1a48018e2a9dbfb93dc06107865eea`.
- Manifest SHA-256:
  `sha256:48108b0d2f59bab99c027d9c22a9b4b5b7a2eb6bc3b7474e7d975f31b37f9068`.
- Permanent deletion: `false`.

## Independent postflight

- Source `tools` directory is empty and its L4 audit is stable with no
  artifacts.
- Independent manifest verification found all four targets to be regular
  non-symlink files with matching hashes and modes; source paths are absent.
- Adjacent content remains present: `@工作文档/_control/STATUS.md` was not
  moved.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

Only this root `tools` subset is complete. The family-level `work-runtime`
status remains `pending`; the registry appends this subset to progress evidence
and leaves all other work-runtime globs open.
