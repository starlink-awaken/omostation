---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T8-19
risk_level: L1
human_gate: false
value_indicator_policy: false
implementation_authorized: true
type: ssot
---

# Web UI (cockpit-ui) 8 大正交一级领域重组与包体瘦身设计规约

## 1. 目标与背景

当前 `cockpit-ui` (React 19 + Vite 8) 随着平台功能高速演进，面临两大核心痛点：
1. **信息架构散乱与表面协议割裂**：侧边栏累积了 42+ 个未分层路由，认知负荷沉重；与此前在 USP v1 (`SurfaceDomain`) 及 Sovereign TUI 2.0 中确立的 8 大正交一级领域（Overview, Execution, Swarm, Compute, Memory, Registry, Security, System）缺乏对齐。
2. **包体臃肿与 Chunk 报警**：未充分实施路由级 Code-Splitting 与精细化依赖分包，生产构建产物中单个主 Chunk (`index.js`) 超过 **1,052 KB**，严重触发 Vite/Rollup `>500 KB` 告警。

本规约旨在：
- 在 `src/routes.tsx` 中将全部视图归纳至 8 大正交一级领域，建立清晰的主从导航体系；
- 在 `vite.config.ts` 引入 `rollupOptions.output.manualChunks` 与路由级懒加载拆分，将核心 Chunk 压降至 `<300 KB`，消除所有构建警告；
- 保持 69 个现有测试套件 100% 绿灯通过。

---

## 2. 8 大正交一级领域路由映射

| 一级正交领域 (Domain) | 包含视图与业务功能 (Views) | 图标/语义 |
|---|---|---|
| **1. Overview (总览驾驶舱)** | `OverviewPage`, `Dashboard`, `Wave2DashboardView`, `CockpitGuideView` | 核心 KPI、大盘概览与向导 |
| **2. Execution (执行与旅程)** | `JourneysTimelineView`, `DeliveryJourneyView`, `WorkflowsView`, `HarnessDashboard`, `EcosWorkflowWorkbench`, `IntentCompiler` | 价值循环、交付旅程与工作流 |
| **3. Swarm (智能体蜂群)** | `SwarmDashboard`, `BrainChat`, `TaskCenterPage`, `QuestBoard`, `SceneCardReviewView` | 多智能体集群、任务中心与场景卡 |
| **4. Compute (算力与引擎)** | `ComputeView`, `RuntimeOpsWorkbench`, `InfrastructureOpsWorkbench`, `EnginesView`, `McpMeshView` | 异构算力织网、L4/BOS 运行时与 MCP |
| **5. Memory (记忆与认知)** | `DigitalBrainWorkplaceView`, `MemoryInjector`, `GBrainDashboard`, `OutcomesView`, `DecisionInboxView` | 向量大脑、经验记忆、决策收件箱 |
| **6. Registry (注册中心与资产)** | `DomainAppsView`, `CapabilityExplorer`, `AssetsView`, `ExternalResourceCatalogView`, `ProtocolWorkbenchView` | 域应用、能力地图、协议资产编目 |
| **7. Security (安全与治理)** | `GovernanceDomainWorkbench`, `C2GStrategyView`, `PlatformControlWorkbench`, `SystemAssuranceWorkbench`, `DebtView`, `AlertCenterPage` | GaC 门禁、合规大盘、技术债务与告警 |
| **8. System (系统与观测)** | `ObservabilityView`, `PerformanceMonitorPage`, `TopologyView`, `SystemMapView`, `L4HealthView`, `LogViewerPage`, `SettingsView` | 可观测性仪表盘、系统拓扑、日志与设置 |

---

## 3. 产物体积优化与分包策略 (Vite Chunk Splitting)

在 `vite.config.ts` 中配置细粒度 `manualChunks`：
1. `vendor-react`: `react`, `react-dom`, `react-router-dom`
2. `vendor-charts`: `recharts`
3. `vendor-flow`: `reactflow`
4. `vendor-icons`: `lucide-react`
5. `vendor-query`: `@tanstack/react-query`, `zustand`

通过将大型第三方库隔离到专属稳定缓存 Chunk，并确保路由组件采用 `React.lazy()` 懒加载，使得首页核心 Chunk 压降至 300KB 以下。

---

## 4. 验收与自证契约

1. 构建验证：`cd projects/cockpit-ui && bun run build` 成功（exit 0），且无任何 `>500 KB` chunk 告警。
2. 单元测试：`cd projects/cockpit-ui && bun run test:unit` 69 个测试套件全绿通过。
3. 门禁验证：主仓 `make gac-local-gate` 56 项全绿通过。
