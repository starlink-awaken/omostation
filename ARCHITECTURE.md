# ARCHITECTURE.md — eCOS v5 全景架构

**2026-06-08 | 根仓库 `starlink-awaken/omostation`**

> 7 层 · 5 BOS 域 · 4 X 轴切面 · 8 核心项目 · ~2,600 Python + 500 TS 源文件

---

## 一、分层架构全景

```
                          ┌─────────────────────────────────────┐
                          │           L4 · 自我层 (21域)          │
                          │  l4-kernel(管理面) + 21域(数据面)     │
                          │  42 MCP tools · 15场景 · 7插件         │
                          └──────────────┬──────────────────────┘
                                         │ MCP
                          ┌──────────────▼──────────────────────┐
                          │          L3 · 统一入口层              │
                          │  cockpit · CLI 18 + MCP 20 + Web     │
                          │  用户/Agent 的唯一交互面               │
                          └──────────────┬──────────────────────┘
                                         │ bos://
                    ┌────────────────────┼────────────────────┐
                    │                    ▼                    │
                    │  ┌─────────────────────────────────┐    │
                    │  │       I0 · 集成织层 (Agora Mesh)  │    │
                    │  │  MCP 服务发现 · 动态代理 · 断路   │    │
                    │  │  42+ tools · :7422/:7431/:8080   │    │
                    │  └───────┬───────────┬─────────────┘    │
                    │          │           │                  │
                    │    ┌─────▼───┐ ┌─────▼──────────┐      │
                    │    │ bos://  │ │ bos://omo      │      │
                    │    │ memory  │ │ governance     │      │
                    │    └─────┬───┘ └─────┬──────────┘      │
                    │          │           │                  │
         ┌──────────▼──────────▼───────────▼──────────────┐  │
         │                 L2 · 引擎面                     │  │
         │  ┌──────────┐ ┌───────────┐ ┌───────────────┐  │  │
         │  │  kairon  │ │  gbrain   │ │     omo       │  │  │
         │  │ 16 包     │ │ 67 MCP    │ │ 债务·任务·健康 │  │  │
         │  │ 知识引擎  │ │ TS 知识脑  │ │               │  │  │
         │  └──────────┘ └───────────┘ └───────────────┘  │  │
         │  ┌──────────────────┐                           │  │
         │  │     metaos       │                           │  │
         │  │ 决策门控·免疫监控  │                           │  │
         │  └──────────────────┘                           │  │
         └──────────────────────┬─────────────────────────┘  │
                                │                            │
                    ┌───────────▼──────────────┐             │
                    │    L1 · 运行时基础设施     │             │
                    │  Matrix + Scheduler       │             │
                    │  KEI Sandbox + Cron       │             │
                    │  30 MCP tools             │             │
                    └───────────┬──────────────┘             │
                                │                            │
                    ┌───────────▼──────────────┐             │
                    │     L0 · 协议层           │             │
                    │  ecos · SSB 签名链        │◄────────────┘
                    │  涌现计算 · MOF 模型       │  bos://forge
                    │  :9090 Dashboard          │
                    └──────────────────────────┘
```

### 各层定位

| 层 | 项目 | 核心职责 | 通信方式 |
|----|------|---------|---------|
| L4 | l4-kernel + 21域 | 域管理 + KEMS六面 + 跨域场景 + 联邦 | CLI + MCP (43 tools, :7455) + Python API |
| L3 | cockpit | 统一入口，用户/Agent 交互面 | CLI + MCP + Web |
| I0 | agora | 服务发现、MCP 代理、路由、断路 | bos:// URI 路由 |
| L2 | kairon/gbrain/omo/metaos | 知识引擎、治理、编排、决策 | MCP Daemon |
| L1 | runtime | 服务注册、健康监控、沙箱执行 | FastAPI + MCP |
| L0 | ecos | 协议定义、签名链、MOF 模型 | SSB + YAML |

---

## 二、BOS URI 5 域命名空间

eCOS v5 通过 `agora` 作为动态反向代理 Mesh，所有项目和包被抽象为 5 大 BOS URI 命名空间：

```
┌─────────────────────────────────────────────────────────┐
│                  Agora Service Mesh                      │
│              bos:// 前缀拦截 → 路由 → 代理                │
├───────────────┬──────────────┬─────────────┬────────────┤
│  bos://memory │  bos://omo   │bos://analysis│bos://forge │
│  记忆与事实源  │  治理与律法   │ 认知与推演    │ 能力与生态  │
│              │              │             │            │
│ kos          │ metaos       │ ontoderive  │ forge      │
│ kronos       │ eidos        │ minerva     │ runtime    │
│ gbrain       │ protocols    │ codeanalyze │ KEI        │
│ sot-bridge   │ omo          │ sophia      │            │
└──────────────┴──────────────┴─────────────┴────────────┘
                              │
                    bos://persona
                    人格与心智
                    sot-bridge
```

### 域映射表

| BOS URI | 域 | 包/服务 | 职责 |
|----------|----|---------|------|
| `bos://memory/` | 记忆与事实 | kos, kronos, gbrain, sot-bridge | 跨域搜索、知识摄取、持久化、SSOT 桥接 |
| `bos://omo/` | 治理与律法 | metaos, eidos, protocols-layer, omo | 决策门控、Schema 约束、触发器规则、债务管理 |
| `bos://analysis/` | 认知与推演 | ontoderive, minerva, codeanalyze, sophia | 本体推导、深度研究、AST 理解、智慧推理 |
| `bos://persona/` | 人格与心智 | sot-bridge | SharedBrain 桥接，Agent 人格面 |
| `bos://forge/` | 能力与生态 | forge, runtime (KEI) | 服务集市、注册表、沙箱执行 |

### Agent 协议约束

1. **禁止裸文件 I/O** — 状态读写使用 `bos://` URI，由 Agora Mesh 路由
2. **使用 `read_resource("bos://agora/registry")`** — 获取当前 Mesh 工具/资源注册表
3. **使用 `mutate_resource(uri, payload, action)`** — 修改 Mesh 管理对象
4. **MANDATORY ATOMIC COMMITS** — 每次修改后立即 commit，触发 `mof-extract` 知识萃取

---

## 三、数据流与调用链

### 3.1 典型请求路径

```
用户/Agent
  │
  ▼
cockpit CLI/MCP ("cockpit research ...")
  │
  ├─► cockpit.cli → commands/research.py
  │     │
  │     ├─► cockpit.storage (SQLite 本地持久化)
  │     │
  │     └─► runtime.cron_service (任务调度)
  │           │
  │           └─► agora Mesh (bos:// 路由)
  │                 │
  │         ┌───────┼───────┬─────────┐
  │         ▼       ▼       ▼         ▼
  │      kairon   gbrain   omo     metaos
  │      (知识)   (存储)   (治理)   (决策)
  │         │       │
  │         └───┬───┘
  │             ▼
  │        data/kos/  data/sharedbrain/
  │
  ▼
响应 (JSON / 流式 / Markdown)
```

### 3.2 服务注册与健康监控 (Matrix 节奏)

```
runtime.matrix (15s 心跳)
  │
  ├─► 读取 ~/runtime/matrix.yaml (服务定义)
  ├─► 轮询 agora :7430/api/events (服务状态 SSE)
  ├─► 写入 matrix_state.json (新鲜度追踪)
  ├─► 检测过时 → 触发 auto-heal (launchd 重启)
  └─► 写入 OMO_STATE_FILE (债务注册)
```

### 3.3 知识摄入管线

```
外部源 (文件/URL/API)
  │
  ▼
kairon/kronos (摄取管线)
  │
  ├─► 解析 → 结构化
  ├─► kairon/eidos (Schema 校验)
  ├─► kairon/kos (向量化索引)
  └─► gbrain (Postgres 持久化)
       │
       ▼
     RAG 混合搜索 (向量 + 全文)
```

### 3.4 决策门控流 (metaos)

```
请求 → metaos.core.engine (SEngine 六步)
  │
  ├─ 1. DecisionGate (红/黄/绿灯)
  │     └─► config/decision_matrix.json (外部规则)
  ├─ 2. Router (任务→模型映射)
  │     └─► config/task_routes.json (外部规则)
  ├─ 3. MLayer (LLM 执行)
  │     └─► OllamaBackend / OpenAIBackend / MockBackend
  ├─ 4. ImmuneMonitor (免疫检查)
  │     └─► WARNING → FREEZE → MELTDOWN 三级
  ├─ 5. 结果组装
  └─ 6. H 确认
```

---

## 四、项目组件级架构

### 4.1 Agora (I0 · MCP 服务网格)

```
agora/
├── mcp_registry/   — 服务注册表 (YAML → 动态)
├── auth/           — Bearer/JWT 认证中间件
├── core/           — 代理核心 · 断路 · 限流
├── plugins/        — 插件市场
├── mcp/            — MCP 协议适配 (stdio/SSE/HTTP)
├── extensions/     — 扩展点注册
├── pipelines/      — 请求/响应处理管线
├── growth/         — 服务发现 (动态注册)
├── federation/     — 跨集群联邦
└── metrics/        — Prometheus 指标
```

### 4.2 Kairon (L2 · 知识引擎 · 16 包)

```
kairon/packages/
├── eidos/          — Schema 约束与校验 (171 py, 7 MCP tools)
├── kos/            — 跨域知识搜索 (110 py, 26 MCP tools)
├── minerva/        — 深度研究 (185 py, 5 tools)
├── ontoderive/     — 本体推导 (187 py, 5 tools)
├── codeanalyze/    — AST 代码理解 (90 py)
├── forge/          — 集市与注册表 (59 py, 70 tools)
├── iris/           — 感知输入 (59 py, 8 tools)
├── kronos/         — 摄取管线 (27 py, 9 tools)
├── sophia/         — 智慧推理 (14 py, 8 tools)
├── ssot/           — SSOT 桥接 (6 tools)
├── core-models/    — 核心数据模型 (27 py)
├── kairon-utils/   — 工具函数 (26 py)
├── kairon-pipeline/  — 流水线框架 (13 py)
├── kairon-observability/ — 可观测性 (12 py)
├── kairon-plugin-sdk/ — 插件 SDK (8 py)
└── kairon-lib-events/ — 事件库 (5 py)
```

### 4.3 Runtime (L1 · 运行时底座)

```
runtime/
├── cli.py                — 主 CLI (7 子命令)
├── matrix.py             — 服务注册表 (ServiceEntry)
├── scheduler.py          — Matrix 调度器 (15s 心跳 + 自愈)
├── protocol.py           — L0 协议注册 (ProtocolEntry)
├── mcp_server.py         — FastMCP stdio (7 tools)
├── bus_consumer.py       — Agora SSE 事件消费
├── kei.py / kei_sandbox.py — KEI 沙箱 + audit hook
├── cron_service/         — Cron 调度服务 (13 files)
│   ├── server.py         — FastAPI HTTP + MCP
│   ├── scheduler.py      — Tick-based 调度
│   ├── executor.py       — 子进程执行
│   └── db.py             — SQLite 持久化
├── executor/             — Agent 编排引擎 (100+ files)
│   ├── engine.py         — AgentRuntime 核心
│   ├── orchestrator.py   — DAG 任务编排 (8 Phase)
│   ├── dsl.py            — DSL 系统 (YAML/JSON)
│   └── swarm.py          — Swarm 蜂群协议
└── tools/                — MCP 工具集 (5 工具组)
```

### 4.4 Cockpit (L3 · 统一入口)

```
cockpit/
├── cli.py                — 主 CLI (23 子命令)
├── storage.py            — SQLite 持久化 + IDataAccess Protocol
├── dashboard_server.py   — FastAPI Web Dashboard
├── agent_runtime_server.py — Agent Runtime HTTP 服务
├── agent_runtime_mcp_server.py — Agent Runtime MCP Server
├── commands/
│   ├── research.py       — 研究命令 (最大模块, 1257 行)
│   ├── status.py         — 状态概览
│   ├── contracts.py      — 契约管理
│   ├── quickstart.py     — 快速初始化
│   └── ...
└── scripts/
    └── cockpit_mcp.py    — MCP Server (13 tools)
```

---

## 五、X 轴保障体系 (贯穿所有层)

```
         L4 ──────────────────────────────────────
              │ X1  │ X2  │ X3  │ X4  │
         L3 ──┼─────┼─────┼─────┼─────┼──────────
              │     │     │     │     │
         I0 ──┼─────┼─────┼─────┼─────┼──────────
              │     │     │     │     │
         L2 ──┼─────┼─────┼─────┼─────┼──────────
              │     │     │     │     │
         L1 ──┼─────┼─────┼─────┼─────┼──────────
              │     │     │     │     │
         L0 ──┼─────┼─────┼─────┼─────┼──────────
              │     │     │     │     │
              ▼     ▼     ▼     ▼     ▼
         审计链  抗熵   价值栈  一致性
```

| 轴 | 定义 | 实现位置 |
|----|------|---------|
| **X1 审计链** | 操作是否安全 | kei_sandbox (audit hook), agora auth (JWT), metaos gate (决策门控) |
| **X2 抗熵** | 数据是否新鲜 | runtime scheduler (15s 健康心跳), matrix auto-heal, omo debt staleness |
| **X3 价值栈** | 投入是否合理 | omo cost tracking, cockpit priority, kairon health-profile |
| **X4 一致性** | 规则是否被遵守 | CI (20 workflows), pre-commit hooks (ruff + mof-validate), protocol validation |

---

## 六、治理体系 (.omo/ 四平面)

```
.omo/
├── _control/       ← 控制面 (人类修改)
│   ├── goals/      — 阶段目标 (current.yaml)
│   └── state/      — 系统状态 (system.yaml, SOTI 健康分)
│
├── _truth/         ← 事实面 (单一事实源 SSOT)
│   ├── tasks/      — 活跃任务 (YAML)
│   ├── standards/  — 架构标准
│   └── registries/ — 端口/依赖/Worker 注册表
│
├── _knowledge/     ← 知识面 (引用事实面，不复制内容)
│   ├── designs/    — 设计文档
│   ├── audits/     — 审计报告
│   └── retrospects/— 复盘
│
└── _delivery/      ← 交付面 (运行证据)
    ├── logs/       — 运行日志
    └── evidence/   — 测试/CI 证据
```

**铁律**: 知识面引用事实面必须用**相对路径指针**，禁止复制内容。同一事实不在多处写。

---

## 七、关键协议与端口

### 服务端口分配

| 服务 | 端口 | 协议 | 用途 |
|------|------|------|------|
| agora | 7422 | HTTP | MCP HTTP 代理 |
| agora | 7431 | SSE | 事件推送 (Server-Sent Events) |
| agora | 8080 | HTTP | Web Dashboard |
| ecos | 9090 | HTTP | SSB Dashboard |
| cockpit | 8090 | HTTP | Web Dashboard |
| runtime cron | 动态 | HTTP | FastAPI Cron Service |

### 端口注册规则

1. 涉及端口时**必须先查** `protocols/port-registry.yaml`
2. 确认端口未被占用
3. 注册新端口
4. 使用环境变量 `{SERVICE}_PORT`
5. CI 和 Agora runtime 双重阻断端口冲突

---

## 八、技术栈速查

| 项目 | 语言 | 包管理 | 构建 | 测试 | 格式化 | Python |
|------|------|--------|------|------|--------|--------|
| agora | Python | uv | hatchling | pytest | ruff | 3.13+ |
| cockpit | Python | uv | hatchling | pytest | ruff | 3.13+ |
| kairon | Python | uv | hatchling | pytest | ruff | 3.13+ |
| gbrain | TypeScript | bun | bun | bun test | bun fmt | — |
| omo | Python | uv | uv_build | pytest | ruff | 3.13+ |
| metaos | Python | uv | hatchling | pytest | ruff | 3.13+ |
| runtime | Python | uv | setuptools | pytest | ruff | 3.13+ |
| ecos | Python | uv | hatchling | pytest | ruff | 3.13+ |

---

## 九、近期架构演进方向

| 主题 | 状态 | 说明 |
|------|------|------|
| BOS URI 大一统 | 95% | agora Mesh 拦截 bos:// 流量，5 域完整覆盖 |
| Plist/Daemon 化 | P68 收尾 | launchd + KeepAlive + auto-restart |
| MCP Proxy Phase 2 | 完成 | 动态加载/卸载、空闲超时、引用计数 |
| 工作流统一建模 | L0 完成 | 26 工作流 M1 节点建模 + CLI + MCP |
| 目录治理 | 完成 | 根目录清理、SharedBrain 归档 |
