# LAYER-INDEX.md — 项目分层索引

> 基于 5+3+1 (eCOS v5) 架构
> 更新: 2026-06-06 | kairon 30 包 · shared-lib 拆出 5 子包 · 对齐架构文档

## I0 — 集成织层 MCP Hub

| 项目 | 角色 | 端口 | 状态 |
|------|------|------|------|
| **agora** | MCP 服务发现 + 代理 + 断路器 | 7430 (HTTP), 7431 (SSE) | 🟢 运行中 · 41 MCP 工具 |

> **当前在 kairon/packages/agora/ 下**，计划拆为独立 `projects/agora/`（架构最优先项）。

## L0 — 协议编织 + 基础依赖

| 项目/包 | 位置 | 说明 |
|---------|------|------|
| **protocols/** | `protocols/` | 16 协议 YAML 注册表（L0 协议定义） |
| **ecos** | `projects/ecos/` | SSB 协议 + 涌现计算（已拆出） |
| kairon-lib-events | `packages/kairon-lib-events/` | 事件总线模型 (BOSEvent, EventBusProtocol) — 从 shared-lib 拆出 |
| kairon-utils | `packages/kairon-utils/` | 通用工具库 (日志/重试/限流/错误/SQLite) — 从 shared-lib 拆出 |
| kairon-plugin-sdk | `packages/kairon-plugin-sdk/` | 插件 SDK (BosPlugin, PluginContext) — 从 shared-lib 拆出 |
| kairon-observability | `packages/kairon-observability/` | 可观测性套件 (指标/告警/异常/SLO) — 从 shared-lib 拆出 |
| kairon-pipeline | `packages/kairon-pipeline/` | D-Harvest 数据管道 (数据源/提取器/质量门) — 从 shared-lib 拆出 |

## L1 — 运行时基础设施

| 项目 | 位置 | 说明 | 状态 |
|------|------|------|------|
| **runtime** | `projects/runtime/` | Matrix 注册表、健康监控、KEI 沙箱 | 🟢 3.7K |
| **cron-service** | kairon `packages/cron-service/` | 定时任务调度 | 🟡 待迁移 → L1 |
| **agent-runtime** | kairon `packages/agent-runtime/` | Agent 执行引擎 | 🔴 待拆分 → L1+L3 |
| **engine-core** | kairon `packages/engine-core/` | EventBus 核心 + 生命周期事件 | 🟡 事件→L1, 存储→L2 |

## L2 — 内核三平面

### L2a · 治理面 OMO

| 项目 | 位置 | 说明 |
|------|------|------|
| **omo** | `projects/omo/` | Phase 目标管理、债务追踪、状态管理 (15K) |
| kairon-governance | kairon `packages/` (governance 模块在 shared-lib 内) | 审批路由、投票、RBAC · 🟡 待合并至 omo |

### L2b · 引擎面 kairon (知识工程流水线, 14 核心包)

| 包 | 工具数 | 代码量 | 说明 |
|----|--------|--------|------|
| eidos | 7 MCP | 35K | 知识类型验证 · 被 5 包引用 |
| kos | 26 MCP | 14K | KOS 搜索索引 · 被 4 包引用 |
| minerva | 5 super-tools | 25K | 深度研究 · 被 3 包引用 |
| ontoderive | 5 tools | 6K | 本体推导 (含 1,920 推导日志) |
| sophia | 8 tools | 1.4K | 范式编译 |
| kronos | 9 tools | — | 知识摄取 |
| iris | 8 tools | — | 数据源连接器 |
| ssot | 6 tools | 14K | 单一事实源 |
| forge | 70 tools | 8K | 工具注册 (JSON 注册表) |
| codeanalyze | 多种 | — | 代码分析 |
| core-models | — | 1.6K | 核心数据模型 (依赖基座, 8 包引用) |
| llm-gateway | — | 3K | LLM 路由 + 提供者抽象 |
| sharedbrain-bridge | — | — | SharedBrain 桥接 (EU/免疫/同步) |
| symphony-protocol | — | 1K | 通信协议 |

### L2c · 引擎面 kairon (支撑基础设施)

| 包 | 说明 |
|----|------|
| shared-lib | core/governance/cognitive/audit 业务模块 (5 子包已拆出至 L0) |
| engine-core | EventBus 核心、生命周期事件 (部分→L1) |
| health-profile | 健康档案 |
| llm-gateway-kernel | LLM 网关内核 |
| sot-bridge | 桥接层 |

### L2 独立

| 项目 | 位置 | 说明 |
|------|------|------|
| **metaos** | `projects/metaos/` | 编排引擎 · 已拆出 (7.8K) |
| **gbrain** | `projects/gbrain/` | TypeScript 知识数据库 · 67 MCP 工具 (163K TS) |

## L3 — 统一入口

| 项目 | 位置 | 说明 | 状态 |
|------|------|------|------|
| **cockpit** | `projects/cockpit/` | 统一 CLI + Web 面板 | 🟡 收并 wksp + hermes-console |
| wksp | kairon (已拆出) | CLI 工具 · 15K → 移至 cockpit | ⚪ |

## L4 — 自我层

| 项目 | 位置 | 说明 |
|------|------|------|
| **CARDS** | `~/Documents/驾驶舱/CARDS/` | SQLite 追踪系统 |
| **Vault** | `~/Documents/学习进化/` | Markdown 知识库 |

## X1-X3 横向切面

| 切面 | 核心模块 | 实现位置 | 状态 |
|------|---------|---------|------|
| **X1 审计链** | KEI 沙箱审计闭环 | `projects/runtime/kei_sandbox.py` | 🟡 基础框架, 告警回路待建 |
| **X2 抗熵** | 服务保鲜 + autoheal | `projects/runtime/scheduler.py` | 🟡 基础框架 |
| **X3 价值栈** | LLM 成本追踪 | llm-gateway `record_llm_cost()` | 🟡 记录点存在, 无汇总 |

## 已归档包

| 包 | 归档时间 | 原因 |
|----|---------|------|
| kairon-assistant | P28-W2 2026-06-05 | 0 外部 import, whisper 缺依赖 |
| kairon-voice | P28-W2 2026-06-05 | 0 外部 import, 自包含 |
| kaironcloud-billing | P28-W6 2026-06-05 | 1 软依赖 (agora try/except) |
| ecos | P31-W0 2026-06-06 | SSB 协议·拆为 `projects/ecos/` |
| metaos | P30-W1 2026-06-06 | 编排引擎·拆为 `projects/metaos/` |
| wksp | P30-W1 2026-06-06 | CLI入口·拆为 `projects/cockpit/` |
| pontus | — | 空壳包 |
| agent-hub | — | 已废弃 |
| gc-engine | — | 空壳包 |

## 实施路线 (优先级)

| 步骤 | 操作 | 收益 | 状态 |
|------|------|------|------|
| M0 已做完 | shared-lib 拆出 5 子包 → L0 | 降低耦合, 独立演进 | ✅ |
| M3 已做完 | metaos + ecos + wksp 搬家 | 自包含包独立 | ✅ |
| M1 | agora 拆出为 I0 独立项目 | 消除最大架构偏差 | 🔴 待做 |
| M2 | cron-service + agent-runtime 拆分 | L1 基础设施完整 | 🟡 待做 |
| M4 | kairon-governance → omo | 治理功能统一 | 🟢 低风险 |
| 其他 | LAYER-INDEX 更新, 包数对齐 | 基准正确 | ✅ P0 |
