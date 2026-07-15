---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0190 — Wave2 dashboard JSON v1 + cockpit entry

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + c2g + cockpit

## Context

Phases A–C produce backtest, forecast/heatmap, and proposals separately.
Cockpit / agents need one stable contract without a React rewrite in the same PR.

## Decision

1. **Schema** `c2g.wave2.dashboard.v1` via `python -m c2g.dashboard_export`
2. Payload: `cards` + `backtest` + `forecast` + `heatmap` + `proposals`
3. `auto_mutate_rules: false` remains part of the contract
4. **L3 entry**: `cockpit wave2 [dashboard|proposals|predictive]` delegates to c2g
5. Optional `--write runtime/c2g/dashboard.json` — **refuse** writes under `.omo/`

## Non-goals

- Full cockpit-ui React heatmap (can consume this JSON later)
- Auto GaC mutation

## Verification

```bash
uv run --directory projects/c2g python -m c2g.dashboard_export --pretty
cockpit wave2 dashboard
pytest projects/c2g/tests/test_dashboard_export.py projects/cockpit/src/cockpit/tests/test_wave2_cmd.py -q
```

## References

- ADR-0185, ADR-0188
- `projects/c2g/src/c2g/dashboard_export.py`
- `projects/cockpit/src/cockpit/commands/wave2.py`
