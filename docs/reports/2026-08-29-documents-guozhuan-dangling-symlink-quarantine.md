---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-79
---

# Documents Guozhuan dangling-symlink quarantine — implementation evidence

## Preflight

- Source: `~/Documents/@工作文档/国转中心/_runtime`.
- L4 audit: `stability_attempts=1`, `content=5`, `runtime=12`,
  `contract=4`; all 12 selected runtime objects were dangling symlinks and
  zero selected objects were regular files.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`,
  `active=191`, `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly the 12 symlink
objects to `~/Workspace/runtime/quarantine/documents-guozhuan-symlinks-20260830`.
It did not follow or restore any missing public-runtime target. The transaction
recorded `bytes=0`, each literal `link_target`, and link mode.

- Source and target fingerprint:
  `sha256:5ffd9cc38b1b6f04a350621bea1fba3e28c63fd5de76c606647bafafd92eb4a4`.
- Manifest SHA-256:
  `sha256:ae02a0ea6659d4548a7b4b625ebc932d2225c36be4864de4e5c7b7ffed0bc5cb`.
- Permanent deletion: `false`.

## Independent postflight

- Source L4 audit: `stability_attempts=1`, `runtime=0`, `content=5`,
  `contract=4`.
- Independent manifest check verified all 12 source paths are absent, all 12
  target paths are symlinks with matching literal targets and `lstat` modes,
  and the manifest remains readable.
- The five content artifacts and four contract artifacts remain in Documents.
- Consumer audit remains `status=ok` with zero forbidden and unmatched
  consumers.

## Family boundary

Only this Guozhuan symlink subset is complete. The family-level
`work-runtime` status remains `pending`; the registry appends this subset to
progress evidence and leaves all other work-runtime globs open.
