---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-86
---

# Documents Weijian control runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/卫健委/_control` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-weijian-control-20260830`.
- L4 command: `audit_content_plane(source, max_attempts=1)`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-86 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T20:34:42Z`.

## Preflight

- Scoped L4 audit: `stability_attempts=1`, `content=44`, `projection=4`,
  `contract=2`, `runtime=5`; the five selected artifacts were regular files.
  No symlink, content, projection, or contract artifact was selected.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

`lib/documents_runtime_quarantine.py --apply` moved exactly five regular files
(`controller.py`, `predictor.py`, `tools/dedup_pdfs.sh`,
`tools/dedup_pdfs_symlink.sh`, and `tools/ocr_index.py`) to the Workspace
quarantine. It preserved file bytes and modes in a rollback manifest and did
not touch any path outside the selected runtime entries.

- Files: `5`.
- Bytes: `30737`.
- Source and target fingerprint:
  `sha256:9c81d4980702c9ebfae1e1bb77064c94242274dff0b1efeec6d8285fe4bd7423`.
- Manifest SHA-256:
  `sha256:fc87ea443ec0fd9c0ce1416cfd8849144c2c2be8ef2e471a4354a9b4394a6a41`.
- Permanent deletion: `false`.

## Independent postflight

- The selected source paths are absent. The source L4 audit is stable with
  `content=44`, `projection=4`, `contract=2`, and `runtime=0`.
- Independent manifest verification found all five targets to be regular
  non-symlink files with matching hashes and modes.
- Health control content remains present, including `README.md`, `STATUS.md`,
  `STATE.md`, `PROJECT_DASHBOARD.md`, `control-rules.md`, and
  `executor-rules.md`.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

Only this Weijian control-runtime subset is complete. The family-level
`work-runtime` status remains `pending`; the registry appends this subset to
progress evidence and leaves the remaining `_scripts` and cleanup globs open.
