---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: A9 strategy retro full-scan repair
bet_id: BET-Y2Q2-T10-154
created: '2026-09-22'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# A9 strategy retro full-scan repair

## Problem

The A9 cockpit gate reports `strategy=PARTIAL` because the strategy collector
discovers 502 retros but its explicit retro budget is 500. Two files are
truncated, producing `retros:sample_budget`, and the cockpit source therefore
cannot prove A9 freshness.

## Change

Raise `MAX_RETRO_FILES` from 500 to 1000 so the current corpus fits inside the
existing global file budget. Add a collector test that creates more retros than
the old limit and asserts no `retros:sample_budget`, no truncation, and state
`OBSERVED`.

## Acceptance

- The live strategy result contains zero hard gaps and zero truncated retros.
- The cockpit source states `strategy` as `OK`.
- Focused dashboard collector tests pass.
- No source status is promoted to green while a read error or real truncation
  remains.

## Non-goals

This does not remove sampling budgets, read unbounded file bytes, activate
Claims Authority, change A9 semantics, or treat partial evidence as PASS.

## Rollback

Restore `MAX_RETRO_FILES = 500`. The collector continues to fail closed with
the exact truncation reason.
