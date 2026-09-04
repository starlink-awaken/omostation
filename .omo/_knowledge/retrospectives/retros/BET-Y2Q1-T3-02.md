---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q1-T3-02 复盘
type: retro
---
# BET-Y2Q1-T3-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week; done_at 2026-08-18。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
IntentModel + Prioritizer (src/agora/intent/): whats_most_important(top_n); 9 tests PASS
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
意图模型落在 agora/intent 而非 omo, 与起初预期路径不同。goals/tasks 变更经 BOS 事件实时进入 MOS, 复用既有事件面。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
agora/intent/ IntentModel + Prioritizer + 9 tests; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
意图优先级在 agora/intent Prioritizer; goals/tasks 变更需发 BOS 事件才实时。
