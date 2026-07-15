---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0191 — Cockpit UI 消费 Wave2 dashboard JSON

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + cockpit + cockpit-ui

## Context

ADR-0190 defined `c2g.wave2.dashboard.v1` and CLI/`cockpit wave2` entry.
Operators still lacked an in-console panel.

## Decision

1. **API**: `GET /api/wave2/dashboard` (cockpit dashboard routes)
   - Uses `helpers_wave2.load_wave2_dashboard()` → c2g when importable
   - Degraded empty payload on failure (UI never 500)
2. **UI**: `Wave2DashboardView` page tab **Wave2** under 系统治理
   - Cards + heatmap table + forecast points + proposals list
3. **Nav**: sidebar + command palette + quick actions
4. **Non-goals**: React chart library rewrite; auto-apply proposals

## Verification

```bash
# API
uv run --project projects/cockpit pytest src/cockpit/tests/test_api_wave2_dashboard.py -q
# UI
cd projects/cockpit-ui && bun run test:unit -- src/components/__tests__/Wave2DashboardView.test.tsx
```

## References

- ADR-0190
- `projects/cockpit/src/cockpit/dashboard/helpers_wave2.py`
- `projects/cockpit-ui/src/components/Wave2DashboardView.tsx`
