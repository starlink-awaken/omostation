---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q2-T6-05 复盘
type: retro
---
# BET-Y1Q2-T6-05 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 days。减法配额制门禁（规则数基线 + 增删对开）08-08 落地（done_at 2026-08-08），未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 新增 GaC 规则的 PR 必须同时删除一条, 否则门禁失败 | ✅ gac-validate _check_quota: 规则数超基线 fail |
| 新增 ADR 的 PR 必须同时归档一份 | ✅ adr-coverage 门禁联动 |
| 例外须带 SWARM_ESCAPE_ID 并记录 | ✅ swarm-escape 台账 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **减法配额需要一个可信基线**: governance-checks.yaml 现登记 rule_baseline=136（规则数），基线漂移会让配额失去意义 —— 基线本身也要被门禁守护（P74 精神: 靠机制不靠自觉）。
2. **「减规则」要先有规则级违规数据**: #1234 (P1 rule-violations.jsonl) 为减法提供数据驱动依据，配额是结果层约束、违规数据是原因层输入。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- gac-validate.py _check_quota（规则数基线检查）
- governance-checks.yaml subtraction_quota.rule_baseline=136
- P1 rule-violations.jsonl 接线 (#1234)
- 无新增 ADR（配额即 ADR-0249 治理比率的延续）

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 新增 GaC 规则必须同时删一条，否则 gac-validate fail；基线 136 在 governance-checks.yaml。
2. 例外走 SWARM_ESCAPE_ID + 台账记录。
3. 减规则以 rule-violations.jsonl 数据为依据，不靠拍脑袋。
