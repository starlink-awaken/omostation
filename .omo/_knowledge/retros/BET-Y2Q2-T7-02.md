---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q2-T7-02 复盘
type: retro
---
# BET-Y2Q2-T7-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 weeks; done_at 2026-08-18。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
v2 场景卡 5 张 (knowledge-ingest/assisted + meeting-supervision + research-pipeline + periodic-reporting + project-supervision)
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
以"场景卡 + shadow 生命周期"承载, 而非真实现业务长流程; 验证抽象对长流程成立, 止步 shadow 不升 assisted。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
5 张 v2 场景卡; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
shadow 场景只做骨架实装, 业务长流程由场景卡声明, 后续按卡升级。
