# 全生命周期模型驱动平台 — 架构设计

> 基于 MOF 本体论正交分解 + SSOT 化，对系统全生命周期所有要素建模
> 日期: 2026-06-09 | 版本: 1.0.0

## 一、背景

### 1.1 现有体系

eCOS v5 已建立完整的 7 层架构 (L0-L4 + I0 + X1-X4):
- **L0 (ecos)**: MOF 元模型体系 (M3→M2→M1→M0) + SSB 协议 + 涌现计算
- **L1 (runtime)**: 运行时矩阵 + 调度器 + KEI 沙箱
- **I0 (agora)**: MCP Hub 服务网格 + 动态反向代理
- **L2 (kairon/omo/metaos/gbrain)**: 知识引擎 + 治理面 + 编排引擎 + 知识数据库
- **L3 (cockpit)**: 统一入口 CLI + Web
- **L4 (l4-kernel)**: 自我层管理面 + 21 域管理
- **X1-X4**: 治理维度

### 1.2 缺口

- MOF 仅覆盖"是什么"和"怎么管"，缺少"全生命周期阶段"建模
- M2 类型偏技术架构，缺少业务/价值/过程类型
- 模型驱动工具分散在多个项目中
- SSOT 未贯穿全生命周期
- 缺少统一的过程建模能力

## 二、四层架构

```
┌─────────────────────────────────────────────────────┐
│              管理面 (Management Plane)                │
│  SPEC + ADR + OKR + OMO 桥接 + 多Agent 协作          │
├─────────────────────────────────────────────────────┤
│              模型面 (Model Plane)                     │
│  统一 MOF 元模型 (M3→M2→M1→M0)                       │
│  系统模型 + 业务模型 + 过程模型 + 价值模型              │
├─────────────────────────────────────────────────────┤
│              生命周期面 (Lifecycle Plane)              │
│  规划→设计→开发→部署→运行→运维→运营                     │
├─────────────────────────────────────────────────────┤
│              工具面 (Tool Plane)                      │
│  Design│Generate│Derive│Validate│Connect│Compile      │
│  Evolve│Monitor│Deploy│Observe│Report│Archive         │
└─────────────────────────────────────────────────────┘
```

## 三、核心模块

### 3.1 MOF 扩展 (mof/)

**M3 扩展:**
- LifecycleElement (Stage, Gate, Transition)
- ValueElement (Goal, KeyResult, CostModel, BenefitModel)
- 7 个标准阶段定义 + 4 个标准门禁

**M2 扩展 (24 新类型):**
- 规划态: roadmap, okr, initiative
- 设计态: adr, spec_design, interface_contract
- 开发态: code_module, test_suite, ci_pipeline
- 部署态: deployment_config, release_plan, environment
- 运行态: runbook, alert_rule, dashboard_config
- 运维态: incident, change_request, migration_plan
- 运营态: user_journey, value_stream, feedback
- 价值体系: cost_model, benefit_model, roi_analysis

### 3.2 生命周期引擎 (lifecycle/)

- **stages.py**: StageStatus/StageInstance/LifecycleTracker — 阶段状态机和实体追踪
- **gates.py**: GateEngine/GateResult/CheckResult — 门禁检查引擎 (8 种检查类型)
- **transitions.py**: TransitionEngine/TransitionRule — 6 条标准转换规则
- **tracking.py**: LifecycleManager/LifecycleDashboard — 多实体管理和仪表板

### 3.3 模型驱动工具链 (toolchain/)

- **bus.py**: ToolchainBus — 工具注册/路由/执行/统计
- **tools.py**: 12 个核心工具 (design/generate/derive/validate/connect/compile/evolve/monitor/deploy/observe/report/archive)

### 3.4 管理面 (management/)

- **spec.py**: Spec/SpecManager — 规格驱动 (7 状态)
- **adr.py**: ADR/ADRManager — 架构决策记录 (6 状态)
- **okr.py**: OKR/OKRManager — 目标对齐 (5 状态 + 进度计算)
- **omo_bridge.py**: OMOBridge — OMO 治理桥接 (事件/债务/任务/审计)
- **agent_collab.py**: AgentCollabManager — 多Agent 协作 (6 状态 + 冲突检测)

### 3.5 SSOT 全生命周期化 (ssot/)

- **lifecycle_ssot.py**: LifecycleSSOT/ValueSSOT/ProcessSSOT/CrossStageConsistencyChecker

## 四、接口

### CLI (6 子命令)
```
model-driven lifecycle <create|advance|status|dashboard|blockers>
model-driven spec <create|list>
model-driven adr <create|list>
model-driven okr <create|list|progress>
model-driven tool <list|execute>
model-driven mcp <list|execute>
```

### MCP Server (25 工具)
- lifecycle: 5 工具 (create/advance/status/dashboard/blockers)
- spec: 2 工具 (create/list)
- adr: 2 工具 (create/list)
- okr: 2 工具 (create/progress)
- omo: 3 工具 (debt-register/task-create/audit-record)
- collab: 3 工具 (collab-create/collab-assign/collab-status)
- toolchain: 2 工具 (model-execute/model-tools)
- ssot: 3 工具 (ssot-drift-check/cross-stage-check/value-roi)

## 五、测试

- 120 tests, 全通过
- 覆盖: M3 扩展(16) + M2 扩展(17) + 生命周期(30) + 管理面(27) + SSOT(11) + 工具链(19)
