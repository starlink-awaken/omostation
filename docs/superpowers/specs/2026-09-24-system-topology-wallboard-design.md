---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 道法术器架构拓扑大屏研发 (SystemTopologyWallboard)
bet_id: BET-Y2Q2-T7-08
created: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# 道法术器架构拓扑大屏研发 (SystemTopologyWallboard) 设计规约

## 1. 目标与背景

在旧版 `:43191` 底座中，道法术器拓扑依赖单体 HTML 中拼接的 500 行硬编码静态 SVG，交互僵硬、无法适配移动/响应式布局。
本规约设计现代化的 React 19 组件 `<SystemTopologyWallboard />`，以现代卡片流与层次结构清晰呈现「道、法、术、器」四大系统层级与唯一合规 Active S-Slot (`COMP-WS-omo`)。

## 2. 核心架构与功能需求

### 2.1 状态接入
- 消费 `useSystemTopology()`（来自 `useGovernancePanorama`）；
- 获取各层级（Dao、Fa、Shu、Qi）及其包含的核心服务节点、当前运行健康状态。

### 2.2 视觉与拓扑呈现 (SSDS/v1)
1. **层次化四层阶梯卡片**：
   - **道 (Dao) — 意志与意图**：Intent Compiler, Master 3Y Bet Ledger (紫青意图质感)
   - **法 (Fa) — 契约与门禁**：Harness 8-Stage DAG, GaC CI 门禁引擎 (金黄规范质感)
   - **术 (Shu) — 编排与协同**：Agent Workflow, A2A Broker, Swarm 协作网 (晶蓝流动质感)
   - **器 (Qi) — 工具与具身**：Cockpit-UI, Local Edge Compute, AetherForge (墨绿具身质感)
2. **唯一合规 Active S-Slot 展示**：
   - 高亮突出 `COMP-WS-omo` 调度槽位，明确其为唯一合法中枢；
3. **节点交互与下钻**：
   - 鼠标悬停高亮关联上下游；
   - 支持各层级展开/收起；
   - 提供流光骨架屏加载态。

## 3. 验收标准与测试
- 编写完整的 Vitest 单元测试 `SystemTopologyWallboard.test.tsx`；
- 验证四大层级渲染、节点计数、S 槽位状态以及节点展开折叠；
- `bun run test:unit src/views/panorama/__tests__/SystemTopologyWallboard.test.tsx` 全部 PASS。
