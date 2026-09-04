---
id: ADR-0416
title: Y2 年度门 — 愿景证伪判定（BET-Y2Q4-T1-01）
status: archived
lifecycle: spec
owner: 夏明星
created: 2026-08-18
last_updated: 2026-08-18
deciders:
  - 夏明星 (最终确认)
  - governance-agent (起草)
related:
  - .omo/_knowledge/decisions/0415-reject-agt-integration-adopt-capability-parity.md
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - docs/plans/BET-EXECUTION-ROADMAP-2026H2.md
---

# ADR-0416: Y2 年度门 — 愿景证伪判定

## Context

按 [BET-Y2Q4-T1-01](../../../docs/plans/3y-bet-ledger.yaml) 要求，对愿景做一次不可回避的证伪判定。源材料：[三年规划 §0.3 愿景（收窄版）](../../../docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md) 与 §2.2 三年后可验收状态。

## 愿景陈述

> 织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。

## 证伪条件（原文）

> 若到 2027-12-31 未能连续 12 周每周产出 ≥ 3 条被本人采纳的建议，则本定位被证伪，应转为纯知识管理工具或关停。

## 可证伪命题（3 条）

| # | 命题 | 证伪判据 | 当前证据（2026-08-18） |
|---|------|---------|----------------------|
| P1 | 系统能**持续产出**被采纳建议 | 连续 12 周每周 ≥ 3 条采纳 | 无系统化的"建议→采纳"记录链路；BRIEF 产能轨显示 0 done / 63 planned（0% 完成率），但这是 backlog 非建议采纳数据 |
| P2 | 修订率**逐年下降**（Y2 降 20%） | 可对比的修订率基线 | Y1 基线未建立（无修订率度量） |
| P3 | 可持有性**守住**（冗余清零 + 保护量不牺牲） | 逐项冗余清单清零 | 部分达成：omo-debt 可并入 omo（未执行）、family-hub/observability 休眠（未清理）、知识层双头（gbrain × kairon 仍并存） |

## 判定

**愿景暂未被证伪，但三条命题均无充分证据支撑**——不是"通过了"，是"还没到判定时刻"。

- P1：建议采纳记录链路不存在 → 无法判定 → 需先建度量（见 Consequences）
- P2：Y1 基线缺失 → Y2 无法对比 → 需立即建基线
- P3：部分达成 → 继续执行减法

## Decision

1. **愿景维持**：不触发证伪转轨。
2. **建度量优先于做判断**：本 ADR 的附属行动 = 建立"建议→采纳"记录链路 + Y1 修订率基线（3 周内完成，绑 BET-Y2Q1-T3-02）。
3. **P3 继续推进**：未清零冗余项走 BET-Y2Q3-T6-01（减法第二轮维持）。

## Consequences

- 2027-12-31 为硬证伪截止日
- 若 P1/P2 度量在建好后 4 周内无改善趋势，提前触发收窄评估

## References

- [三年规划 §0.3 愿景](../../../docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md)
- [BET-Y2Q4-T1-01 goal](../../../docs/plans/3y-bet-ledger.yaml)
