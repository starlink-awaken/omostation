---
id: ADR-0402
status: ACCEPTED
lifecycle: spec
owner: architecture-governance
last-reviewed: 2026-09-20
type: ssot
related:
  - ADR-0195
---

# ADR-0402 — 声明/执行鸿沟: 多尺度信号而非缺陷

- **Status**: ACCEPTED
- **Date**: 2026-09-20
- **Owner**: architecture-governance
- **Parent**: ADR-0195 (ISC-2: 声明/执行鸿沟收敛)

## 问题

`DECL_EXEC_GAP` 指出: `bet_ledger = 100` (计划面: 426/426 全闭) 但
`compass_radar = 50` (运行面), `maturity_scorecard = 62`, spread = 50。

该张力被当作一个 `critical` 未关闭债务。本问: **这个 50 分的鸿沟, 是缺陷还是信号?**

## 认定

**是信号, 而非缺陷。** 理由:

1. **两个分数回答的不是同一个问题。**
   - `bet_ledger` 回答: "我们对 3 年计划的承诺闭环了多少?" (plan-completeness)
   - `compass_radar` 回答: "当前系统的运行健康是什么?" (runtime health)
   - ADR-0195 ISC-2 **已故定** 权重为 governance×0.3 + freshness×0.2 +
     runtime×0.5 —— **运行面说了算**。计划面=100 并不取胜, 因为权重只有 0.3。

2. **`maturity-align.py` 已原样落实这一解释。** `declaration_execution_gap`
   (ledger vs compass spread) **报告但不加权**进 `health_score`;
   `reconciliation_score` 只衡 **同口径一致性** (compass vs scorecard),
   回避了自指 (计划全闭 → spread 恒等于 100−compass → reconciliation 恒等于
   compass 的恶搞)。

3. **gap 大正是预期之中。** 计划封单而运行未修复 ⇒ ledger=100 & compass=50 是
   **正常** (计划先行, 执行滞后)。因此健康分 `health_score≈50` 正确反映了
   "计划完备但当前运行仍欠佳". 让健康分跳上去, 才是**伪高** (ADR-0195 ISC-1
   把 84 当作虚高打回)。

## 结论

- `declaration_execution_gap` **>= 10** 时, 作为 **cross-scope health signal**
  (当前值 50 ≫ 10 ✓, 照明"计划完结 ≠ 运行恢复" —— 如设计), **不归类为缺陷**,
  **不得因其降低 maturity/reconciliation 分数**, **不得一键关闭 DECL_EXEC_GAP**。
- `DECL_EXEC_GAP` 归结为 `resolved: accepted-design` —— 该张力已被 ADR-0195 +
  ADR-0402 显式接受为架构意图。唯一后续行动: 推动 `compass_radar` 自身上升
  (即推动**运行面**修复, 而非改动分数)。

## 配套

| 改动 | 目的 |
|----|----|
| 本 ADR | 把"gap=by-design" 显式化, 为关闭 DECL_EXEC_GAP 提供**真实可考**证据 |
| `maturity-align.py` 语义 (已就绪) | `declaration_execution_gap` 仅报告, 不加权 |

## 风险

- 误读为"放弃提升健康": 否 —— gap 信号依然可见 (>=10), 只是不当作缺陷关单。
- 治理腐蚀: 若未来有人在无 ADR 下把 ledger/compass 等同来压分, 则违反 ADR-0195
  的同口径原则 —— 将被 `gac-local-gate maturation-align` 守卫阻断。

## 回退

如判定该信号应作为缺陷追踪, 反向: 把 `declaration_execution_gap` 加权入
`health_score` 并重新打开 `DECL_EXEC_GAP`; 删除本 ADR。
