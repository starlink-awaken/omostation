---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-82
---

# Documents Guizi tools runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/规自委/tools` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-guizi-tools-20260830`.
- L4 command: `audit_content_plane(source, max_attempts=1)`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-82 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T19:34:25Z`.

## Preflight

- Scoped L4 audit: `stability_attempts=1`, `content=0`, `runtime=3`,
  `contract=0`; the three selected artifacts were regular files and no
  symlink was selected.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- The three files are byte-identical to the same-named copies under
  `@工作文档/国转中心/tools` and `@工作文档/tools`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly the three regular
files (`controller.py`, `extract.py`, `predictor.py`) to the Workspace
quarantine. It preserved file bytes and modes in a rollback manifest and did
not touch any path outside the source directory.

- Files: `3`.
- Bytes: `18284`.
- Source and target fingerprint:
  `sha256:2f6b66f2f17a331943a66c9e6a2a1914fd3e4973d29cd9ef88d50a586ccb36f7`.
- Manifest SHA-256:
  `sha256:868c0e69fce7fb54d2bfad620b7fad7c142b1e8a5ba7b07466671ac1bfbba834`.
- Permanent deletion: `false`.

## Independent postflight

- Source `tools` directory is empty and its L4 audit is stable with no
  artifacts.
- Independent manifest verification found all three targets to be regular
  non-symlink files with matching hashes and modes; source paths are absent.
- Adjacent content remains present: `@工作文档/规自委/_control/README.md`
  and `@工作文档/规自委/_runtime/README.md` were not moved.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

Only this Guizi `tools` subset is complete. The family-level `work-runtime`
status remains `pending`; the registry appends this subset to progress evidence
and leaves all other work-runtime globs open.
