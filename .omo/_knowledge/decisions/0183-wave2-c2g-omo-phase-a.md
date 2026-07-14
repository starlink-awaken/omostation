---
status: accepted
date: 2026-07-14
id: 0183
title: Wave 2 C2G+OMO — Phase A (data closed loop) scope
---

# ADR-0183 — Wave 2 Phase A 范围锁定

## Context

Draft `draft/WAVE2-C2G-OMO-ROADMAP.md` listed six directions. Full parallel
execution risks incomplete delivery. We promote **Phase A only** as accepted
scope; other directions stay backlog.

## Decision

**Wave 2 Phase A (P0)**: **数据闭环**

1. C2G `OutcomeTracker` records real outcomes with schema validation.
2. A read-only **backtest report** command (or script) reads tracker store and
   emits JSON under `runtime/omo/_delivery/` via broker-safe paths when writing
   governed state; otherwise stdout-only is acceptable for Phase A.
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
| Outcome schema exists | `projects/c2g` outcome module importable |
| Backtest CLI/script | `python -m c2g...` or `scripts/` entry documented |
| No direct-omo-io | contract_gatekeeper clean on new code |
| Docs | this ADR + draft roadmap links here |

## Follow-ups

- Phase B/C remain draft until separate ADRs.
- Do not expand Wave 2 scope without superseding this ADR.
