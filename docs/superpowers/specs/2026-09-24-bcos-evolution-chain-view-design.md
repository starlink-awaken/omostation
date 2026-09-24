---
schema_version: specification/v1
spec_version: 1.0.0
title: BCOS 主权进化链与学习图谱组件研发 (BcosEvolutionChainView)
bet_id: BET-Y2Q2-T7-09
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-24'
last-reviewed: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
type: ssot
---

# BCOS 主权进化链与学习图谱组件研发 (BcosEvolutionChainView) 设计规约

## 1. 目标与背景

BCOS（Blockchain-inspired Cognitive Operating System）是系统知识结晶、踩坑信念萃取与自进化的核心驱动力。旧体系中 BCOS 指标缺乏直观的进化时间轴大屏。
本规约设计现代化的 `<BcosEvolutionChainView />` 组件，呈现系统记忆自蒸馏、学习率与历史进化里程碑时间轴。

## 2. 核心架构与功能需求

### 2.1 状态接入
- 消费 `useBcosEvolution()`（来自 `useGovernancePanorama`）；
- 获取当前进化轮次 `epoch`、自蒸馏记忆条目数 `selfDistillationCount`、学习健康度 `healthScore` 与历史记录 `recentRecords`。

### 2.2 视觉与呈现规范 (SSDS/v1)
1. **进化态势大屏仪表卡片**：
   - 当前进化世代（如 `Epoch 24`，大字号晶体展示）；
   - 自蒸馏知识单元数（`142+`）；
   - 认知自愈指数（`98.7%`）；
2. **历史进化里程碑时间轴 (Evolution Timeline)**：
   - 垂直卡片时间轴，展示最近几代进化的摘要、影响范围（Impact Scope）与时戳；
   - 世代标识 Badge（如 `Epoch 24` 翠绿、`Epoch 23` 晶蓝）；
3. **即时交互与刷新**：
   - 提供「刷新进化图谱」按钮，支持调用 `refetch()` 并通过 `useToast` 反馈。

## 3. 验收标准与测试
- 编写完整的 Vitest 单元测试 `BcosEvolutionChainView.test.tsx`；
- 验证世代卡片、时间轴记录渲染以及一键刷新交互；
- `bun run test:unit src/views/panorama/__tests__/BcosEvolutionChainView.test.tsx` 全部 PASS。
