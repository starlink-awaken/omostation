---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q3-T3-01 复盘
type: retro
---
# BET-Y2Q3-T3-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 weeks; done_at 2026-08-19。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
transfer_calibration (omo_belief.py): 加权平均迁移 + 来源追溯 (transferred_from/transfer_operator/audit); min-samples 防低置信传播; 6 tests PASS
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
"学习是真的"——场景经验可迁移改善另一场景判断; min-samples 防线防止低置信样本污染目标场景。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
omo_belief.py transfer_calibration + 6 tests; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
校准迁移带来源追溯, 审计链完整; min-samples 是防污染关键参数。
