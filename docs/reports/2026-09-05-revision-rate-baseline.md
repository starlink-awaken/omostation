---
schema_version: receipt/v1
type: report
title: Principal Revision Rate Baseline — First Receipt
bet_id: BET-Y1Q4-T4-04
kr_id: KR-VALUE-REVISION-RATE
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last_updated: 2026-09-05
---

# Principal Revision Rate Baseline — First Receipt

## Baseline Status: UNMEASURED (tooling established, runtime data pending)

This receipt records the **first baseline measurement** for
`KR-VALUE-REVISION-RATE` (principal_revision_rate).

The measurement tooling (`bin/bc-os/north_star_meter_v3.py --revision-rate`)
is in place and produces verifiable output. Current status: `unmeasured`
because the runtime event ledger is not available in this worktree.

## Metric Definition

```
principal_revision_rate = edit_verdicts / total_adjudicated_suggestions

denominator = COUNT(*) FROM outcome_event
              WHERE verdict IN ('accept', 'edit', 'reject') AND binding = 1
numerator   = COUNT(*) FROM outcome_event
              WHERE verdict = 'edit' AND binding = 1
```

Y2 target: **≤ 0.2** (-20% from baseline once system "remembers every edit").

## First Measurement (2026-09-05, 30d window)

```json
{
  "schema_version": "revision-rate-baseline/v1",
  "observed_at": "2026-09-05T09:33:04Z",
  "window": {"start": "2026-08-06T09:33:04Z", "end": "2026-09-05T09:33:04Z", "days": 30},
  "metric": "principal_revision_rate",
  "denominator": 0,
  "numerator": 0,
  "status": "unmeasured",
  "reason": "event-ledger-not-available",
  "gap_inventory": ["event-ledger-missing"]
}
```

## Circuit Breaker

Per BET-Y1Q4-T4-04 design: never synthesize fake Diff samples or use commit
counts / doc word counts as proxies. When event ledger is unavailable,
emit `unmeasured` + blocker inventory.

## Next Steps

1. Deploy to runtime where event-ledger.sqlite3 is populated
2. Re-run `python3 bin/bc-os/north_star_meter_v3.py --revision-rate --json`
3. Track toward Y2 target (≤0.2)

## Tooling

- **Meter**: `bin/bc-os/north_star_meter_v3.py --revision-rate --json`
- **Spec**: `docs/superpowers/specs/2026-09-05-revision-rate-baseline-design.md`