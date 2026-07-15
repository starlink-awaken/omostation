---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0192 — Wave2 提案 → TaskCenter 闭环（dry-run plan）

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + cockpit + cockpit-ui

## Context

ADR-0191 rendered proposals in UI but operators could not jump to tasks or
preview broker materialization without leaving the console.

## Decision

1. Enrich each proposal with `task_query` + `handoff.tab=TaskCenter`
2. API `GET /api/wave2/proposals/plan` — dry-run of `apply_proposals_as_tasks`
   (`mutation: false`, never creates tasks)
3. UI: per-proposal **在任务中心打开** seeds TaskCenter search
4. UI: **预览 apply plan** loads dry-run actions
5. Real task creation remains CLI-only (`--apply-tasks`) — no auto GaC rewrite

## Verification

```bash
pytest projects/cockpit/src/cockpit/tests/test_api_wave2_dashboard.py -q
bunx vitest run projects/cockpit-ui/src/components/__tests__/Wave2DashboardView.test.tsx
```

## References

- ADR-0188, ADR-0190, ADR-0191
- `helpers_wave2.enrich_proposals_for_handoff` / `load_wave2_proposal_plan`
