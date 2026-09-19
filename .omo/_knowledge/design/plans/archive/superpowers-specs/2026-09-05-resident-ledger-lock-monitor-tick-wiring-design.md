---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T9-02
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# Resident ledger lock-monitor tick 接线（BET-Y1Q4-T9-02）

## Goal

Wire T9-01 `ledger_check.check_and_recover` into the resident
daemon/heartbeat tick path so lock monitoring runs without manually
calling `omo resident status`.

## Non-goals

- Do not change lock thresholds or zombie kill policy
- Do not replace SQLite
- Do not add a new bin script / cron surface if existing tick paths suffice

## Done when

1. Resident daemon and/or heartbeat tick path calls
   `ledger_check.check_and_recover` explicitly (cold-start non-fatal)
2. `make resident-status` still reports `health=recovered` or `health=ok`

## Verify

```bash
make resident-status
```

Expect: `health=recovered` or `health=ok`.

## Design

- Prefer an explicit call at the start of `daemon.tick_once` and/or
  `heartbeat.publish_heartbeat`, so recover runs even when status is not
  the entry point.
- Missing ledger / probe errors remain non-fatal (best-effort log/skip).
- Thresholds and kill policy stay owned by T9-01 `ledger_check.py`.
