---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T4-01 复盘
type: retro
---
# BET-Y1Q1-T4-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。AdjudicationRecorded 事件 + 裁决存储 + decision_id 关联合计约 3 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| OMO 新增 AdjudicationRecorded 事件类型 (verdict/edit_diff/time_spent) | ✅ omo_adjudication.py |
| .omo/_delivery/outcomes/ 落盘且 append-only | ✅ adjudications.jsonl (append-only) |
| 事件可关联回 decision_outcome.decision_id | ✅ decision_id (do-NNNN) 关联 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **裁决数据源稀少**: `.omo/_delivery/outcomes/adjudications.jsonl` 起初仅 1 条（smoke test），真实裁决主要在 pr-harvest.jsonl（152 条，PR 评审即裁决）+ GitHub API 拉取状态。评测集 bet (T4-01 Y1Q4) 依赖本 bet 的真实裁决数据。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- omo_adjudication.py (AdjudicationRecorded 事件 + 裁决存储)
- .omo/_delivery/outcomes/ (append-only jsonl)
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 裁决落盘在 .omo/_delivery/outcomes/adjudications.jsonl（append-only），字段含 verdict/edit_diff/time_spent。
2. decision_id 关联回 MOS decision_outcome 表 (do-NNNN)。
3. pr-harvest.jsonl 是真实裁决的富数据源，评测集生成器 (gen-real-evalset.py) 消费它。
