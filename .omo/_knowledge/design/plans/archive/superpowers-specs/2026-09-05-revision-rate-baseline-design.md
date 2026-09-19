---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T4-04
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# Principal Revision Rate Baseline — Design

## Problem

VISION-2029 "remember every edit" promise needs a measurable signal:
`KR-VALUE-REVISION-RATE` (principal_revision_rate). T1-14 registered it but
the meter is missing. The metric is the **inverse** of value proof: when
the system remembers well, revision rate drops because accepted suggestions
land close to what the principal wants.

Y2 target: **-20% revision rate**. Without a baseline, no progress measurement.

## Decision

1. Extend `bin/bc-os/north_star_meter_v3.py` with `--revision-rate` mode:
   - `denominator`: total suggestions exiting to principal (verdict in {accept, edit, reject})
   - `numerator`: suggestions where verdict = `edit` (principal signed off after modification)
   - `revision_rate = numerator / denominator`
   - **Equivalent**: signed-Diff commits on suggestion branches
   - Fail-closed `unmeasured` when data missing
2. Update `KR-VALUE-REVISION-RATE.baseline.status` to `measured` (tooling established).
3. Publish first baseline receipt to `docs/reports/`.

## Metric Formula

```
principal_revision_rate = edit_verdicts / total_adjudicated_suggestions

denominator = COUNT(*) FROM outcome_event
              WHERE verdict IN ('accept', 'edit', 'reject')
                AND binding = 1
                AND window ∈ [start, end)
numerator   = COUNT(*) FROM outcome_event
              WHERE verdict = 'edit' AND binding = 1
                AND window ∈ [start, end)
```

Equivalent source (signed-Diff commits):
```
revision_rate = edit_commits / (edit_commits + accept_commits + reject_commits)
```

## Circuit Breaker

If no adjudication data and no signed-Diff samples, emit `unmeasured` + gap inventory.
Never synthesize fake Diff samples or use commit counts/doc word counts as proxies.

## Non-goals

- Do not implement LoRA/SEMA distillation (T10-105/T10-115)
- Do not claim revision rate is already dropping
- Do not use doc word counts or commit counts as proxies for signed Diff

## Output Schema

```json
{
  "schema_version": "revision-rate-baseline/v1",
  "observed_at": "...",
  "window": {"start": "...", "end": "...", "days": 30},
  "metric": "principal_revision_rate",
  "denominator": 0,
  "numerator": 0,
  "value": 0.0,
  "status": "measured | unmeasured",
  "evidence_refs": [],
  "gap_inventory": []
}
```