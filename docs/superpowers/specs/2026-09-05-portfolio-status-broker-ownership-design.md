---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T1-13
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# Portfolio-status broker ownership（BET-Y1Q4-T1-13）

## Goal

Register broker ownership for `.omo/_control/portfolio-status.json` so
`broker_owns_portfolio_targets` returns ok for BOTH required `.omo` targets
(`.omo/goals/current.yaml` already brokered; portfolio-status was missing).
Wire `--check-broker` as the ownership dry-run path.

## Non-goals

- Do not reverse Ledger write direction
- Do not rewrite W0 Markdown projection
- Do not authorize full `--apply-omo` adapter wiring beyond ownership
  (`PORTFOLIO_BROKER_APPLY_NOT_WIRED` remains acceptable per T1-08)

## Architecture

1. Add a `mutation-surfaces.yaml` brokered entry whose `mutation_target` is
   exactly `.omo/_control/portfolio-status.json`, mirroring goals-style
   fields (`broker_ref`, `mode: brokered`, `mutation_target`).
2. Reuse `broker_owns_portfolio_targets` for CLI `--check-broker`; print
   `broker_reason` (`broker_ok` when both targets are owned).
3. Circuit breaker: if no reusable OMO ingress template exists, degrade to
   ownership registration + dry-run docs only — ownership check must still
   pass; apply adapter may remain unwired.

## Done when

1. `mutation-surfaces` registers portfolio-status.json as brokered write owner
2. `broker_owns_portfolio_targets` returns ok
3. dry-run ownership check does not halt with `PORTFOLIO_BROKER_OWNER_MISSING`

## Verify

```bash
python3 bin/plan/portfolio_projection.py --check-broker
# expect: broker_ok
```

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 新建 OMO ingress vs 仅登记 ownership | ownership + dry-run | circuit breaker；apply 仍可 NOT_WIRED |
| 2 | 改 return 文案 vs 保持 `broker_ok` | 保持 `broker_ok` | 既有测试断言；CLI 打印 broker_reason |
| 3 | 重写 Markdown / 反向 Ledger | 不做 | non_goals / T1-08 边界 |
