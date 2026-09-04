---
schema_version: specification/v1
spec_version: 1.0.0
title: Convergence pulse capability projection sync
bet_id: BET-Y1Q3-T10-107
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# Convergence pulse capability projection sync

## Decision

Regenerate the existing capability projection after PR #2744 registered
`convergence-pulse-weekly` without refreshing
`docs/generated/capability-registry.yaml`. Change no native capability source,
workflow, script, dispatcher, baseline, or runtime state.

## Acceptance

- Full-profile generation adds exactly the existing workflow and changes the
  workflow total from 18 to 19.
- `gen-capability-registry.py --check --quiet`, doc SSOT, GaC, and required CI
  pass.
- The projection-only PR is merged and the blocked downstream PR can update to
  the repaired main.

## Rollback

Regenerate from the authoritative workflow registry. Never hand-edit generated
capability rows.
