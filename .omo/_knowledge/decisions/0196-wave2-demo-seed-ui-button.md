---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0196 — Cockpit「加载演示数据」按钮

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + cockpit + cockpit-ui

## Context

ADR-0193 added CLI seed; empty Wave2 panels still need a one-click console path.

## Decision

1. `POST /api/wave2/demo-seed` body `{ "reset": true|false }`
2. Calls `c2g.demo_seed.seed_demo_outcomes` → `runtime/c2g/outcomes` only
3. UI button **加载演示数据** on Wave2 panel; refreshes dashboard after seed
4. Refuses paths under `.omo/`
5. Not a security boundary for production data — demo fixture only

## Verification

```bash
pytest projects/cockpit/src/cockpit/tests/test_api_wave2_dashboard.py -q
bunx vitest run Wave2DashboardView.test.tsx
```
