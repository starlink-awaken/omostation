---
schema_version: specification/v1
spec_version: 1.0.0
title: Script Convergence Gates
bet_id: BET-CONV-01
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L2
human_gate: false
---

# BET-CONV-01: Script Convergence Gates

## Scope
Establish four hard gates for bin/ script convergence:
1. SFOP_SLOT/DAO_LAYER declaration check
2. Script lifecycle registry check
3. BOS URI bidirectional binding check
4. State management spec + StateManager

## Acceptance Criteria
- All four checks implemented and CI green
- Standards documents created
- gac-validate integrates new checks

## Non-Goals
- No script merging (rules only)
- No historical cleanup (rules only)
- No CI pipeline restructuring

## Dependencies
None
