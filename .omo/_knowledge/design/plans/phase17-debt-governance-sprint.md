# Phase 17 — Debt Governance Sprint

> **周期**: 1 day | **前置**: Phase 16 completed | **门禁**: 绿色清单全部修复+验证

## 概述

Phase 17 为债务治理冲刺：清理 agentmesh 迁移残留 + kairon 包健康修复 + .omo 债务台账清理。
基于 2026-06-03 全面深度审计发现的 **10 项绿色清单**，全部修复后进入 Knowledge Capture/Search Pilot。

## 依赖关系

```
Wave D1 — Governance Cleanup（5 项治理文档修复，无依赖）
  ├── T1 [P1] 清理 debt/items/ 6 对重复文件
  ├── T2 [P1] 修复 ../_truth/INVENTORY.md 包数
  └── T3 [P2] 更新 CONSISTENCY-CHECK.md
  └── T4 [P2] 修复任务描述 158/158
  └── T5 [P2] 更新 R3 债务描述

Wave D2 — kairon P0/P1 Fixes（并行，无相互依赖）
  ├── T6 [P0] 修复 forge tools-registry.json
  ├── T7 [P0] 添加 sharedbrain-standalone 基础测试
  ├── T8 [P0] 替换 metaos 15 处 sys.path.insert
  ├── T9 [P1] 补全 5 包 dependencies 声明
  └── T10 [P2]验证 R1 产品交互层进入 Phase 17 计划

Wave D3 — 验证 + 闭环
  └── T11 全量验证 + 更新状态
```

## 门禁条件

```
☐ 所有 P0 修复验证通过
☐ .omo debt/items/ 无重复文件
☐ ../_truth/INVENTORY.md 与 PROJECTS.yaml 包数一致
☐ 所有新代码通过 ruff lint
```

## TASK_POOL 映射

| ID | Task | Wave | 预估 | 状态 |
|----|------|------|------|------|
| T1 | 清理 debt 重复文件 | D1 | 5min | **backlog** |
| T2 | 修复 INVENTORY 包数 | D1 | 5min | **backlog** |
| T3 | 更新 CONSISTENCY-CHECK | D1 | 15min | **backlog** |
| T4 | 修复任务描述 | D1 | 5min | **backlog** |
| T5 | 更新 R3 债务描述 | D1 | 5min | **backlog** |
| T6 | 修复 forge 注册表 | D2 | 30min | **backlog** |
| T7 | standalone 添加测试 | D2 | 30min | **backlog** |
| T8 | 替换 metaos path.insert | D2 | 1h | **backlog** |
| T9 | 补全依赖声明 | D2 | 1h | **backlog** |
| T10 | 验证 R1 计划 | D2 | 10min | **backlog** |
