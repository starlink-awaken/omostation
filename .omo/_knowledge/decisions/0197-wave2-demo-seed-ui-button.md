---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0197 — Cockpit「加载演示数据」按钮

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + cockpit + cockpit-ui

## Context

ADR-0193 CLI seed exists; empty Wave2 panels need one-click in console.

## Decision

1. `POST /api/wave2/demo-seed` body `{ "reset": true|false }`
2. Writes `runtime/c2g/outcomes` only (never `.omo/`)
3. UI button **加载演示数据** then refreshes dashboard
4. Demo fixture only — not production analytics

## Verification

```bash
pytest projects/cockpit/src/cockpit/tests/test_api_wave2_dashboard.py -q
# Wave2 panel → 加载演示数据
```
