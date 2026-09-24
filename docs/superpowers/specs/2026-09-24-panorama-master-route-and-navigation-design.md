---
schema_version: specification/v1
spec_version: 1.0.0
title: Cockpit-UI 体系全景主航道路由与侧边栏首要导航装配
bet_id: BET-Y2Q2-T10-162
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

# Cockpit-UI 体系全景主航道路由与侧边栏首要导航装配设计规约

## 1. 目标与背景

随着 M2 里程碑四大核心治理资产（门禁、哨兵、架构拓扑、BCOS 进化链）React 模块化研发完毕，本 BET 负责建立统一的容器组件 `<PanoramaMasterView />`，挂载顶层路由 `/panorama`，在侧边栏主航道最核心位置挂载入口，并在 ⌘K 命令面板中注册索引，实现真正的单一人类总控入口。

## 2. 核心架构与功能需求

### 2.1 容器组件设计 (`PanoramaMasterView.tsx`)
1. **四大选项卡 (Tab Control)**：
   - `gates`：门禁全景矩阵 (`<GatesMatrixView />`)
   - `guardian`：74s 哨兵大屏 (`<GuardianInspectionWallboard />`)
   - `topology`：道法术器架构拓扑 (`<SystemTopologyWallboard />`)
   - `bcos`：BCOS 主权进化链 (`<BcosEvolutionChainView />`)
2. **顶层全景姿态条 (Overview Summary Bar)**：
   - 呈现全景健康总分、74s 倒计时、门禁通过比例与活跃 S-Slot；
   - 支持 Tab 快捷切换与 URL query 参数同步（如 `?tab=guardian`）。

### 2.2 路由与导航系统集成
1. **路由定义**：在 `App.tsx` 中定义 `/panorama` 路由，指向 `<PanoramaMasterView />`；
2. **侧边栏挂载**：在 `AppLayout.tsx` 侧边栏主航道中增加「🌌 体系全景」导航项；
3. **全局命令面板**：在 `CommandPalette.tsx` 中添加“切换至体系全景大屏”快捷指令。

## 3. 验收标准与测试
- 编写完整的 Vitest 单元测试 `PanoramaMasterView.test.tsx`；
- 验证四大 Tab 无缝切换、URL query 同步以及各子大屏组件正常装配；
- `bun run test:unit src/views/panorama/__tests__/PanoramaMasterView.test.tsx` 全部 PASS。
