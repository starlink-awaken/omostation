---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q3-T6-01 复盘
type: retro
---
# BET-Y2Q3-T6-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 2 weeks; done_at 2026-08-18。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
surface 审计通过 (exit 0); test_loc 未下降; gac_required +1; 减法配额制运行中
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
减法配额制从规则层面生效: 新增脚本须同时归档。本轮无净增, 配额制本身成为第一道防线。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
surface 审计通过, test_loc 未下降, gac_required +1; 无净增脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
减法配额制继续运行; 归档统一进 bin/_archive/<bet-id>/。
