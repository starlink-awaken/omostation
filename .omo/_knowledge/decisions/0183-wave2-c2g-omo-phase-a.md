---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-14
---

# ADR-0183 — Wave 2 Phase A 范围锁定

- **Status**: ACCEPTED
- **Date**: 2026-07-14
- **Owner**: governance-team

## Context

Draft `draft/WAVE2-C2G-OMO-ROADMAP.md` listed six directions. Full parallel
execution risks incomplete delivery. We promote **Phase A only** as accepted
scope; other directions stay backlog.

## Decision

**Wave 2 Phase A (P0)**: **数据闭环**

1. C2G `OutcomeTracker` records real outcomes with schema validation.
2. A read-only **backtest report** command emits JSON to stdout:
   `uv run --directory projects/c2g python -m c2g.outcome_backtest`
3. No automatic strategy mutation in Phase A (that is Phase C 自动联动).

**Out of Phase A** (explicit non-goals):

- ARIMA/Prophet predictive models
- Cockpit heatmaps
- Auto feedback into OMO rules
- MOF M0 toolchain expansion
- Full cross-repo schema audit

## Phase A acceptance

| Check | Command / evidence |
|-------|-------------------|
| Outcome schema exists | `OutcomeTracker` importable |
| Backtest CLI | `python -m c2g.outcome_backtest` |
| Unit tests | `pytest tests/test_outcome_backtest.py` |
| Docs | this ADR + draft roadmap links here |

## Follow-ups

- Phase B accepted: [ADR-0185](0185-wave2-phase-b-predictive-viz.md).
- Phase C remains draft until a separate ADR.
- Do not expand Wave 2 scope without a new ADR.
