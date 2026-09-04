---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q4-T2-01 复盘
type: retro
---
# BET-Y2Q4-T2-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 2 weeks; done_at 2026-08-19。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
4 信号源全绑定场景 (apple_mail+netease→document-review, github_push→engineering-delivery, inbox_folder→unified-inbox); 周信号量运行时观测中
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
感知面从 2 根管子扩展到 4 信号源全绑定场景, 但"第三/四根"实际是信号源扩展而非全新管子类型。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
4 信号源 → 场景绑定; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
信号源注册在 signal-sources.yaml, 绑定场景在 scene card; 周信号量观测确认可用性。
