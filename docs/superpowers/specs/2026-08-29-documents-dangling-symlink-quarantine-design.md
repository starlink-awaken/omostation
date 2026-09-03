---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents dangling symlink quarantine
bet_id: BET-Y1Q3-T10-73
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Documents dangling symlink quarantine

## Intent

Remove dangling execution-plane symlinks left in the Weijian Documents domain
after public-runtime source retirement, without following or recreating their
missing targets.

## Transaction contract

- Select only the preflight inventory's symlink entries whose link targets are
  absent; regular files are a separate wave.
- Record each link target, mode, relative path, and a digest of the link target
  string; never read through a symlink.
- Move symlink objects with no-follow semantics into a retention-protected
  Workspace quarantine and write a rollback manifest only after postflight
  verifies link identity and source absence.
- On any collision, mutation, or manifest failure, restore moved symlinks in
  reverse order. No target bytes are reconstructed.

## Acceptance

- All selected dangling symlinks are absent from the Documents source root and
  present as identical symlink objects in quarantine.
- Regular runtime files, content, contracts, projections, `_storage`, and
  other domains remain untouched.
- The work-runtime family remains non-terminal until its regular runtime set
  is separately processed.
