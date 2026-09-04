---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-78
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Work-runtime family scope correction

## Decision

Migration-family status is family-wide, not per-directory. Because the
`work-runtime` registry family covers multiple Documents surfaces, the verified
quarantine of `@工作文档/卫健委/_runtime` is partial progress and must not set
the whole family to `retired`.

Restore `work-runtime` to `pending` and attach explicit progress evidence for
the completed 17-file Weijian regular-runtime subset. Preserve the quarantine
manifest and keep all remaining family globs pending for later bounded work.

## Scope

- Change only the migration registry and its evidence/report/retro/ledger.
- Record the completed source root, fingerprints, manifest, and file/byte count
  as partial evidence.
- Do not move, restore, delete, or rewrite any host or Documents file.

## Acceptance criteria

1. `work-runtime` status is `pending`, not a terminal status.
2. The completed Weijian regular-runtime subset is recorded with its exact
   manifest and fingerprints.
3. The remaining work-runtime globs are explicitly named and remain open.
4. Migration coverage and document SSOT checks pass with no family-level
   overclaim.
