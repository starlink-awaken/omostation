---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y3H1-T3-01 复盘
type: retro
---
# BET-Y3H1-T3-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 4 weeks; done_at 2026-08-19。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
SceneColdStartPlanner (scene_cold_start.py): capability_ref 匹配最佳源场景; 折扣播种 (0.8x, max 0.6); 复用追溯; 预估冷启动周数; 7 tests PASS
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
冷启动通过 capability_ref 复用源场景校准 + 折扣播种, 预估周数可量化; "2 周"是目标不是硬约束。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
scene_cold_start.py SceneColdStartPlanner + 7 tests; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
冷启动走 SceneColdStartPlanner; 折扣播种 0.8x/max 0.6 是默认参数。
