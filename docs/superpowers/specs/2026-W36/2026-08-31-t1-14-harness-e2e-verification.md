---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: xiamingxing
created: 2026-08-31
last_updated: 2026-08-31
bet_id: BET-Y1Q3-T1-14
risk_level: L2
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# T1-14 Harness E2E 真实场景验证 — 强约束强感知

## Objective

验证 Harness 自举后的强约束与强感知：以真实 BET 走完 8 段全链路，证明 Harness 在架构上明确体现为唯一 S。

## Contract

- 唯一入口 `harness run`，`Policy Registry` 单点决策
- `write_surfaces` 越权写直接 `halt`
- 7 探针中 `toolchain` 探针触发即发 `harness:toolchain:update` 事件

## Grill

- Q1 边界：仅 `docs/plans/3y-bet-ledger.yaml` + `bin/harness`
- Q2 反模式：禁止 `as any`/`@ts-ignore`
- Q3 容量：`appetite 0.5d` 内完成
- Q4 回滚：`git checkout origin/main -- ledger` 即可回滚
- Q5 可观测：`harness trace` 一行回放

## Done when

- `harness ledger add` 成功且 `bet-ledger lint` OK
- `harness probe --emit` 命中 `toolchain` TRIGER
- `harness grill/audit/verify/closeout` 全绿
- `harness trace` 可回放

## Metrics

- `verify --parallel` <10s
- `rework_rate` 0
