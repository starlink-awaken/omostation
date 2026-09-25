---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 门禁全景矩阵组件研发 (GatesMatrixView)
bet_id: BET-Y2Q2-T7-06
created: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# 门禁全景矩阵组件研发 (GatesMatrixView) 设计规约

## 1. 目标与背景

门禁矩阵（A1-A9、RF0、RC-DL）是 omostation 体系最高宪法级守门人。原先散落在 `:43191` 底座的单体 HTML 中，交互僵硬且缺乏类型约束。
本规约设计现代化的 React 19 组件 `<GatesMatrixView />`，作为主权驾驶舱体系全景的核心视窗之一。

## 2. 核心架构与功能需求

### 2.1 数据接入与状态机
- 直接消费 `useGatesMatrix()` 或 `useGovernancePanorama()`；
- 支持 5 档判定 Badge：
  - `PASS`：健康翠绿 (`text-emerald-400 bg-emerald-950/40 border-emerald-500/30`)
  - `WARN`：预警琥珀 (`text-amber-400 bg-amber-950/40 border-amber-500/30`)
  - `FAIL`：阻断烈红 (`text-red-400 bg-red-950/40 border-red-500/30`)
  - `BLOCKED`：依赖紫灰 (`text-purple-400 bg-purple-950/40 border-purple-500/30`)
  - `PENDING`：等待执行 (`text-slate-400 bg-slate-800/40 border-slate-600/30`)

### 2.2 视觉与微交互规范 (SSDS/v1)
1. **暗夜毛玻璃卡片**：`backdrop-blur-md bg-slate-900/70 border border-slate-700/60 rounded-xl hover:border-cyan-500/50 transition-all`；
2. **流光骨架屏**：当 `isLoading` 为 true 时，渲染 9 个具有脉冲流光效果的 `<SkeletonCard />`，彻底杜绝布局跳变；
3. **详情折叠与证据路径**：支持点击卡片展开详情，清晰展示 `evidencePath`、`exitCode` 与详细判定日志；
4. **即时反馈与主动刷新**：点击「立即重新巡检」按钮，调用 `refetch()` 并通过 `useToast` 弹出「门禁全量巡检完成」提示。

## 3. 验收标准与测试
- 编写完整的 Vitest 单元测试 `GatesMatrixView.test.tsx`；
- 验证卡片渲染、状态筛选、骨架屏状态以及展开收起交互；
- `cd projects/cockpit-ui && bun run test:unit src/views/panorama/__tests__/GatesMatrixView.test.tsx` 全部 PASS。
