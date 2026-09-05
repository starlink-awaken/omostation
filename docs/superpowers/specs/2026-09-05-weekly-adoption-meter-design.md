---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T4-03
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# Weekly Adoption Falsification Meter — Design

## Problem

VISION-2029 falsification condition: **≥3 principal-accepted suggestions/week for 12 consecutive weeks by 2027-12-31**. `KR-VALUE-WEEKLY-ADOPTION` is registered (T1-14) but has no measurement path. Without a meter, the strategy has no automated red/green feedback.

## Decision

1. Add `bin/bc-os/weekly-value-report.py` with weekly snapshot:
   - `signals_count`: real external signals ingested in the week (event-ledger source)
   - `accepted_by_principal`: suggestions where principal verdict = `accept` and `binding=true`
   - `window_start`, `window_end`: ISO week boundaries
   - `status`: `red | amber | green | unmeasured` (fail-closed when data missing)
   - `falsification_risk`: projection toward 12-week threshold
2. Extend `bin/gac/value-tracker.py` with `--weekly-snapshot` to record receipts.
3. Append weekly snapshots to `docs/reports/weekly-value-snapshots.jsonl` (append-only).
4. Update `KR-VALUE-WEEKLY-ADOPTION.baseline.status` to `measured` (tooling established).
5. Provide Cockpit/CLI snapshot command.

## Metric Formula

```
weekly_adoption_rate = accepted_by_principal / signals_count
falsification_status = 
  "green"  if accepted_by_principal >= 3 AND consecutive_weeks >= 12
  "amber"  if accepted_by_principal >= 1 AND accepted_by_principal < 3
  "red"    if accepted_by_principal == 0
  "unmeasured" if signals_count == 0 (no real data, fail-closed)
```

## Circuit Breaker

If real signals/accept data is unavailable, emit `unmeasured` + blocker list. Never use PR/CI/agent self-report counts. Never use synthetic/fixture samples to inflate adoption.

## Non-goals

- Do not achieve 12 consecutive weeks (that's runtime fact, not a single delivery)
- Do not include PR/CI/agent self-reports or synthetic samples
- Do not implement multi-channel notifications (HITL-02 scope)

## Strategy refs

- `docs/superpowers/specs/2026-09-05-obj-value-portfolio-split-design.md` §T4-03
- `KR-VALUE-WEEKLY-ADOPTION` in `docs/plans/3y-bet-ledger.yaml`
- VISION-2029 falsification: 12 weeks × ≥3 accepted suggestions

## Output Schema

```json
{
  "schema_version": "weekly-value-snapshot/v1",
  "week_iso": "2026-W36",
  "window": {"start": "...", "end": "..."},
  "signals_count": 0,
  "accepted_by_principal": 0,
  "weekly_adoption_rate": 0.0,
  "status": "unmeasured",
  "falsification_risk": "insufficient_data",
  "blockers": ["event-ledger-missing"]
}
```