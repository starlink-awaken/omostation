---
title: BET-Y1Q3-T6-12 retro — MOSBeliefManager 运行时计数解耦
type: retro
owner: engineering-agent
created: 2026-08-20
bet: BET-Y1Q3-T6-12
lifecycle: history
last_updated: 2026-08-20
---

# BET-Y1Q3-T6-12 复盘（五问）

## Q1 实际耗时 vs appetite?
- **appetite**: 1 hour
- **实际**: 20 minutes
- **比例**: 3x 快于计划，精准定位并消除动态回写脏行。

## Q2 done_when 是否全部通过?
- [x] MOSBeliefManager 默认写入 runtime truth 投影
- [x] `.omo/_truth/registry/memory-os.yaml` 恢复为干净静态 SSOT
- [x] projects/omo 相关单元测试全绿通过 (38 passed)
- [x] `make gac-local-gate` 46 项检查全部通过

## Q3 过程中发现的与 plan 不符的事实 (打假)
- 原先部分测试与运行时会直接调用 manager 并产生未提交的 `as_of` 和 `total_capability_calibrations`，将 schema 声明与动态计数混在同一文件，破坏了 git 索引整洁性。

## Q4 净增减
- 静态 SSOT 注册表去除动态污染行，架构平面彻底解耦。

## Q5 下一个认领本 track 的 agent 需要知道什么?
- 静态 Schema 与策略放在 `.omo/_truth/registry/`；动态遥测与计数一律写入 `.omo/state/` 或 runtime projections。
