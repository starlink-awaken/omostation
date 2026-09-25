---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: OMO gitlink freshness repair
bet_id: BET-Y1Q4-T10-172
created: '2026-09-20'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# OMO gitlink freshness repair

## Problem

Root main pins `projects/omo` at `022ba3001219e1c7684643e977e46c15b1af54de`,
while the OMO child main has advanced to
`d7feb927f97f9aca7871a6965e8211ba99c18437`. The freshness and auto-bump gates
correctly fail closed and require a managed owner publication.

## Change

Advance only the root `projects/omo` gitlink from the old pin to child main
`d7feb927f97f9aca7871a6965e8211ba99c18437`. Do not amend or rewrite the child
commit.

## Acceptance

- Old pin is an ancestor of the target child commit.
- Focused claims bridge and start-preflight tests pass.
- Root workflow verification, compliance, and default governance gate pass.
- Required contexts pass on the unique root PR.
- After merge, `origin/main:projects/omo` equals the target child commit.

## Rollback

Revert the root gitlink commit through a new governed PR. Never force push or
rewrite the child repository.

## Non-goals

No other gitlink changes, no child history rewrite, no runtime mutation, no
branch-protection change, and no business-value claim.
