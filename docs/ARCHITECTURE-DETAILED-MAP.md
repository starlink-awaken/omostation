# omostation 全量架构功能地图 (细化版)

> **SSOT**: 本文档是 omostation 系统架构、模块依赖、内部功能、数据流/控制流/逻辑流的唯一全景地图
> **更新**: 2026-06-28 | **范围**: 17 项目 (5+4+1+1 架构) | **方法**: 3 组 subagent 并行深挖
> **前置**: `docs/FUNCTIONAL-CAPABILITY-MAP.md` (功能能力地图), 本文档是其架构细化

> **配套文档**: `docs/FUNCTIONAL-CAPABILITY-MAP.md` (聚焦 WHAT: 8 域 32 能力, CLI/MCP/HTTP 入口矩阵)

---

## 目录

1. [整体架构层次](#1-整体架构层次)
2. [模块依赖矩阵](#2-模块依赖矩阵)
3. [各项目内部模块架构](#3-各项目内部模块架构)
4. [数据流 (Data Flow)](#4-数据流-data-flow)
5. [控制流 (Control Flow)](#5-控制流-control-flow)
6. [逻辑流 (Logic Flow)](#6-逻辑流-logic-flow)
7. [架构模式总结](#7-架构模式总结)

---

## 1. 整体架构层次

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    L4 自我层 (l4-kernel)                        │
                    │           域注册 · KEMS 六面 · MCP tools · 信号总线 (见 project-registry.yaml)         │
                    └──────────────────────────────┬──────────────────────────────────┘
                                                   │
                    ┌──────────────────────────────┴──────────────────────────────────┐
                    │                    L3 入口层 (cockpit + mounted cockpit-ui)      │
                    │    CLI 子命令 · Web · MCP tools (见 project-registry.yaml: cockpit)         │
                    │    cockpit-ui 视图组件 (Vite/React)                          │
                    └──────────┬───────────────────────────────────┬──────────────────┘
                               │                                   │
                    ┌──────────▼──────────┐          ┌────────────▼──────────────────┐
                    │  I0 织层 (agora)     │          │  X 横切框架                    │
                    │  MCP Hub (见 project-registry.yaml: agora)    │          │  model-driven (M0): 7阶段+门禁 │
                    │  BOS URI 服务 (见 project-registry.yaml: bos)     │          │  bus-foundation: Omni-Bus 三平面│
                    │  A2A · 联邦 · 代理    │          │  aetherforge: LLM网关+网格+蜂群 │
                    │  限流/熔断/缓存       │          │  c2g: 战略需求引擎              │
                    └──┬──────┬──────┬─────┘          │  omo-debt: 债务评分             │
                       │      │      │                │  observability: Langfuse        │
         ┌─────────────┘      │      └────────────┐  │  family-hub: 家庭枢纽           │
         │                    │                    │  └─────────────────────────────────┘
         │                    │                    │
┌────────▼─────────┐ ┌───────▼────────┐ ┌────────▼─────────┐
│  L2 知识引擎      │ │  L2 治理面     │ │  L2 编排引擎      │
│  kairon (见 project-registry.yaml: kairon.packages)   │ │  omo (见 project-registry.yaml: omo.src_files) │ │  metaos          │
│  gbrain (70 ops)  │ │  治理/任务/债务  │ │  门控/DAG/免疫    │
│  搜索/摄取/推导    │ │  自愈/GaC      │ │  认知框架         │
└────────┬─────────┘ └────────┬───────┘ └────────┬────────┘
         │                    │                    │
         └──────────┬─────────┴────────────────────┘
                    │
         ┌──────────▼──────────┐
         │  L1 运行时 (runtime)  │
         │  Matrix · KEI 沙箱    │
         │  Cron · Executor 80+  │
         │  Bus Consumer         │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │  L0 协议层 (ecos)     │
         │  MOF M3→M2→M1        │
         │  SSB 签名链           │
         │  M1 节点 (见 project-registry.yaml: m1_yaml)         │
         │  mof-* 工具 (见 project-registry.yaml: ecos.mof_tools)        │
         │  workflow 引擎        │
         └─────────────────────┘
```

### 5+4+1+1 架构分层

> 能力入口矩阵 (谁提供什么 CLI/MCP/HTTP): 见 [`FUNCTIONAL-CAPABILITY-MAP.md` §1-8](./FUNCTIONAL-CAPABILITY-MAP.md#1-知识摄取与持久化-knowledge-ingestion)

| 层 | 项目 | 核心职责 |
|:--:|------|---------|
| **L4** | l4-kernel | 自我层管理面: 域注册 (见 project-registry.yaml: l4-kernel.domains), KEMS 六面, 健康聚合, 信号总线 |
| **L3** | cockpit | 统一入口: CLI + Web + MCP, 唯一人类入口 (cockpit-ui 挂载至 cockpit, layer=X) |
| **I0** | agora | 织层: MCP Hub, BOS URI 路由, A2A, 联邦, 限流/熔断/缓存 |
| **L2** | kairon, gbrain, omo, metaos | 引擎面: 知识/治理/编排 |
| **L1** | runtime | 运行时: Matrix, KEI 沙箱, Cron, Executor |
| **L0** | ecos | 协议层: MOF 元模型, SSB 签名链, BOS URI 声明, workflow |
| **M0** | model-driven | 横切: 7 阶段生命周期引擎, 4 门禁, 3 PipelinePhase |
| **X** | aetherforge, bus-foundation, c2g, omo-debt, observability, family-hub | 横切: 算力/事件总线/需求/债务/可观测/家庭 |

---

## 2. 模块依赖矩阵

### 2.1 Python import 依赖 (17x17)

> `X` = 直接 Python import 依赖; `B` = 仅 BOS URI 运行时依赖; `·` = 无依赖

| ↓ 依赖方 \ 被依赖方 → | aeth | agora | bus | c2g | cock | ecos | fam | gbrain | kairon | l4 | metaos | model | omo | omo-debt | runtime |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **aetherforge** | — | · | X | · | · | · | · | · | · | · | · | · | · | · | · |
| **agora** | · | — | X | · | · | X | · | · | · | · | X | · | · | · | · |
| **bus-foundation** | · | · | — | · | · | · | · | · | · | · | · | · | · | · | · |
| **c2g** | · | · | · | — | · | · | · | · | · | · | · | · | · | · | · |
| **cockpit** | · | X | · | · | — | · | · | · | · | X | · | · | X | · | X |
| **ecos** | · | · | · | · | · | — | · | · | B | · | B | · | X | · | B |
| **family-hub** | · | · | · | · | · | · | — | · | · | · | · | · | · | · | · |
| **gbrain** | · | · | · | · | · | · | · | — | · | · | · | · | · | · | · |
| **kairon** | · | · | X | · | · | · | · | · | — | · | · | · | · | · | · |
| **l4-kernel** | · | · | X | · | · | · | · | · | · | — | · | X | · | · | · |
| **metaos** | · | X | X | · | · | · | · | · | · | X | — | · | · | · | · |
| **model-driven** | · | · | · | · | · | · | · | · | · | · | · | — | · | · | · |
| **omo** | X | X | X | · | · | · | · | · | · | · | · | X | — | · | · |
| **omo-debt** | · | · | · | · | · | · | · | · | · | · | · | · | · | — | · |
| **runtime** | X | X | X | · | · | · | · | · | · | · | · | · | X | · | — |

### 2.2 依赖层次分析

```
                cockpit (L3, 顶层)
               /    |    \    \
           agora  l4-k  omo  runtime (L2/I0/L1, 中层)
          / | \    | \    | \    |
       bus ecos model  bus  aether (L0/X, 基础层)
        |   |         |
     (leaf) omo→ecos  (leaf: model-driven, bus-foundation)
```

**关键发现**:
1. **bus-foundation** 是被依赖最多的项目 (7 个直接 import), 真正的基础设施
2. **agora** 是运行时枢纽 (4 个 import 依赖 + 所有 BOS URI 经它路由)
3. **omo** 被 cockpit/ecos/runtime 依赖, 是治理内核
4. **model-driven** 是零依赖叶子, 被 l4-kernel 和 omo 依赖
5. **ecos→omo** 是唯一的 L0→L2 向上依赖 (mof-state-bridge, 已记录为例外)
6. **零依赖叶子**: bus-foundation, c2g, family-hub, model-driven, omo-debt, observability

### 2.3 BOS URI 运行时调用图

| 调用方 → 被调方 | BOS URI | 说明 |
|:---|:---|:---|
| cockpit → agora | `resolve_bos_uri()` | 所有 URI 经 agora 路由 |
| cockpit → family-hub | `bos://persona/family-hub/health` | 家庭健康检查 |
| cockpit → kos | `bos://memory/local/all-search` | 全域搜索 |
| cockpit → omo | `bos://governance/cockpit/*` | 治理操作 |
| ecos → minerva | `bos://analysis/minerva/research` | 深度研究 |
| ecos → kos | `bos://memory/kos/search` | 知识搜索 |
| ecos → codeanalyze | `bos://analysis/codeanalyze/scan` | 代码分析 |
| ecos → omo | `bos://governance/omo/audit` | 审计 |
| ecos → metaos | `bos://governance/metaos/gate` | 决策门控 |
| ecos → runtime | `bos://capability/agent-runtime/*` | Agent 执行 |
| omo → agora | `resolve_bos_uri()` | 经连接池 |
| runtime → agora | SSE 消费 | 事件流 |

---

## 3. 各项目内部模块架构

### 3.1 omo — 治理内核 (见 project-registry.yaml: omo.src_files)

| 模块组 | 文件数 | 职责 | 核心数据结构 |
|--------|:------:|------|-------------|
| 入口 | 2 | CLI 39 子命令 + MCP 19 tools | — |
| I/O SSOT | 3 | AppendOnlyLog + 原子写 + fcntl 锁 | `AppendOnlyLog`, `AdvisoryLock` |
| 债务管理 | 17 | registry/lifecycle/dispatch/execution/metrics/reporting/approval/campaign | `DebtItem` |
| 审计 | 4 | 审计+同步+去重+rollout | `AuditRecord` |
| BOS 服务 | 6 | BOS dispatch/metrics/schema/seeds | `BosService` |
| Worker 调度 | 6 | core/dispatch/promotion/status | `WorkerContract` |
| 治理面 | 19 | overlay/surfaces/state_plane/ingress/mutation | `GovernanceSurface` |
| Ingress | 9 | debt/doc/goal/registry/task (archive/contract/lifecycle/promotion) | `TaskMetadata` |
| Lint | 6 | lint/doc/god_module/mutation_ledger/schemas/yaml_bypass | `LintReport` |
| 自愈 | 3 | engine + fixes + trend | `HealingRule` |
| 桥接 | 4 | model-driven/agora/bus/cockpit | factory 模式 |
| 晋升 | 5 | approval/analytics/history/readiness/request | `PromotionRequest` |
| 演化循环 | 3 | evolution/weekly/release | — |

**状态管理**: YAML SSOT (`.omo/`) + JSONL (7 consumers 共享 AppendOnlyLog)

**内部调用链**:
```
cli.py governance → omo_governance_surfaces_report → 7 面检查 → score 100 A+
cli.py task → omo_ingress_task_lifecycle → write_yaml_atomic → .omo/tasks/
omo_audit/omo_event/omo_bos_metrics → AppendOnlyLog.append() → fcntl_lock → JSONL
```

### 3.2 ecos — 协议层 (MOF+SSB+workflow)

| 模块组 | 目录 | 职责 | 核心数据结构 |
|--------|------|------|-------------|
| SSOT (MOF) | `ssot/mof/` | M3→M2→M1 元模型层次 | MOF M3 (7 阶段), M2 (48 schema), M1 (见 project-registry.yaml: m1_yaml) |
| SSOT 注册表 | `ssot/registry/` | L0 约束 SSOT | `L0-constraints.yaml` (GaC 规则 (见 project-registry.yaml: gac.rules_count)) |
| SSOT 工具 | `ssot/tools/` (见 project-registry.yaml: ecos.mof_tools) | MOF 工具链 | validate/audit/derive/bridge-sync/state-bridge |
| Workflow | `workflow/` | M1 DSL → loader → validator → executor | `WorkflowEngine` |
| L0 核心 | `l0/` | SSB + emergence + governance | SSB 签名链 |
| Services | `services/` | 治理/集成/监控 | — |
| Common | `common/` (18 模块) | logger/exceptions/config/security/cache | — |

**状态管理**: YAML SSOT (M3/M2/M1 + 注册表) + SSB 签名链 (不可篡改)

### 3.3 kairon — 知识引擎 (见 project-registry.yaml: kairon.packages) monorepo

| 包 | 职责 | 依赖 |
|---|------|------|
| core-models | 共享数据模型 (Entity/Relation/Provenance) | (无) |
| kairon-utils | 通用工具 (logging/retry/rate-limit) | (无) |
| kairon-lib-events | 事件数据模型 | (无) |
| kairon-observability | OpenTelemetry + DeepEval | (无) |
| kairon-pipeline | D-Harvest 数据管线 | bus-foundation |
| kairon-plugin-sdk | 插件 SDK (BosPlugin 基类) | (无) |
| eidos | Schema 定义/校验/统一记忆 API | core-models |
| kos | 跨域搜索 (FTS5 + jieba) | eidos |
| minerva | 深度研究 (多源搜索 + 知识图谱) | kos, core-models, kairon-* |
| ontoderive | 渊衍框架 (事实驱动推导) | core-models, kairon-lib-events |
| kronos | 知识摄取管线 (5 层抓取) | core-models |
| codeanalyze | 代码分析 (AST/CRG) | eidos, core-models |
| iris | 平台连接器 (20+) | eidos, kronos, minerva |
| forge | 工具市场 | — |
| sophia | 范式编译器 | — |
| health-profile | 健康档案数据模型 | core-models |

### 3.4 runtime — 运行时 (executor 80+ 文件)

| 模块组 | 文件 | 职责 |
|--------|------|------|
| Matrix | `matrix.py` | 服务注册表 (`ServiceEntry`) |
| Scheduler | `scheduler.py` (19KB) | 15s 心跳 + auto-heal |
| Protocol | `protocol.py` | L0 协议注册 (`ProtocolEntry`, 7 类) |
| KEI 沙箱 | `kei*.py` (见源码) | `sys.addaudithook` FS mutation 拦截 |
| Cron Service | `cron_service/` (见源码) | FastAPI + SQLite 调度 |
| Executor 核心 | `engine.py` (19KB) | AgentRuntime (LLM→tools→result) |
| 编排 | `orchestrator.py` | DAG 8-Phase 编排 |
| DSL | `dsl*.py` (见源码) | YAML/JSON DSL 解析 |
| Swarm | `swarm*.py` | 蜂群协议 |
| ISC | `isc_*.py` (见源码) | Ideal State Criteria |
| 韧性 | `self_healing.py`, `guardian.py` | 自愈 + 守卫 |

### 3.5 agora — MCP Hub

| 模块组 | 目录 | 职责 |
|--------|------|------|
| MCP Server | `server/` (见源码) | 工具注册 + proxy + a2a (God Module 25KB) |
| BOS Resolver | `mcp/resolver/` (6 模块) | BOS URI 解析 (services 37KB) |
| Core | `core/` | ServiceRegistry + SmartRouter + CircuitBreaker |
| Proxy | `mcp_proxy/` (见源码) | Stdio/HTTP MCP 客户端代理 |
| Registry | `mcp_registry/` (7 模块) | 服务发现 + 生命周期 |
| Auth | `auth/` (见源码) | OAuth2/HMAC/Tenant/Ed25519 |
| Bus | `bus/` | Omni-Bus shim (→ bus-foundation) |
| A2A | `a2a/` | Agent-to-Agent 协议 |

### 3.6 cockpit — 统一入口

| 模块组 | 文件 | 职责 |
|--------|------|------|
| CLI | `cli.py` (35KB) | argparse 路由 (见 project-registry.yaml) |
| Commands | `commands/` (见源码) | 子命令实现 (research 57KB 最大) |
| Web API | `web/` (见源码) | FastAPI 路由 (agora/alerts/bos/ecos/health/...) |
| Dashboard | `dashboard/` | 数据聚合 + 路由 (constants 27KB) |
| Storage | `storage.py` + `storage_sqlite.py` | `IDataAccess` Protocol + SQLite 实现 |
| Agent Runtime | `agent_runtime_*.py` (见源码) | HTTP + MCP 桥接到 runtime |
| L4 Bridge | `l4bridge.py` (14KB) | L4 域桥接 |

### 3.7 其余项目 (简要)

| 项目 | 层 | 核心模块 | 职责 |
|------|:--:|---------|------|
| **bus-foundation** | X | `bus/` (Data/Event/Control 三平面) | Omni-Bus 基础设施: ring buffer (Data) + 扇出 (Event) + ACK/NACK+DLQ (Control). 零依赖叶子, 被 7 个项目 import |
| **c2g** | X | `brainstorm/` + `bet/` + `bridge_import.py` | 战略需求引擎: V2P (Voice to Pitch) → C2G (Challenge to Governance). IOC + 双适配器 (ecos/local) |
| **l4-kernel** | L4 | `registry.py` (见 project-registry.yaml: l4-kernel.domains) + `kems/` (六面) + `signal_bus.py` | 自我层管理面: 域注册 + KEMS 六面健康 + 信号总线 + MCP tools (见 project-registry.yaml) |
| **model-driven** | M0 | `mof/m3_extended.py` + `lifecycle/pipeline.py` + `trigger/` | 横切生命周期引擎: 7 阶段 + 4 门禁 + 3 PipelinePhase + 10 触发机制. 零依赖叶子 |
| **aetherforge** | X | `gateway/` + `mesh/` + `swarm/` | 算力框架: LLM 网关 (多 Provider 路由) + 算力网格 (节点池) + 蜂群 (GraphWorkflow DAG) |
| **family-hub** | X | `mcp_server.py` (FastMCP) | 家庭数字枢纽: 任务游戏化 + LLM 生成 + OMO 治理接入 (G2 修复) |
| **omo-debt** | X | `cli.py` + `scorer.py` | 技术债务评分 CLI: v2 生命周期感知 (Honestesty + Legacy 维度) |
| **observability** | X | Docker (Langfuse) | 可观测性: HTTP :3050, OTLP trace 采集 |
| **cockpit-ui** | X | Vite/React (24+ 视图) | Web 控制台: Dashboard/C2G/Compute/Assets/Mesh/Engines/L4Health/Task/Alert/Quest/Debt |
| **spaces** | — | YAML 配置 | 空间配置: 用户空间/租户空间 manifest 和所有权边界 |
| **protocols** | L0 | YAML (port-registry 等) | 协议注册: 端口/服务/协议声明式注册表 |

---

## 4. 数据流 (Data Flow)

### 4.1 URL → 知识库 (kronos → gbrain)

```
URL
 ↓ kronos fetch_router.py (5 层路由)
 │  L1: MCP 工具 → L2: Jina AI → L3: 缓存 → L4: CloakBrowser → L5: 手动
 ↓ HTML / raw text
 ↓ kronos extractor.py (Ollama LLM → 规则 → 默认 fallback)
 ↓ ExtractedResult {title, summary, key_points, entities, tags}
 ↓ kronos dispatcher.py (三路分发)
 ├→ Obsidian Vault (.md, frontmatter)
 ├→ WPS Note (XML)
 └→ KOS 索引 + gbrain import (chunk → 向量 → Postgres)
```

**数据格式变换**: `URL → HTML → Markdown → 结构化 JSON → 向量嵌入 → Postgres`

### 4.2 用户需求 → 任务 (c2g → omo)

```
自然语言需求
 ↓ c2g brainstorm (6 场景: gongwen/vault/research/family/health/finance)
 ↓ Pitch markdown (frontmatter: Upstream + Appetite + Scenario)
 ↓ 用户填充背景/目标/验收标准
 ↓ c2g bet → bridge_import.py
 │  1. _parse_pitch_frontmatter()
 │  2. llm.py: LLM 提取 task 结构
 │  3. task_builder.py: build_ecos_task()
 │  4. _validate_ecos_task() → OMO M2 schema
 ↓ YAML task (M2 validated)
 ↓ omo ingress-task (omo_ingress_task_lifecycle.py)
 │  1. validate_task_data(group="planned")
 │  2. fcntl_lock
 │  3. 注入 metadata (ingress_plane, broker, source_ref)
 │  4. write_yaml_atomic → .omo/tasks/planned/<id>.yaml
 │  5. _record_trail() → omo-trail.jsonl
 │  6. record_audit() → governance-audit.jsonl
```

**数据格式变换**: `自然语言 → Pitch markdown → YAML task (M2 schema 校验) → .omo/tasks/`

### 4.3 代码 → 代码图 (codeanalyze → gbrain)

```
源码目录 (.py/.ts/.rs)
 ↓ codeanalyze crg build (Tree-sitter AST 解析)
 ↓ 图节点 (函数/类/方法/变量) + 边 (调用/继承/导入/引用)
 ↓ SQLite (.crg.db) + HTML 可视化
 ↓ (可选) gbrain code-intel → Postgres 持久化
```

### 4.4 治理事件 → 审计日志 (omo → AppendOnlyLog)

```
治理事件 (agent_mutation / audit / bos_invoke)
 ↓ omo event emit → record = {ts, kind, source, payload}
 ↓ AppendOnlyLog.append(rec, schema=...)
 │  7 consumers 共享同一物理层:
 │  #1 omo_audit      → governance-audit.jsonl
 │  #2 omo_bos_metrics → bos-metrics.jsonl
 │  #3 omo_sync        → omo-sync.jsonl
 │  #4 omo_alert       → omo-alerts.jsonl
 │  #5 omo_event       → omo-events.jsonl
 │  #6 omo_history     → governance-history.jsonl
 │  #7 omo_trail       → omo-trail.jsonl
 ↓ fcntl_lock → JSONL append
```

### 4.5 健康数据 → Dashboard (runtime → cockpit)

```
runtime scheduler.py (每 15s)
 ↓ MatrixScheduler._check()
 │  1. load_matrix() → ~/runtime/matrix.yaml
 │  2. launchctl list / HTTP probe
 │  3. freshness tracking
 │  4. auto_heal (连续失败 → 重启)
 ↓ 检查结果 dict
 ↓ 双文件写入:
 │  ~/runtime/matrix_state.json (freshness, status)
 │  .omo/state/system_health.yaml (schema 校验)
 ↓ cockpit dashboard_server.py (:port (见 port-registry))
 ↓ HTTP API → cockpit-ui (React) 渲染
```

---

## 5. 控制流 (Control Flow)

### 5.1 Agent 请求路由 (agora BOS resolve)

```
Agent → resolve_bos_uri("bos://memory/kos/search", {query: "..."})
 ↓
agora MCP Hub (:port (见 port-registry) SSE / :port (见 port-registry) HTTP / stdio)
 ↓ BOS Resolver (services.py)
 │  regex 匹配: bos://<domain>/<package>/<action>
 │  POC_SERVICES 注册表: etc/bos-services.yaml (服务 (见 project-registry.yaml: bos.service_count))
 ↓ BosService {transport, command, module_path, func_name, http_url}
 ↓ Transport 决策:
 ├→ stdio: subprocess.run(uv run ...)
 ├→ internal: Python 函数直接调用
 ├→ http: HTTP 请求到后端 API
 └→ mcp_proxy: MCP stdio 代理
 ↓ 后端执行
 ↓ {"ok": true, ...data} (agora _ok 格式)
```

### 5.2 任务调度 (omo → metaos gate → runtime KEI)

```
omo worker dispatch <task_id> <worker_id>
 ↓ omo_worker_dispatch.py: dispatch_task()
 │  1. validate_task_file() → schema 校验
 │  2. Task Gate:
 │     A. debt P0 阻塞? → BLOCKED
 │     B. depends_on 未完成? → BLOCKED
 │  3. 生成 Worker Prompt Contract (写入边界 + deliverables)
 ↓ (通过 Task Gate)
 ↓ MetaOS DecisionGate (gate.py)
 │  evaluate(task):
 │    red_keywords → RED (阻止)
 │    yellow_keywords → YELLOW (需事后确认, 24h deadline)
 │    默认 → GREEN (放行)
 │  规则: config/decision_matrix.json (热重载)
 ↓ DecisionLevel
 ↓ runtime KEI Sandbox (kei_sandbox.py)
 │  sys.addaudithook (Python C-level)
 │  拦截: subprocess/socket/open + FS mutation
 │  默认: 仅 localhost, workspace r/w, 禁止子进程
 │  审计: JSONL 日志
```

### 5.3 治理审计 (omo governance → 7 检查 → healing)

```
omo governance audit
 ↓ omo_governance_surfaces_report.py
 ↓ 7 项治理面检查:
 │  1. state_plane_asset    (state_plane.py)
 │  2. mutation_surface     (mutation_surface.py)
 │  3. internal_write_profile (internal_write_*.py)
 │  4. c2g_omo_boundary     (c2g_boundary.py)
 │  5. ingress_registry     (ingress.py)
 │  6. ingress_artifacts    (ingress_artifacts.py)
 │  7. task_policy_registry (task_policy.py)
 ↓ GaC 规则校验 (gac-validate + gac-drift)
 ↓ governance score
 ├→ score = 100 (A+ 稳态) → ✓
 └→ score < 100
    ↓ omo self-healing (omo_self_healing.py)
    │  HealingRuleEngine:
    │    ErrorEventCounter (滑动窗口 300s)
    │    动作: upsert_debt + workflow 修复 + event publish
    └→ FIX_REGISTRY: omo_self_healing_fixes.py
```

### 5.4 工作流执行 (cockpit → ecos → backend)

```
cockpit workflow run <name>
 ↓ ecos/workflow/loader.py: load_workflow(name)
 │  优先: M1 节点 → 回退: definitions/
 ↓ workflow dict (M1 normalized)
 ↓ ecos/workflow/validator.py (X1-X4 校验管线)
 │  Preflight:
 │    X1ConstraintChecker (协议注册 + 跨层调用)
 │    X2BudgetDeducer (预算拦截, 余额不足 → 熔断)
 │  Execute:
 │    executor.py: execute_m1_workflow()
 │    cache_get() → 缓存命中?
 │    → backend_registry.resolve() 路由
 │  Postflight:
 │    X4ConsistencyChecker (依赖完整性)
 │    X3CostRecorder (成本归因)
 │    M0 snapshot (workflow-runs 状态)
 ↓ backend_registry.py: resolve(backend)
 │  6 后端: metaos / agora / symphony / swarm / runtime / default
 │  + cache.py (LRU) + circuit_breaker.py (熔断)
```

---

## 6. 逻辑流 (Logic Flow)

### 6.1 GaC 规则生命周期 (状态机)

```
draft ──(radar 验证 7天)──→ active ──(过时/替代)──→ deprecated ──(28天 GC)──→ removed
 │                            │                        │                           │
 │ schema 强制 7 必填字段      │ executor drift 检测      │ 仍执行但标记警告            │ 终态
 │ 不执行 (仅声明)             │ CI gate 阻塞            │ gac-gc --dry-run 预览      │ 从注册表删除
 │                            │ M1 实例化 (gac-m1-sync)  │ 28 天共存期                │ M1 标 deprecated
```

**转换条件**:
- draft → active: radar 验证执行通过 + schema 校验 + drift 检测
- active → deprecated: 规则过时或被替代 (ADR + 注册表 + drift)
- deprecated → removed: 28 天共存期后 gc cron 清理

### 6.2 任务生命周期 (状态机)

```
                    ┌──────────┐
                    │ planned  │ ← c2g bet 创建
                    └────┬─────┘
                         │ promote_task_to_active (人工审批)
                         ▼
                    ┌──────────┐
           ┌───────│  active   │───────┐
           │        └────┬─────┘       │
           │             │ Worker 完成  │ Task Gate 阻塞
           │             ▼             │ / 依赖未完成
           │        ┌──────────┐       │
           │        │  review  │       ▼
           │        └────┬─────┘  ┌──────────┐
           │             │        │ blocked  │
           │      ┌──────┴──────┐ └────┬─────┘
           │      │            │      │ 条件解除
      revert  ┌──────┐   ┌──────┐     │
      to      │ done │   │revert│←────┘
      planned └──────┘   └──────┘
                │
                │ archive_done_task
                ▼
           ┌──────────┐
           │ archived │
           └──────────┘
```

**task_policy 红线**:
- `self-evolution-approval`: 必须保留 planned + approval_state=awaiting_human
- `human-approval-ref`: 需 approval_ref 指向 runs/

### 6.3 免疫监控 (阈值升级)

```
NONE ──(驳回 3 次 / 语义噪声)──→ WARNING ──(累计超阈值)──→ FREEZE ──(连续冲突 5 次)──→ MELTDOWN
 │                                 │                        │                          │
 │ 正常                            │ 可驳回                  │ 只读模式                  │ 强制降级
 │                                 │ 元认知盲点诊断           │ 需 H 干预解冻             │ 停止所有自动决策
 │                                 │ 接受建议但 outcome<0.3   │                          │ 需人工介入恢复
```

**升级阈值**:
- NONE → WARNING: `WARNING_THRESHOLD = 3` (同类驳回 3 次)
- WARNING → FREEZE: 累计超阈值 (自动只读)
- FREEZE → MELTDOWN: `MELTDOWN_THRESHOLD = 5` (连续冲突 5 次 / 核心价值观冲突)

### 6.4 MOF 派生链 (SSOT 级联校验)

```
M3 元元模型 (model-driven/m3_extended.py)
 │ STANDARD_STAGES (7): COLD_START→REQUIREMENT→DESIGN→IMPLEMENTATION→VERIFICATION→DEPLOYMENT→HARDENING
 │ STANDARD_GATES (4): G1_REQUIREMENT→G2_DESIGN→G3_IMPLEMENTATION→G4_VERIFICATION
 │ PipelinePhase (3): COLD_START→EVOLUTION→HARDENING
 ↓ mof-derive (跨仓推理, 真实 import 11 字段)
M2 schema (ecos/m2/*.yaml, 48 个)
 │ 建模契约: required / optional / stateMachine / validationRules
 │ 硬约束: gate_status=passed implies evidence>=1
 ↓ mof-schema-validate (4 flags: --strict/--check-types/--check-transitions/--check-refs)
M1 实例 (ecos/m1/**/*.yaml, 节点 (见 project-registry.yaml: m1_yaml))
 │ 每个必含: m3_parent + model_driven_refs (双向引用)
 │ 9 子目录: architecture/domain/process/specification/bosroute/artifact/skill/mechanism/entity
 ↓ mof-bridge-sync (lifecycle 增量 diff/sync)
 ↓ mof-state-bridge (.omo/tasks/ ↔ M1 OMOTask 双向同步)
 ↓ gac-m1-sync (registry ↔ M1 GacRule 实例同步)
```

**桥接铁律**:
1. M3 是 SSOT (不得复制)
2. M1 必含双向引用 (m3_parent + model_driven_refs)
3. M2 schema 必含 validationRules (硬约束)
4. 新增阶段/门禁 → 6 处同步
5. pre-commit hook 强制 (--staged --strict)

---

## 7. 架构模式总结

### 7.1 核心架构模式

| 模式 | 实现 | 应用位置 |
|------|------|---------|
| **AppendOnlyLog SSOT** | 7 consumers 共享 JSONL 物理层 (fcntl 锁) | omo (审计/事件/指标/告警/同步/历史/trail) |
| **BOS URI 抽象** | 声明式注册表 + 泛化路由 (SmartRouter) | agora (服务 (见 project-registry.yaml: bos.service_count), 9 域) |
| **X1-X4 校验管线** | preflight (X1+X2) → execute → postflight (X4+X3+M0) | ecos workflow |
| **M3→M2→M1 派生链** | SSOT 级联校验 (6 处同步) | ecos MOF + model-driven |
| **门控决策** | GREEN/YELLOW/RED + 免疫三层 | metaos DecisionGate + ImmuneMonitor |
| **Ports & Adapters** | IOC + 双适配器 (ecos/local) | c2g |
| **IDataAccess Protocol** | 可替换存储层 (SQLite/MCP/HTTP) | cockpit |
| **Factory 桥接** | 运行时注入 (model-driven/agora/bus/cockpit) | omo 4 个 bridge |
| **KEI 沙箱** | sys.addaudithook (C-level 拦截) | runtime |
| **声明式注册** | 加规则 = 加 YAML (不改代码) | GaC (见 project-registry.yaml: gac.rules_count) |

### 7.2 数据持久化矩阵

| 项目 | YAML | JSON | JSONL | SQLite | Postgres | 文件 |
|------|:----:|:----:|:-----:|:------:|:--------:|:----:|
| omo | ✅ (.omo/) | — | ✅ (7 logs) | — | — | — |
| ecos | ✅ (M1/M2/registry) | — | ✅ (SSB) | — | — | — |
| runtime | ✅ (matrix) | ✅ (state) | ✅ (KEI) | ✅ (cron) | — | — |
| agora | ✅ (bos-services) | ✅ (registry) | — | ✅ (DLQ) | — | — |
| cockpit | — | — | — | ✅ (research) | — | — |
| gbrain | — | — | — | — | ✅ (70 ops) | — |
| kairon | — | — | ✅ (events) | ✅ (index) | (via gbrain) | ✅ |
| l4-kernel | ✅ (domain) | — | — | — | — | ✅ |

### 7.3 状态机汇总

| 系统 | 状态机 | 转换 |
|------|--------|------|
| GaC 规则 | draft → active → deprecated → removed | 7天验证, 28天 GC |
| 任务 | planned → active → review → done/blocked/archived | 人工审批, Task Gate |
| 免疫监控 | NONE → WARNING → FREEZE → MELTDOWN | 3次驳回, 5次冲突 |
| 工作流缓存 | cached → invalidated → expired | TTL + 手动 |
| 熔断器 | closed → open → half-open → closed | 失败计数 + 冷却 |
| MOF 生命周期 | COLD_START→REQUIREMENT→DESIGN→IMPLEMENTATION→VERIFICATION→DEPLOYMENT→HARDENING | 7阶段 + 4门禁 |

---

*全量架构功能地图 (细化版) · 2026-06-28 · 3 组 subagent 并行深挖 · 架构+依赖+内部+数据流+控制流+逻辑流*
