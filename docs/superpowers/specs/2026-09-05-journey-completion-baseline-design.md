---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T4-02
risk_level: L1
human_gate: false
value_indicator_policy: true
type: ssot
last_updated: 2026-09-05
---

# Journey Completion Rate Baseline — Design

## Problem

`KR-VALUE-JOURNEY-COMPLETION` is registered (T1-14) but `unmeasured`. No
baseline exists. The north_star_meter_v2 only measures weekly adoption
episodes; it has no journey-completion axis. Without a baseline, Y2 targets
(≥50% completion) have no ground truth.

## Decision

1. Add `bin/bc-os/north_star_meter_v3.py` with a new `journey-completion` axis:
   - **Denominator**: real external-signal instances that entered a work journey
     (source: `event-ledger.sqlite3` events with `type=signal.ingested` and
     `domain=work`, joined to `journey_instance` records).
   - **Numerator**: journeys that reached a human-adjudication terminal state
     (`outcome.accepted`, `outcome.edited`, `outcome.rejected`) and are not
     discard-only (`outcome.discard` without human review).
   - **Missing data**: emit `"unmeasured"` with a gap inventory, never `0%`.
2. Extend `bin/gac/value-tracker.py` with `--axis journey-completion` so the
   baseline receipt can be recorded as value evidence.
3. Update `KR-VALUE-JOURNEY-COMPLETION.baseline.status` to `measured` in
   `3y-bet-ledger.yaml` with `evidence_refs` pointing to the baseline receipt.
4. Publish first weekly baseline receipt to `docs/reports/`.

## Non-goals

- Do not target ≥50% completion (Y2 goal). This BET only establishes a verifiable baseline.
- Do not use proxy metrics (health scores, capability pass rates, mtime deliveries).
- Do not modify Cockpit UI (CLI/JSON receipt is sufficient).

## Circuit breaker

If real journey samples are insufficient (< 7d window or < 1 journey),
remain `unmeasured` and output a gap inventory. Never synthesize or backfill
with fixtures.

## Metric definition

```
journey_completion_rate = completed_work_journeys / entered_work_journeys

where:
  entered_work_journeys  = COUNT(DISTINCT journey_id FROM journey_instance ji
                         JOIN signal_event se ON se.id = ji.trigger_signal_id
                         WHERE se.domain = 'work'
                           AND se.timestamp >= window_start
                           AND se.timestamp < window_end)
  completed_work_journeys = COUNT(DISTINCT ji.id FROM journey_instance ji
                         JOIN outcome_event oe ON oe.journey_id = ji.id
                         WHERE oe.verdict IN ('accepted', 'edited', 'rejected')
                           AND oe.review_type != 'discard_only'
                           AND oe.timestamp >= window_start
                           AND oe.timestamp < window_end)
```

## Output schema (JSON)

```json
{
  "schema_version": "journey-baseline/v1",
  "window": { "start": "...", "end": "...", "days": 7 },
  "metric": "journey_completion_rate",
  "status": "measured | unmeasured",
  "value": 0.0,
  "denominator": 0,
  "numerator": 0,
  "evidence_refs": ["receipt://..."],
  "gap_inventory": []
}
```

## Strategy refs

- `docs/superpowers/specs/2026-09-05-obj-value-portfolio-split-design.md` §T4-02
- `KR-VALUE-JOURNEY-COMPLETION` in `docs/plans/3y-bet-ledger.yaml`
