# Closeout — 2026-07-15 Wave2 Cockpit UI dashboard

## Landed

| Item | Detail |
|------|--------|
| ADR-0191 | UI consumes c2g.wave2.dashboard.v1 |
| cockpit API | `GET /api/wave2/dashboard` + helpers_wave2 |
| cockpit-ui | Wave2DashboardView + nav + tests |
| verify | API 3 tests · UI 2 tests · vite build baseline |

## Operator

1. Start cockpit dashboard (port 8090 default)
2. Open UI → **系统治理 → Wave2 预测面板**
3. Or CLI: `cockpit wave2 dashboard`
