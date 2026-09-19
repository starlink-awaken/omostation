---
schema_version: receipt/v1
type: report
title: Weekly Adoption Falsification Meter — First Receipt
bet_id: BET-Y1Q4-T4-03
kr_id: KR-VALUE-WEEKLY-ADOPTION
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last_updated: 2026-09-05
---

# Weekly Adoption Falsification Meter — First Receipt

## Baseline Status: UNMEASURED (tooling established, runtime data pending)

This receipt records the **first weekly adoption snapshot** for
`KR-VALUE-WEEKLY-ADOPTION`, the VISION-2029 falsification meter
(≥3 accepted suggestions/week for 12 consecutive weeks by 2027-12-31).

The measurement tooling (`bin/bc-os/weekly-value-report.py`) is in place
and produces verifiable weekly snapshots. Current status: `unmeasured`
because the runtime event ledger (`runtime/omo/event-ledger.sqlite3`)
is not available in this worktree.

## Metric Definition

```
signals_count            = real external signals ingested in the ISO week
accepted_by_principal    = suggestions where verdict='accept' AND binding=true
weekly_adoption_rate     = accepted_by_principal / signals_count
status                   = unmeasured if signals==0
                          red       if accepted==0
                          amber     if accepted in [1, THRESHOLD)
                          green     if accepted >= THRESHOLD (3)
```

## First Measurement (2026-W36)

```json
{
  "schema_version": "weekly-value-snapshot/v1",
  "week_iso": "2026-W36",
  "window": {
    "start": "2026-09-07T00:00:00Z",
    "end": "2026-09-14T00:00:00Z"
  },
  "signals_count": 0,
  "accepted_by_principal": 0,
  "weekly_adoption_rate": 0.0,
  "status": "unmeasured",
  "falsification_risk": "insufficient_data",
  "consecutive_qualifying_weeks": 0,
  "blockers": ["event-ledger-missing"]
}
```

## Circuit Breaker

Per BET-Y1Q4-T4-03 design: never use PR/CI/agent self-reports, synthetic,
or fixture samples. When event ledger is unavailable, emit `unmeasured`
+ blocker inventory. The falsification bar (VISION-2029 §0.3) cannot be
falsified without authentic principal-accept verdicts on real signals.

## Next Steps

1. Deploy to runtime where event-ledger.sqlite3 is populated
2. Run weekly: `python3 bin/bc-os/weekly-value-report.py --append`
3. Append to `docs/reports/weekly-value-snapshots.jsonl`
4. Track toward 12 consecutive weeks × ≥3 accepted

## Tooling

- **Meter**: `bin/bc-os/weekly-value-report.py --json`
- **Recorder**: `bin/gac/value-tracker.py --weekly-snapshot --week 2026-WXX`
- **Spec**: `docs/superpowers/specs/2026-09-05-weekly-adoption-meter-design.md`
- **Snapshot log**: `docs/reports/weekly-value-snapshots.jsonl`