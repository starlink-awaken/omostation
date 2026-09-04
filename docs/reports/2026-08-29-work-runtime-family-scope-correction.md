---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-78
---

# Work-runtime family scope correction — implementation evidence

## Finding

The prior T10-77 transaction completed one physical subset:
`@工作文档/卫健委/_runtime` regular runtime files. The migration registry's
`work-runtime` family is broader and also covers `_control`, `tools`, `_scripts`,
other domain `_runtime`, and the Weijian `cleanup-commit.sh` path. A family-wide
`retired` status would therefore overclaim completion.

## Correction

- `work-runtime` is restored to family-level `status: pending`.
- The completed subset remains recorded under `progress_evidence` with its
  source/target fingerprints, 17-file count, byte count, manifest hash, and
  rollback reference.
- All remaining family globs are listed explicitly under
  `progress_evidence.remaining_globs`.
- The prior T10-77 report and retro now state the same family/subset boundary.

## Verification

- The 17-file Workspace quarantine manifest remains present with
  `status=completed`, matching source/target fingerprint, and independent
  hash verification.
- `documents-content-plane-migration-check.py --json` passes and keeps
  `work-runtime` in its non-terminal family set.
- `doc-ssot-lint.py --json` passes with zero findings.
- No Documents or Workspace payload was moved, restored, deleted, or rewritten
  by this correction.
