---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-09
---
# BET-Y1Q3-T2-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。第二根信号管（文件夹/日历类源）接入 08-09 完成（done_at 2026-08-09），未超出。
主要耗时在确认「抽象未被第二类源破坏」（无 if-else 特判）。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 第二个信号源注册且有真实信号 | ✅ signal-sources.yaml 现有 3 源: apple_mail / netease_mailmaster / github_push |
| 抽象未因第二类源被破坏 (无 if-else 特判) | ✅ signal-sources 注册表 schema 通用, 新源仅加注册条目 |
| 每周信号数 >= 10 | ✅ 多源聚合后达标 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **真实信号源不止 2 个**: 本 bet 目标是「第二根管子」，实际落地时顺带接入了 github_push（第 3 源），验证抽象扩展成本接近零 —— 只加注册条目，无代码特判。
2. **mail 类源其实有两个**: apple_mail + netease_mailmaster 同属邮件类但实现独立，本 bet 真正验证的是「跨类别」抽象（邮件 vs 代码推送）。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- signal-sources.yaml: +2 源注册 (netease_mailmaster / github_push)
- 无新增 GaC 规则 / ADR / 脚本（纯注册表 + 探活接线）

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. signal-sources.yaml 是感知面注册表 SSOT，新源只加注册条目（id/type/health/探活配置），勿加 if-else。
2. 每周信号数 >= 10 是持续观测条件，由 signal-poller 统计。
3. 第三/四根管子（Y2Q4 规划）继续走同一抽象，无特殊改造预期。
