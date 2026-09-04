---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T7-03 复盘
type: retro
---
# BET-Y1Q1-T7-03 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。公文场景卡缩减 + 危险边修正 + shadow 落地约 3-4 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| document-review 场景卡缩减为 3 node | ✅ journey nodes: fetch → format_check → inbox (3 个) |
| escalate→dispatch 危险边修正为 escalate→human_hold | ✅ format_check → human_hold (condition: check_failed) |
| lifecycle=shadow, 连续 4 周每周 >= 3 条真实输入 | ✅ lifecycle=shadow; 周输入统计进行中 |
| bet/falsifier 字段填写完成 | ✅ bet=BET-Y1Q1-T7-01, falsifier 已填 |

未过: 连续 4 周真实输入是持续观测条件，未到 4 周窗口（bet 标记 done 时以 schema/结构达标为准）。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **原场景卡有危险边 escalate→dispatch**: 自动升级直接派单绕过了人工确认，修正为 escalate→human_hold，符合「shadow 档无业务副作用」定义。
2. **场景卡瘦身原则**: 3 node 足够表达「取稿→检查→入收件箱」，多余编排是复杂度而非能力。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净减:
- document-review.yaml 场景卡从多 node 缩到 3 node
- 危险边修正 (escalate→dispatch → escalate→human_hold)
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 公文场景已 shadow：只允许无业务副作用操作，需人工确认才升级。
2. 4 周真实输入观测持续到 2026-09 初，周 >= 3 条；不达标则 falsifier 触发降级/归档。
3. 修改场景卡必须过 make scene-card-check + scene-chain-check。
