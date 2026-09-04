---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-77
---

# Documents Weijian regular work-runtime quarantine — implementation evidence

## Scope

The transaction moved only the 17 regular files classified as `runtime` by a
stable L4 audit under `~/Documents/@工作文档/卫健委/_runtime`. It did not follow
or move symlinks and did not touch content, contract, cache, invalid-archive,
projection, or schedule artifacts.

## Preflight evidence

- L4 audit: `stability_attempts=1`, `content=23`, `runtime=17`, `contract=31`,
  `symlink_count=0` in the selected runtime set.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`,
  `active=191`, `workspace_read_owners=12`, `forbidden_executors=0`,
  `unmatched=0`.
- Target was absent before the transaction and is protected by
  `.gitignore: runtime/quarantine/*/`.

## Transaction and postflight evidence

- Owner: `lib/documents_runtime_quarantine.py` with `--apply`.
- Target: `~/Workspace/runtime/quarantine/documents-weijian-runtime-20260830`.
- Moved exactly 17 files, totaling 80,317 bytes; permanent deletion was false.
- Source and target fingerprint:
  `sha256:d2c043895c524880f76c18909eb013216a0b985b81000cb912dd258032b63f29`.
- Independent manifest SHA-256:
  `sha256:46e7093e9046a7257a9eb3b2b30b0aae4e5f4aa2bbec4589c34a9ef99f38d949`.
- Independent recheck verified all 17 source paths absent, all target files
  regular/non-symlink with matching hash and mode, and manifest retained.
- Postflight L4 audit: `stability_attempts=1`, `runtime=0`, `content=23`,
  `contract=31`.
- Postflight consumer audit remained `status=ok` with zero forbidden or
  unmatched consumers.
- Remaining Documents runtime root contains only content/contract directories
  and files, including `00-OMO框架.md` and `README.md`.

## Registry decision

The 17-file Weijian regular-runtime subset is recorded as completed progress,
but the family-level `work-runtime` status remains `pending` because its
registry globs also cover other Documents `_control`, `tools`, `_scripts`, and
domain runtime surfaces. Rollback is manifest-driven and remains available
during the observation window. No other migration-family status changed.
