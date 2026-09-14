---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet: BET-Y1Q4-T8-19
title: Web UI (cockpit-ui) 8 大正交一级领域重组与包体瘦身
symptom: 旧版 cockpit-ui 42 个散乱路由缺乏清晰信息架构，静态 import 导致首页 Bundle >1MB 超大告警，无头测试环境出现 React Lazy 接收到 undefined 抛错
solution: 基于 8 大正交一级领域重构路由拓扑与 SurfaceDomainType 映射，采用 React.lazy() 路由级代码分割与 Vite manualChunks 细粒度分包，将主入口包体从 1,052 KB 压降至 65 KB，修复 GBrain 组件 default export
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-19 复盘

## 做对了什么

1. **8 大正交一级领域重塑信息架构**：在 `projects/cockpit-ui/src/routes.tsx` 中完整映射 Overview、Execution、Swarm、Compute、Memory、Registry、Security、System 八大核心领域，引入 `SurfaceDomainType` 类型安全契约与 `getRoutesByDomain` 拓扑查询方法。
2. **包体断崖式瘦身（1,052 KB → 65 KB）**：排查发现 `ChainStudio`（含 reactflow 300KB+）与 `AuditDashboard`/`BcosDashboard`（含 recharts 400KB+）此前被静态导入打包进入口 chunk。将其转为 `React.lazy()` 配合 `vite.config.ts` 的 `manualChunks`（`vendor-react`, `vendor-charts`, `vendor-flow`, `vendor-icons`, `vendor-query`），首页 chunk 从 1,052 KB 锐减至 65 KB，彻底消除 Vite 构建大包告警。
3. **修复无头测试环境 React Lazy 渲染异常**：定位并修复 `GBrainDashboard.tsx` 缺少 `default export` 导致的无头测试 DOM 模拟器拦截报错，确保 70 个测试套件 669 项单元/集成测试 100% 绿灯通过。

## 踩了什么坑

| 坑 | 修复 |
|---|---|
| 静态 import 重型依赖库（reactflow/recharts）导致首页 chunk 超过 1MB 告警 | 统一路由级 `React.lazy()` 动态加载与 Vite `manualChunks` 细粒度拆包 |
| `GBrainDashboard.tsx` 仅具名导出 `DashboardPage`，动态引入时引发 `Element type is invalid: Received a promise that resolves to: undefined` | 在 `GBrainDashboard.tsx` 末尾追加 `export default DashboardPage;`，根除 lazy 加载失败 |
| 并发 commit 合入 `WorkCasesPage` 导致 routes.tsx 冲突 | 基于最新 origin/main 进行 rebase，保留并将其无缝接入 Execution 业务域 |

## 交付自证

- 构建验证：`cd projects/cockpit-ui && bun run build` (无任何 Chunk 警告，首页 Chunk 仅 65 KB)
- 测试套件：`cd projects/cockpit-ui && bun run test:unit` (70 passed, 669 passed)
- 门禁状态：通过 `agent-workflow` 闭环校验与本地 GaC 门禁。
