---
id: BET-Y1Q3-T1-04
type: retro
status: archived
date: 2026-08-18
bet_id: BET-Y1Q3-T1-04
north_star_ref: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
related:
  - BET-Y1Q3-T1-03
  - ADR-0200
  - docs/plans/annual-gate-rebaseline-2026Q4.md
  - docs/plans/annual-gate-decision-summary-2026Q4.md
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q3-T1-04 Retro: Y1Q4 年度门修订评审 — code_loc 重基线"
---

# BET-Y1Q3-T1-04 Retro: Y1Q4 年度门修订评审 — code_loc 重基线

## Q1 目标回顾
Y1Q4 门 `code_loc <= 690000` 按 Y1 初基线制定, 未纳入 gbrain 重写噪音与新项目出生两变量。正式走年度门修订: 用 T1-03 净值口径重算真实缺口, 产出重基线提案交人类拍板。

## Q2 实际结果
完成年度门重基线闭环:

1. **提案产出** (`annual-gate-rebaseline-2026Q4.md`): 三情景量化
   - A 守原门(690K): 净值口径也守不住(871K > 690K)
   - B 调门(1,100K): 推荐
   - C 拆门: 作为 B 补充观测
2. **ADR-0200 草案**: 按推荐情景 B 预写(Proposed → Accepted)
3. **人类批示(2026-08-18)**: 采纳推荐方案
4. **落地**: ADR-0200 转 Accepted + Y1Q4 门值更新(690K → 1,100K)
5. **决策摘要归档**: `annual-gate-decision-summary-2026Q4.md`

## Q3 目标偏差
- 净值口径数据显示: 名义 src_loc 1,663,966 中, gbrain 重写噪音 +179K/-179K(净 +360),
  _root churn +677K, 真实业务增长 ~+145K。690K 门严重失真。
- 门检从"总量口径"切换为"净值口径"是本次修订的核心, 远超简单的数值调整。

## Q4 机制沉淀
- **年度门重基线流程**: 提案(三情景量化) → ADR 草案(按推荐预写) → 人类批示 →
  ADR 转 Accepted + 门值更新 + retro。全链路可复用。
- **净值口径**: numstat 净值(add-del)剥离重写噪音, 重写是维护成本而非表面扩张。
- **决策材料精简**: 决策摘要(一句话结论 + 数据表 + 三勾选)让人类快速拍板。

## Q5 给下一个 agent 的建议
- Y2Q4 年度门(2027-12)应复用本流程, 提前用净值口径做基线。
- 分项目净增长观测(季度)需持续执行, 为 Y2 门提供"出生 vs 膨胀"分解。
