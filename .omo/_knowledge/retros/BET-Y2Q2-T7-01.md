---
lifecycle: history
owner: governance-team
last_updated: 2026-08-19
title: BET-Y2Q2-T7-01 复盘
type: retro
---
# BET-Y2Q2-T7-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 2 weeks; done_at 2026-08-18。多数能力已在并发 agent 分支积累, 本 bet 为合入 main + 验证 + 补测试, 实际增量时间低于 appetite 全额。

## Q2 done_when 是否全部通过？哪条没过，为什么？
knowledge-ingest.yaml (v2): lifecycle=assisted 第二场景; calibration/recall 运行时指标收集状态 (assisted_active_collecting_evidence)
未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
assisted 放权机制可复制性得到验证: 第二场景 (知识入库) 进入受审执行。指标收集状态机驱动 (active → collecting_evidence)。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
knowledge-ingest.yaml v2 + 运行时指标状态; 无新增 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
assisted 场景需在 scene card 声明 lifecycle=assisted + calibration/recall 指标收集。
