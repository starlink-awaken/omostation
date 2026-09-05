---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T9-01
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# Resident ledger 锁监控与自动恢复（BET-Y1Q4-T9-01）

## Goal

Monitor SQLite event-ledger lock age; on lock held >5 minutes run WAL
checkpoint; after 3 consecutive checkpoint failures, kill a confirmed zombie
holder (CPU &lt;1% over 5min). Expose lock age on `omo resident status`.

## Non-goals

- Do not replace SQLite
- Do not change ledger schema

## Done when

1. `projects/omo/src/omo/resident/ledger_check.py` implements lock-age probe,
   timed checkpoint, and zombie kill (circuit_breaker gated)
2. `resident status` includes `components.ledger.lock_age_seconds`
3. Missing ledger / cold daemon are non-fatal for status health
4. `make resident-status` reports `health=recovered` or `health=ok`

## Verify

```bash
make resident-status
```
