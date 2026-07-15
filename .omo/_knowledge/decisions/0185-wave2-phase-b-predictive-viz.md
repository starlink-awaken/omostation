---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0185 — Wave 2 Phase B: 预测增强 + 可视化导出

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + c2g

## Context

ADR-0183 locked Wave 2 Phase A (OutcomeTracker backtest, no auto-mutation).
Draft roadmap Phase B called for **预测模型增强** (ARIMA/Prophet) + **可视化**
(Cockpit heatmap). Full ARIMA/Prophet + cockpit UI in one PR risks:

1. Heavy deps (statsmodels/prophet) on a lean c2g package.
2. Cockpit UI coupling before a stable data contract exists.
3. Incomplete delivery if UI and model land half-done.

## Decision

**Phase B scope (this ADR)** — *contract first, heavy models later*:

| Item | Choice |
|------|--------|
| B1 Forecaster | Stdlib **EMA + linear trend** + residual band (`c2g.predictive.PredictiveModel`) |
| B2 Prior blend | Pitch success probability shrinks toward historical mean (`blend_prior`) |
| B3 Viz contract | Risk heatmap JSON (`status × score_bucket`) + Markdown table |
| B4 CLI | `python -m c2g.predictive_report` → stdout JSON (optional `--markdown`) |
| B5 Tracker API | `OutcomeTracker.predictive_report()` |

**Explicit non-goals (Phase B+ / C)**:

- ARIMA / Prophet / neural nets (optional later behind extra extra deps)
- Cockpit React heatmap UI (consumes JSON contract in a later PR)
- Auto write-back into OMO rules (Phase C)
- Strategy auto-mutation from forecast

## Acceptance

| Check | Evidence |
|-------|----------|
| Module | `from c2g.predictive import PredictiveModel, risk_heatmap` |
| CLI | `python -m c2g.predictive_report --data-dir <tmp>` |
| Tests | `pytest tests/test_predictive.py` |
| Pitch blend | history-aware `predict_pitch_success_probability` |

## Consequences

- Cockpit / agents can subscribe to a **stable JSON shape** without waiting for UI.
- Replacing EMA with ARIMA later is a drop-in on `PredictiveModel.fit_series` only.
- Phase C can read `forecast.trend` + heatmap `critical` counts for rule proposals.

## Verification

```bash
cd projects/c2g
uv run pytest tests/test_predictive.py -q
uv run python -m c2g.predictive_report --data-dir /tmp/c2g-empty
```

## References

- ADR-0183 (Phase A)
- `draft/WAVE2-C2G-OMO-ROADMAP.md`
- `projects/c2g/src/c2g/predictive.py`
- `projects/c2g/src/c2g/predictive_report.py`
