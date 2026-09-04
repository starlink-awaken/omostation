---
title: BET-Y1Q3-T1-03 复盘 — surface numstat 净值口径
type: retro
owner: governance-team
created: 2026-08-15
related:
  - .omo/_knowledge/audits/surface-area-source-breakdown-20260815.md
context: >-
  surface 审计发现总量口径对重写型变更失真。本 bet 让 surface 输出三口径对照。
  PR #1525 (主仓 56e12f18c)。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T1-03 复盘

## Q1 实际耗时 vs appetite

appetite 1 day, 实际 0.3 天。

## Q2 done_when 全过?

| # | done_when | 结果 |
|---|---|---|
| 1 | surface 输出含 numstat 净值列与原始列并存 | ✅ 三口径: churn_add/churn_del/净值/重写噪音 |
| 2 | 复现审计结论 (gbrain 噪音被剥离) | ✅ 实测 gbrain churn 165,617/165,610, 净值 +7 |
| 3 | 审计方法论固化为可重跑命令 | ✅ bet-ledger.py surface 一条命令含子模块聚合 |

全过, 置 done。

## Q3 计划与事实的偏差

**重大发现修正了审计结论本身**: 审计说 gbrain "+468K/-468K" — 实测是
**165K/165K** (审计的 468K 是含 gbrain 仓内全部历史 churn 的口径差)。方向一致
(纯重写噪音, 净≈0), 数字差 3 倍。净值口径的实测全貌:

- 真实增长 ~+145K: cockpit-ui +30K / omo +27K / cockpit +22K / runtime +22K / omlxc +20K
- gbrain 纯重写 (净 +7), agora 净 +6K
- 重写噪音合计 ~11K (逐文件对称)

**对 T1-04 (年度门重基线) 的直接输入**: 「+926K 缺口」叙事应修正为
「净值 +145K 增长 + 总量口径失真」。Y1Q4 门的 690K 基线数字锚定的是总量口径,
重基线提案必须同时处理口径和数值。

## Q4 表面积影响

+131 行 (bet-ledger +115/test +45 减 merge 冲突)。指标工具自身小膨胀, 换取
全部后续 surface 讨论的诚实口径——值得。

## Q5 给下一个 agent 的建议

1. **T1-04 重基线提案直接引用本 retro 的净值表** (数字已实测, 别再拍脑袋)。
2. numstat 聚合只扫 projects/<sub>/src/ (主仓 projects/ 路径 + 子模块 src/) —
   若未来项目布局变了 (非 src/ 布局), 记得扩 _parse_numstat 的路径集。
3. ruff 净回归检查: 改动前后各跑一次 ruff count 对比 (10→9), 别只看新增文件全绿。
