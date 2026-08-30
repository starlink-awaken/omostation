---
schema_version: specification/v1
spec_version: 1.0.0
title: Wave 1 Debt Repayment
bet_id: BET-CONV-02
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L2
human_gate: false
---

# BET-CONV-02: Wave 1 Debt Repayment

## Scope
Merge duplicate health/scorecard and governance scripts, unify state management.

## Acceptance Criteria
- health/scorecard scripts reduced from 22 to <=5
- governance scripts reduced from 32 to <=10
- .omo/state/ files reduced from 21 to <=8
- All CI green

## Non-Goals
- No scene-* script merging (Wave 2)
- No check-* script merging (Wave 3)
- No submodule code changes

## Dependencies
- BET-CONV-01
