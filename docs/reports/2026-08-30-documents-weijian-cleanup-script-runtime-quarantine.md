---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-88
---

# Documents Weijian cleanup script runtime quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/卫健委/cleanup-commit.sh` only.
- Target scope: `~/Workspace/runtime/quarantine/documents-weijian-cleanup-20260830`.
- Owner change: `lib/documents_runtime_quarantine.py` now supports one
  regular-file source while retaining directory and no-follow symlink behavior.
- Test command: `uv run --with pyyaml --with pytest python -m pytest
  tests/test_documents_runtime_quarantine.py -q`.
- Consumer command: `lib/documents_consumer_audit.py` with a fresh evidence
  receipt under the T10-88 run directory.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Postflight observed at: `2026-08-29T21:05:26Z`.

## RED → GREEN

- RED: the two new single-file source tests failed with the prior
  `source roots must be regular directories` guard; the existing 9 tests
  remained green.
- GREEN: the minimal owner enhancement passed all `12` tests, including
  regular-file acceptance, apply, and source-symlink rejection.

## Preflight

- Single-file L4 classification: exactly one `runtime` regular file,
  `cleanup-commit.sh`, with no directory-wide inventory.
- Consumer audit: `documents.consumer-audit.v1`, `status=ok`, `active=191`,
  `forbidden_executors=0`, `unmatched=0`.
- Target was absent and protected by `.gitignore: runtime/quarantine/*/`.

## Transaction

The updated owner moved exactly `cleanup-commit.sh` to the Workspace
quarantine. It preserved file bytes and mode in a rollback manifest and did
not inspect or move neighboring `_storage` scripts.

- Files: `1`.
- Bytes: `3916`.
- Source and target fingerprint:
  `sha256:875b55d2689e90bc6871a145e79283ead281e5461a48c149e225988ab873adb2`.
- Manifest SHA-256:
  `sha256:ea6d0aa35f03a3d608effdca00b66ac21379814e594cf664e4d08b54097b4bd1`.
- Permanent deletion: `false`.

## Independent postflight

- The source file is absent. The target directory contains only the moved file
  and `manifest.json`; independent verification found matching target hash and
  mode.
- A scoped scan across all work-runtime directories returned no remaining
  `runtime`, `cache`, or `invalid_archive` artifacts.
- Adjacent health-control and work-content surfaces remain present, including
  `@工作文档/卫健委/_control/README.md` and the `_storage` directory.
- Fresh consumer evidence remains `status=ok` with zero forbidden and
  unmatched consumers.

## Family boundary

This was the final regular runtime artifact matched by the `work-runtime`
source globs. The registry therefore marks `work-runtime` `retired` with a
family completion digest; this does not retire or complete `public-runtime`,
`root-oneoff-assets`, `documents-client-state`, or any other migration family.
