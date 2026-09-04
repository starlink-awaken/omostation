---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-80
---

# Documents Guizi dangling-symlink quarantine — implementation evidence

## Preflight

- Source: `~/Documents/@工作文档/规自委/_runtime`.
- Scoped L4 audit: `stability_attempts=1`, `content=1`, `runtime=11`,
  `contract=0`; all 11 selected runtime objects were dangling symlinks and
  zero selected objects were regular files.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly the 11 symlink
objects to `~/Workspace/runtime/quarantine/documents-guizi-symlinks-20260830`.
It did not follow or restore any missing public-runtime target. The transaction
recorded `bytes=0`, each literal `link_target`, and link mode.

- Source and target fingerprint:
  `sha256:16c51b28b55af10f8608e31dbc043978d4275146be6cf596c5876cc8fbe26e0a`.
- Manifest SHA-256:
  `sha256:7bacbae4998f693511b295a13edddd385939ec021caa7b67c7787d7c0e01f17b`.
- Permanent deletion: `false`.

## Independent postflight

- Source L4 audit: `stability_attempts=1`, `runtime=0`, `content=1`,
  `contract=0`.
- Independent manifest check verified all 11 source paths are absent, all 11
  target paths are symlinks with matching literal targets and `lstat` modes,
  and the manifest remains readable.
- The README content artifact remains in Documents.
- Fresh consumer audit remains `status=ok` with zero forbidden and unmatched
  consumers.

## Family boundary

Only this Guizi symlink subset is complete. The family-level `work-runtime`
status remains `pending`; the registry appends this subset to progress evidence
and leaves all other work-runtime globs open.
