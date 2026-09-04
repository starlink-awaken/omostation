---
title: BET-Y1Q4-T1-01 retro — Y1 表面积盘点与年度门
type: retro
owner: governance-agent
created: 2026-08-18
bet: BET-Y1Q4-T1-01
related:
  - .omo/_knowledge/retros/gates/Y1-surface-audit.md
  - docs/adr/ADR-0200-y1q4-code-loc-gate-rebaseline.md
lifecycle: history
last_updated: 2026-08-19
---

# BET-Y1Q4-T1-01 复盘（五问）

## Q1 实际耗时 vs appetite?
- appetite: 3 days
- 实际: 1 day (审计 + 报告 + 判定)
- 比例: 3x 快 — 复用 T6-01 归并数据

## Q2 done_when 全部通过?
9 项 done_when: 7 ✅ / 2 待人类决策 (observability 退役 + D2/D3/D5 退役评估)。
核心项 (保护量/归并/去重/年度门) 全达。

## Q3 打假
1. **src_loc 增长是真实业务增长**: +164K 主要来自 aetherforge 内包 (gateway/mesh 保留) + 新业务代码, 非冗余
2. **ADR 只分层不裁剪**: 380 ADR 是历史沉淀, 裁剪成本 > 收益, 分层管理更务实
3. **worktree 口径 vs 含子模块口径**: 890K (worktree) vs 1,692K (含子模块), 均在 1,100K 门内

## Q4 净增减
- 文档: +1 (Y1-surface-audit.md, 76 行)
- 台账: Y1Q4-T1-01 in_progress → done (+1 done)
- ADR: +1 (ADR-0200 年度门重基线)

## Q5 下一个 agent 需知
1. **observability/family-hub 退役**: 待人类决策, 不得自行归档
2. **D2/D3/D5 退役**: T1-07 观察窗后启动
3. **年度门已重基线**: 新 code_loc 门值 1,100K (ADR-0200)
