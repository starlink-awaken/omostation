---
schema_version: receipt/v1
type: report
title: Journey Completion Rate Baseline — First Receipt
bet_id: BET-Y1Q4-T4-02
kr_id: KR-VALUE-JOURNEY-COMPLETION
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
last_updated: 2026-09-05
---

# Journey Completion Rate Baseline — First Receipt

## Baseline Status: UNMEASURED (tooling established, runtime data pending)

This receipt records the **first baseline measurement** for
`KR-VALUE-JOURNEY-COMPLETION` (effective work journey completion rate).

The measurement tooling (`bin/bc-os/north_star_meter_v3.py --journey`) is
in place and produces verifiable output. The current status is `unmeasured`
because the runtime event ledger (`runtime/omo/event-ledger.sqlite3`) is
not available in this worktree.

## Metric Definition

```
journey_completion_rate = completed_work_journeys / entered_work_journeys

denominator = real external-signal instances that entered a work journey
numerator   = journeys reaching human-adjudication terminal state
              (accepted/edited/rejected, not discard-only)
```

## First Measurement (2026-09-05)

```json
{
  "schema_version": "journey-baseline/v1",
  "observed_at": "2026-09-05T04:55:43Z",
  "window": {
    "start": "2026-08-29T04:55:43Z",
    "end": "2026-09-05T04:55:43Z",
    "days": 7
  },
  "metric": "journey_completion_rate",
  "status": "unmeasured",
  "reason": "event-ledger-not-available",
  "gap_inventory": ["event-ledger-missing"]
}
```

## Gap Inventory

| Gap | Description |
|-----|-------------|
| event-ledger-missing | `runtime/omo/event-ledger.sqlite3` not present in worktree (runtime artifact) |

## Circuit Breaker

Per BET-Y1Q4-T4-02 design: when real journey samples are insufficient,
remain `unmeasured` and output a gap inventory. Never synthesize or backfill
with fixtures.

## Next Steps

1. Deploy to runtime environment where event-ledger.sqlite3 is populated
2. Re-run `python3 bin/bc-os/north_star_meter_v3.py --journey --json`
3. Update this receipt with actual measured value once data is available
4. Track progress via `python3 bin/gac/value-tracker.py --journey-baseline`

## Tooling

- **Meter**: `bin/bc-os/north_star_meter_v3.py --journey --json`
- **Recorder**: `bin/gac/value-tracker.py --journey-baseline`
- **Spec**: `docs/superpowers/specs/2026-09-05-journey-completion-baseline-design.md`
