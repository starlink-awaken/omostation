---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-68
---

# Workspace quarantine retention guard

## Incident

The public-runtime quarantine was initially observed complete: 58 files,
346217 bytes, source absence 58/58, and target hash/size/mode equality 58/58.
A later read-only recheck found both the quarantine directory and manifest
absent while the Documents source files remained absent. The loss actor is not
identified; the package path was not protected by a repository ignore rule.

## Repair

The root `.gitignore` now protects every child package under
`runtime/quarantine/`. This is a repository-retention guard only. T10-68 does
not restore, reconstruct, move, delete, or overwrite any payload, and it does
not change any Documents migration-family status or terminal evidence.

## Verification

The regression test proves that
`runtime/quarantine/documents-public-runtime-20260829/manifest.json` is
ignored by `git check-ignore`. The protected path remains a Workspace runtime
location and is intentionally absent until a separately authorized recovery
transaction creates a fresh package.
