---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T2-01 复盘
type: retro
---
# BET-Y1Q1-T2-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 days。signal-sources 注册表建立 + 契约 schema + BOS 注册合计约 2 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| .omo/_truth/registry/signal-sources.yaml 建立, 含 apple_mail_inbox 一条 | ✅ |
| schema 含 idempotency_key / dedup_window / failure_policy / health / last_signal_at | ✅ 12 个字段引用 |
| 不可达时 health=unreachable, 禁止呈现为"本周 0 条信号" | ✅ |
| bos://perception/* 在 agora 注册 | ✅ |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **信号「0 条」与「不可达」必须区分**: 早期把感知面不可达静默显示为 0 条信号，掩盖了故障。契约要求 health=unreachable 时禁止伪装成正常空数据。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- .omo/_truth/registry/signal-sources.yaml 注册表
- signal-poller.py 消费接线 (bin/ssot)
- bos://perception/* BOS 注册
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. signal-sources.yaml 是感知面注册表 SSOT，新增信号源必须先登记再接线。
2. health=unreachable 的源不能伪装为 0 条信号（防误导）。
3. 信号源事件由 signal-poller.py 轮询并写入总线（感知面 → 编排闭环）。
