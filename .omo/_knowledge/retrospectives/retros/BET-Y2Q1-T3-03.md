---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q1-T3-03 复盘
type: retro
---
# BET-Y2Q1-T3-03 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 2 weeks; done_at 2026-08-18。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
MentalModel (mental_model.py): world/self/intent 三模型注入 SceneWatcher; 同一 confidence 在不同 calibration 下产生不同决策; 10 tests PASS
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
SceneWatcher 注入三模型后决策依赖历史与上下文而非纯阈值, 但"脱离纯阈值"是渐进式, 部分场景仍保留阈值兜底。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
mental_model.py + SceneWatcher 注入 + 10 tests; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
MentalModel 在 mental_model.py; SceneWatcher 决策链路已注入三模型, 后续场景接入时复用注入。
