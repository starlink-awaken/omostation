# `.omo/debt/items/` — Debt Canonical SSOT

> **状态**: active · **类型**: lifecycle SSOT · **层级**: `.omo/` state plane
> **创建**: 2026-07-06 (修正 c82cbd23 误判 — 把整个 `.omo/debt/` untrack)

## 这是什么

债务项 (debt item) 的 **canonical SSOT**——每个债项一个 yaml 文件, 由 broker `omo governance ingress-debt` 写入 (双写: canonical 到此 + delivery artifact 到 `runtime/omo/_delivery/ingress/debts/`).

跟 `.omo/tasks/` 同类——都是 lifecycle 治理数据 (有 status / lifecycle_state / evidence / history), **该入仓可追溯**.

## 为什么入仓 (架构原则)

| 原则 | 体现 |
|------|------|
| SSOT 契约 | `mutation-surfaces.yaml` 声明 `mutation_target: .omo/debt/items/` (canonical) |
| 一致性 | 跟 `.omo/tasks/` 同等 (lifecycle SSOT), 都入仓 |
| X1-X4 治理 | lifecycle/evidence/x3_tier 可追溯; GaC 规则 target 此目录 |
| digest 模式 | 派生产物 (dashboard 等) 由 `write_dashboard` 从此 + metrics 派生 |

## 为什么之前空

c82cbd23 (2026-06) "untrack .omo/debt/ — 运行时数据不应入仓" 误判——把 items/ (SSOT) 跟派生产物 (dashboard 等) 一起 untrack. 2026-07-06 修正: `.gitignore` 加例外 `!.omo/debt/items/`, 恢复 SSOT 入仓.

## 当前状态 (2026-07-06)

**空**——主仓 workspace 无真生产债. `runtime/omo/_delivery/ingress/debts/` 的 10 个 artifact 全是测试/self_healing 自动告警/aetherforge budget demo, **非生产债**, 不 re-ingress.

未来 broker 跑真生产债时, canonical yaml 落此目录, GaC 规则 (CR-X3-DEBT-TIER / CR-DEBT-*) 真检查 (不再 vacuous PASS).

## 相关

- broker: `projects/omo/src/omo/omo_ingress_debt.py:upsert_debt_item`
- 派生产物生成器: `projects/omo/src/omo/omo_debt.py:write_dashboard`
- GaC 规则: `.omo/_truth/registry/governance-checks.yaml` (CR-DEBT-*)
- mutation 声明: `.omo/_truth/registry/mutation-surfaces.yaml` (omo-governance-ingress-debt)
