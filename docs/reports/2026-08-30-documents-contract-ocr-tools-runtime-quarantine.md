---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-85
---

# Documents contract OCR tools runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/合同法规/_control/tools` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-contract-ocr-20260830`.
- L4 command: `audit_content_plane(source, max_attempts=1)`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-85 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T20:20:02Z`.

## Preflight

- Scoped L4 audit: `stability_attempts=1`, `content=0`, `runtime=2`,
  `contract=0`; the two selected artifacts were regular files and no symlink
  was selected.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly `ocr_index.py` and
`ocr_pdfs.py` to the Workspace quarantine. It preserved file bytes and modes
in a rollback manifest and did not touch any path outside the source directory.

- Files: `2`.
- Bytes: `8677`.
- Source and target fingerprint:
  `sha256:0a9fc292f100c2b7b62306ba10f2d3f1954926bb1acc5ea9058e3db750fc26a2`.
- Manifest SHA-256:
  `sha256:2d9bfe2f727cc8a46226757e52274e46b271eb423e44a6731372ed064a63a3e8`.
- Permanent deletion: `false`.

## Independent postflight

- Source `tools` directory is empty and its L4 audit is stable with no
  artifacts.
- Independent manifest verification found both targets to be regular
  non-symlink files with matching hashes and modes; source paths are absent.
- The parent control surface remains valid: L4 reports `content=6`,
  `projection=2`, `runtime=0`; `README.md` and `STATE.md` remain present.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

Only this contract OCR subset is complete. The family-level `work-runtime`
status remains `pending`; the registry appends this subset to progress evidence
and leaves all other work-runtime globs open.
