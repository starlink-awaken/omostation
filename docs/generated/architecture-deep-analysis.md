# 织星 eCOS v6 — 架构深度剖析

> 生成时间: 2026-07-13
> 数据源: `docs/project-registry.yaml` · `protocols/port-registry.yaml` · `ARCHITECTURE.md` · 源码 `@mcp.tool()` 扫描
> 覆盖: 17 项目 · 5+4+1+1 全架构层 · ~500 MCP 工具 · 114 BOS 服务

---

## 1. 全景数字

| 维度 | 数量 | 读源 |
|------|:----:|------|
| 层级 | 5+4+1+1 (L0-L4 + I0 + M0 + X) | project-registry |
| 子模块 | 17 git submodules | project-registry |
| BOS 服务 | 114 | agora/etc/bos-services.yaml |
| 活跃端口 | 30 (含 12 omlx 推理) | port-registry |
| MCP 工具 | ~500+ (gbrain 135 + toolbox 243) | 源码扫描 |
| GaC 规则 | 96 | governance-checks.yaml |
| MOF M1 节点 | 1196 yaml | project-registry |
| MOF M2 schema | 48 | project-registry |
| mof-tools | 34 | project-registry |
| L4 管理域 | 28 | l4-kernel registry.py |
| 收敛 Web 面板 | 1 (cockpit :8090) | port-registry |

---

## 2. 分层架构 (5+4+1+1)

```
┌─────────────────────────────────────────────────────┐
│  L4 自我层      l4-kernel (28域·42 MCP·KEMS·CARDS)  │
├─────────────────────────────────────────────────────┤
│  L3 入口层      cockpit (CLI+Web·51路由·唯一人类入口)│
│                 cockpit-ui (React·24视图)            │
├─────────────────────────────────────────────────────┤
│  L2 引擎层      kairon (16包·80 MCP·知识引擎)        │
│                 gbrain (Postgres·135 ops·混合RAG)    │
│                 omo (173文件·39 CLI·19 MCP·治理核)   │
│                 metaos (决策门控·免疫·DAG编排)       │
├─────────────────────────────────────────────────────┤
│  L1 运行时      runtime (Matrix·Scheduler·KEI·Cron)  │
├─────────────────────────────────────────────────────┤
│  L0 协议层      ecos (MOF M3→M2→M1·SSB·workflow)     │
├─────────────────────────────────────────────────────┤
│  I0 织层        agora (66 MCP·BOS路由·九步链路)      │
│  M0 横切        model-driven (7阶段·4门禁)           │
│  X 扩展         bus-foundation·aetherforge·c2g      │
└─────────────────────────────────────────────────────┘
```

---

## 3. 项目全量清单

| # | 项目 | 层 | 版本 | 核心职责 | MCP Tools |
|---|------|:--:|:----:|---------|:---------:|
| 1 | **ecos** | L0 | 0.8.0 | MOF 元模型、SSB 签名链、workflow 引擎 | 30 |
| 2 | **runtime** | L1 | 1.0.0 | Matrix/Scheduler/KEI 沙箱、Cron | 14 |
| 3 | **kairon** | L2 | 1.0.0 | 知识引擎 monorepo (16 packages) | ~80 |
| 4 | **gbrain** | L2 | 0.39.0 | Postgres 知识数据库 + 混合 RAG | 70+ |
| 5 | **omo** | L2 | 1.0.0 | 治理中枢 (任务/债务/审计/自愈/GaC) | 19 |
| 6 | **metaos** | L2 | 1.0.0 | 编排引擎 (决策门控/免疫/路由) | — |
| 7 | **cockpit** | L3 | 0.4.0 | 统一入口 (CLI + MCP + Web) | 2 |
| 8 | **cockpit-ui** | L3 | — | Web 控制台 UI (Vite/React) | — |
| 9 | **l4-kernel** | L4 | 1.0.0 | 自我层管理面 (28 域 · KEMS) | 42 |
| 10 | **agora** | I0 | 3.0.0 | MCP Hub · BOS URI 路由 · A2A | 66 |
| 11 | **model-driven** | M0 | 1.0.0 | 横切生命周期框架 (7 阶段) | 2 |
| 12 | **aetherforge** | X | 1.0.0 | 能力与算力框架 (LLM 网关/网格/蜂群) | 7 |
| 13 | **bus-foundation** | X | 0.2.0 | Omni-Bus 基础设施 (9 backends) | 0 (lib) |
| 14 | **c2g** | X | 0.1.0 | 战略需求引擎 (V2P → C2G) | 3 |
| 15 | **omo-debt** | L2/X | 1.0.0 | 技术债务评分 CLI | 0 (CLI) |
| 16 | **observability** | X | Docker | 可观测性 (Langfuse) | — |
| 17 | **family-hub** | L2 | 0.1.0 | 家庭数字枢纽 (任务游戏化) | 6 |

**归档项目**: compute-mesh → aetherforge/mesh · swarm-engine → aetherforge/swarm · hermes-console → cockpit-ui · agora-dashboard → cockpit :8090

---

## 4. HTTP/API 服务矩阵

### 4.1 活跃端口 (30 个)

| 端口 | 名称 | 框架 | 所属 | 状态 |
|:----:|------|------|------|:----:|
| **7420** | bos-api | FastAPI | agora | ✅ |
| **7422** | agora-mcp-http | FastMCP | agora | ✅ |
| **7430** | agora-internal | FastAPI | agora | ✅ |
| **7431** | agora-mcp-sse | FastMCP | agora | ✅ |
| **7432** | ecos-event-listener | FastAPI | ecos | ✅ |
| **7437** | omlx-mesh-router | Python http | bin | ✅ |
| **7450** | runtime-cron-http | FastAPI+SQLite | runtime | ✅ |
| **7456** | l4-kernel-mcp-sse | FastMCP | l4-kernel | ✅ |
| **8080** | ontoderive-web | FastAPI | kairon | ✅ |
| **8090** | **cockpit-dashboard** | FastAPI | cockpit | ✅ 唯一人类入口 |
| **8766** | kos-rest-api | FastAPI+uvicorn | kairon/kos | ✅ |
| **9100** | omo-webhook | FastAPI | omo | ✅ |
| **9876** | runtime-l1 | FastAPI | runtime | ✅ |
| **8745** | bus-foundation-metrics | FastAPI | bus-foundation | ✅ |
| **11434** | ollama | Ollama | 外部 LLM | ✅ |
| **8181-8192** | omlx-vision/embed/mythos 等 | MLX Serve | omlx | ✅ |

### 4.2 Deprecated / Converged

| 端口 | 名称 | 状态 | 收敛到 |
|:----:|------|:----:|--------|
| 8765 | minerva-kos-ontoderive | deprecated | cockpit /dev/* |
| 9090 | ecos-dashboard | deprecated | cockpit /api/ecos/* |

---

## 5. MCP 工具生态

### 5.1 全量统计

| 项目 | MCP Tools 数 | 关键工具 |
|------|:------------:|---------|
| **kairon** (16 packages) | **~80** | `derive`, `search_knowledge`, `research_now`, `kronos_fetch` |
| **agora** (I0 Hub) | **66** | `resolve_bos_uri`, `list_bos_resources`, `a2a_send_task` |
| **ecos** (L0) | **30** | `ssot_check/derive/compile`, `workflow_run/validate` |
| **omo** (治理核) | **19** | `validate_task`, `omo_worker_dispatch`, `cards_status` |
| **l4-kernel** (L4) | **42** | `l4_domains_list`, `l4_cards_*`, `l4_kems_validate` |
| **runtime** (L1) | **14** | `runtime_health`, `runtime_matrix_list`, `runtime_agent_*` |
| **gbrain** | **70+** | `search`, `query`, `put_page`, `extract_facts` |
| **toolbox** | **243** | WPS Office Excel/Word/PPT 全套 |
| **其他** (iris/kronos/forge/sophia/minerva/codeanalyze/family-hub) | **~80** | 各领域专用 |

**MCP 工具生态总计: ~500+ 工具**

### 5.2 传输协议分布

| 传输类型 | 使用方 |
|---------|--------|
| **stdio** | kairon packages, ecos, omo, runtime, cockpit, c2g, family-hub |
| **SSE** | agora :7431, l4-kernel :7456 |
| **HTTP** | agora :7422, gbrain HTTP transport |
| **internal** | agora resolver (同进程 importlib) |

---

## 6. BOS URI 服务 (114 服务注册)

> SSOT: `projects/agora/etc/bos-services.yaml` · 路由枢纽: agora `resolve_bos_uri`

### 6.1 BOS 域分布

| BOS 域 | URI 前缀 | 服务数 | 核心能力 |
|--------|----------|:------:|---------|
| **memory** | `bos://memory/` | ~25 | kos/search/mcp-v2/graphrag, kronos/ingest, gbrain/search/query/sync |
| **governance** | `bos://governance/` | ~30 | omo/state/debt/audit, metaos/decide/immune/route, agent-workflow/* |
| **analysis** | `bos://analysis/` | ~20 | minerva/research, ontoderive/derive, codeanalyze/scan, iris/discover |
| **capability** | `bos://capability/` | ~20 | agent-runtime/execute, forge/*, swarm/run, runtime/health |
| **persona** | `bos://persona/` | ~8 | core-models/schema, health-profile/query, family-hub/health |
| **meta/system** | `bos://meta/` `bos://system/` | ~20 | ecos/workflow, backends/routes, discovery/package |

### 6.2 九步路由链

```
Agent → resolve_bos_uri(uri, args)
  ① 域鉴权 → ② 限流 acquire → ③ 熔断检查 → ④ 缓存查询
  → ⑤ BOSRouter.resolve (Trie O(k)) → ⑥ get_service(uri)
  → ⑦ transport 执行 (stdio/internal/http/mcp_stdio)
  → ⑧ 缓存写入 + record_success → ⑨ L0 审计 + EventBus 发布
```

---

## 7. 每层核心能力

### 7.1 L0 — 协议层 (ecos)

| 能力域 | 核心模块 |
|--------|---------|
| MOF 元模型 | `ssot/mof/` (M3→M2→M1, 1196 节点) |
| SSOT 工具 | `ssot/tools/` (34 tools) |
| Workflow 引擎 | `workflow/` (loader→validator→executor+6 backend) |
| SSB 签名链 | `l0/` (不可篡改认知操作记录) |
| 治理模块 | `l0/governance/` (X1-X4 协议检核) |

### 7.2 L1 — 运行时 (runtime)

| 能力域 | 核心模块 |
|--------|---------|
| Matrix 服务注册 | `matrix.py` (ServiceEntry YAML) |
| Scheduler | `scheduler.py` (15s 心跳 + auto-heal) |
| KEI 沙箱 | `kei_sandbox.py` (sys.addaudithook C-level 审计) |
| Cron Service | `cron_service/` (FastAPI + SQLite, 7 HTTP 路由) |
| Executor 核心 | `engine.py` (AgentRuntime: LLM→tools→result) |

### 7.3 L2 — 引擎面

#### kairon (16 packages, ~80 MCP tools)

| Package | 职责 | 关键能力 |
|---------|------|---------|
| **kos** | 知识检索 | FTS5 + jieba 中文分词 + 本体图谱 + REST :8766 |
| **minerva** | 深度研究 | DuckDuckGo + Semantic Scholar 多源搜索 |
| **ontoderive** | 渊衍框架 | 事实驱动推导, 15 推理器 |
| **kronos** | 知识摄取 | 5 层抓取路由 |
| **codeanalyze** | 代码分析 | AST/CRG 代码图 (31 MCP) |
| **iris** | 平台连接器 | 20+ 平台连接器 |
| **eidos** | Schema 记忆 | CRDT 语义索引 |
| **forge** | 工具市场 | 搜索/安装/发布 |
| **sophia** | 范式编译 | 状态机驱动研究运行时 |

#### gbrain (135 ops, 70+ MCP-exposed)

| 能力域 | 关键操作 |
|--------|---------|
| Page CRUD | `get/put/delete/list/restore_page` |
| 混合 RAG | `search`, `query`, `search_by_image` |
| 代码智能 | `code_callers/callees/blast/flow` |
| 热记忆 | `extract_facts`, `recall`, `memory_tree` |
| 矛盾检测 | `find_contradictions`, `find_anomalies` |

#### omo (173 .py, 39 CLI, 19 MCP)

| 能力域 | 模块 |
|--------|------|
| 债务管理 | 17 文件 (registry/lifecycle/dispatch/metrics/reporting) |
| 审计 | 审计+同步+去重+rollout |
| Worker 调度 | core/dispatch/promotion/status |
| 治理面 | overlay/surfaces/state_plane/mutation |
| 自愈 | engine + fixes + trend |
| GaC 规则 | 96 声明式规则 + drift 检测 |

#### metaos (编排引擎)

| 能力域 | 核心模块 |
|--------|---------|
| 决策门控 | DecisionGate (GREEN/YELLOW/RED) |
| DAG 编排 | 8-Phase DAG + SQLite 断点续跑 |
| 免疫监控 | ImmuneMonitor (NONE→WARNING→FREEZE→MELTDOWN) |
| 认知框架 | BDSK / Six Hats 动态加载 |
| 日课仪式 | metaos morning/evening/day/review |

### 7.4 L3 — 入口层 (cockpit + cockpit-ui)

| 能力域 | 核心模块 |
|--------|---------|
| CLI | `cli.py` (35KB, argparse) |
| Web API | `web/` (FastAPI, 51 路由) |
| Dashboard | `dashboard/` (数据聚合 + constants) |
| Agent Runtime | `agent_runtime_*.py` (HTTP + MCP 桥接) |
| L4 Bridge | `l4bridge.py` (14KB, L4 域桥接) |
| cockpit-ui | Vite/React (24+ 视图) |

### 7.5 L4 — 自我层 (l4-kernel)

| 能力域 | 核心模块 | MCP Tools |
|--------|---------|:---------:|
| 域管理 | `registry.py` (28 域) | 6 |
| KEMS 六面 | `kems/` (state/memory/signals/timeline/status/rules) | 7 |
| 搜索/校验 | search/kems_validate/freshness | 4 |
| CARDS | cards_list/get/check/search/compliance | 5 |
| 健康/仪表板 | health/dashboard/signal_patterns | 3 |
| 插件/工作流 | plugin_actions/workflows/specs | 5 |
| Self-Evolution | evolution_status/trigger/tasks | 3 |
| Config/Tools/Storage | config_read/tools_list/storage_usage | 7 |

### 7.6 I0 — 织层 (agora)

| 能力域 | 核心模块 |
|--------|---------|
| MCP Hub | `server/mcp.py` (工具注册 + proxy + a2a) |
| BOS Resolver | `mcp/resolver/` (6 模块, 九步路由) |
| 核心 | `core/` (ServiceRegistry + SmartRouter + CircuitBreaker) |
| Proxy | `mcp_proxy/` (Stdio/HTTP MCP 客户端代理) |
| Auth | `auth/` (OAuth2/HMAC/Tenant/Ed25519) |
| A2A | `a2a/` (Agent-to-Agent 任务协议) |
| 中间件 | `mcp/bos_middleware.py` (限流/熔断/缓存) |

### 7.7 M0 — 横切框架 (model-driven)

| 能力域 | 核心模块 |
|--------|---------|
| 生命周期引擎 | 7 阶段 (COLD_START→HARDENING) + 4 门禁 |
| Trigger 管理 | 10 种触发机制, M1↔M0 漂移检测 |
| 推导引擎 | DR 规则 + 工具执行总线 |

### 7.8 X — 横切扩展

| 项目 | 核心能力 |
|------|---------|
| **bus-foundation** | Omni-Bus v0.3.0: 9 backends + Middleware + DLQ + Schema Registry |
| **aetherforge** | LLM 网关 + 算力网格 + 蜂群 DAG |
| **c2g** | V2P → C2G 双适配器 (ecos/local) |
| **omo-debt** | v2 生命周期感知评分 |
| **observability** | Langfuse HTTP :3050 + OTLP trace |
| **family-hub** | 任务游戏化 + LLM + OMO 治理 |

---

## 8. 跨项目集成链 (17 条已验证)

| # | 集成链路 | 数据流 | 机制 |
|---|---------|--------|------|
| 1 | **cockpit → agora → BOS → target** | 人类命令 → MCP resolve → 后端 | FastMCP client |
| 2 | **cockpit → KOS → gbrain → Minerva** | 搜索 → 跨域语义 → 混合 RAG → 研究 | HTTP :8766 + MCP |
| 3 | **agora → kos/search → gbrain → ontoderive** | BOS URI → stdio → 知识推导 | stdio transport |
| 4 | **c2g → omo → metaos gate → runtime KEI** | 战略需求 → Planned Task → 门控 → 沙箱 | BOS URI |
| 5 | **runtime scheduler → cockpit → cockpit-ui** | 15s 心跳 → matrix_state → HTTP → React | 双文件 + HTTP |
| 6 | **omo governance → 7 检查 → AppendOnlyLog** | 治理事件 → 审计/同步 → JSONL | fcntl 锁 |
| 7 | **ecos workflow → 6 backend** | cockpit workflow run → executor → backend | cache + CB |
| 8 | **kronos → gbrain import** | URL → 5 层抓取 → chunk → 向量 → Postgres | stdio + HTTP |
| 9 | **iris → WPS Note/Notion/...** | 平台连接器同步 → 双向写入 | 20+ 连接器 |
| 10 | **model-driven ↔ M1 (.omo/tasks/)** | mof-state-bridge 双向同步 | 生命周期 diff |
| 11 | **agora → bus-foundation (EventBus)** | BOS 事件发布 → 扇出 → consumer | Omni-Bus shim |
| 12 | **l4-kernel → cockpit L4 bridge** | 域注册 + KEMS 健康 → cockpit 展示 | l4bridge.py |
| 13 | **aetherforge gateway → Ollama/云 LLM** | compute generate → mesh-router → Provider | HTTP :11434 |
| 14 | **family-hub → omo ingress-task** | create_quest → OMO Planned Task | BOS internal |
| 15 | **mof-state-bridge (ecos↔omo)** | M1 OMOTask ↔ .omo/tasks/ 双向同步 | Model-driven 桥接 |
| 16 | **GaC 96 rules → gac-validate/drift → M1 sync** | 声明 → 校验 → 6 层 drift → 同步 | gac-m1-sync |
| 17 | **Agogo MCP :7431 SSE → cockpit probe** | 实时蜂群拓扑 → cockpit dashboard | SSE 推送 |

---

## 9. 功能域 × 场景矩阵

### 域 1：知识生产与消费 (Memory)
- **场景**：URL → 知识库 → 检索 → 推导
- **链路**：kronos(5层抓取) → KOS(FTS5+向量+图谱) → gbrain(混合RAG) → ontoderive(推导)
- **入口**：`bos://memory/local/all-search`

### 域 2：深度研究 (Analysis)
- **场景**：问题 → 多源检索 → 综合报告
- **链路**：minerva(DuckDuckGo+Scholar) → sophia(范式编译) → codeanalyze(AST/CRG)

### 域 3：治理与合规 (Governance)
- **场景**：规则声明 → 审计 → 演化 → 自愈
- **链路**：GaC 96 rules → M1 实例化 → drift → omo 7项审计 → healing

### 域 4：战略到执行 (Capability)
- **场景**：自然语言需求 → 任务 → 门控 → 沙箱执行
- **链路**：c2g(brainstorm→bet→bridge) → omo(ingress-task) → metaos(gate) → runtime(KEI)

### 域 5：自我管理 (L4)
- **场景**：域注册 → KEMS 健康 → 信号 → 日课 → 演化
- **入口**：`l4_domains_list`, `l4_kems_validate`, `l4_signals_list`

### 域 6：家庭枢纽 (Persona)
- **场景**：任务游戏化 → LLM 生成 → OMO 治理
- **项目**：family-hub (6 MCP)

---

## 10. 三大核心数据闭环

### 闭环 1：知识流 (URL → 知识库)
```
URL → kronos fetch (5层路由: MCP→Jina→缓存→CloakBrowser→手动)
    → HTML/raw text → kronos extract (Ollama LLM→规则→fallback)
    → ExtractedResult → ├→ Obsidian Vault (.md)
                         ├→ WPS Note (XML)
                         └→ KOS 索引 + gbrain import (chunk→向量→Postgres)
                               ← kos search (跨域) ← gbrain query (混合RAG)
                               ← ontoderive derive (事实推导) ← sophia (范式编译)
```

### 闭环 2：治理流 (规则 → 审计 → 自愈)
```
GaC 96 rules → M1 实例化 → mof-schema-validate
             → drift 检测 (6层) → gac-m1-sync
             → omo governance (7项审计) → score 100 A+
             → omo healing (ErrorEventCounter 滑动窗口 300s)
             → FIX_REGISTRY → upsert_debt + 修复 workflow
             → AppendOnlyLog (7 consumers)
```

### 闭环 3：执行流 (需求 → 任务 → 门控 → 执行)
```
自然语言 → c2g brainstorm (6场景) → Pitch markdown
         → c2g bet → bridge_import → LLM 提取 + M2 schema 校验
         → omo ingress-task lifecycle → fcntl_lock → .omo/tasks/planned/
         → promote_task_to_active (人工审批)
         → omo worker dispatch → metaos gate (RED/YELLOW/GREEN)
         → runtime KEI sandbox (sys.addaudithook 审计)
         → omo evidence → task complete → 晋升/归档
```

---

## 11. 数据流与依赖图

### 11.1 Python import 依赖矩阵

```
cockpit (L3, 顶层)
   ├── agora (I0) ─┬─ bus-foundation (X, 基础)
   │                 ├── ecos (L0) ──→ omo (L2, 唯一向上)
   │                 └── metaos (L2) ── l4-kernel (L4)
   ├── l4-kernel ────── model-driven (M0, 叶子)
   ├── omo (L2) ───┬─ aetherforge (X)
   │                 ├── bus-foundation (X)
   │                 └── model-driven (M0)
   └── runtime (L1) ─┬─ aetherforge (X)
                      ├── bus-foundation (X)
                      └── omo (L2)

bus-foundation — 被 7 项目 import，真正基础设施
model-driven   — 零依赖叶子
gbrain         — 独立 TS runtime，零 Python import
```

### 11.2 数据持久化矩阵

| 项目 | YAML | JSON | JSONL | SQLite | Postgres | 文件 |
|------|:----:|:----:|:-----:|:------:|:--------:|:----:|
| omo | ✅ | — | ✅ (7 logs) | — | — | — |
| ecos | ✅ | — | ✅ (SSB) | — | — | — |
| runtime | ✅ | ✅ | ✅ (KEI) | ✅ (cron) | — | — |
| agora | ✅ | ✅ | — | ✅ (DLQ) | — | — |
| cockpit | — | — | — | ✅ | — | — |
| gbrain | — | — | — | — | ✅ | — |
| kairon | — | — | ✅ | ✅ | (via gbrain) | ✅ |
| l4-kernel | ✅ | — | — | — | — | ✅ |

### 11.3 状态机汇总

| 系统 | 状态机 | 转换条件 |
|------|--------|---------|
| GaC 规则 | draft → active → deprecated → removed | 7 天验证, 28 天 GC |
| 任务 | planned → active → review → done/blocked | 人工审批 + Task Gate |
| 免疫监控 | NONE → WARNING → FREEZE → MELTDOWN | 3 次驳回 / 5 次冲突 |
| 熔断器 | closed → open → half-open → closed | 失败计数 + 冷却 |
| MOF 生命周期 | COLD_START → ... → HARDENING (7 阶段) | 4 门禁 |

---

## 12. 架构洞察

### 健康信号 ✅
- 依赖方向清晰 (cockpit 在顶层，bus-foundation 在底层)
- 收敛效果好 (Web 面板 → cockpit 单一入口)
- MCP 工具生态丰富 (~500)
- 三大闭环完整运转
- BOS URI 抽象层完善 (114 服务统一路由)

### 关注信号 ⚠️
1. **omo 模块膨胀** (173 .py / 39 CLI) — 治理域持续扩展
2. **kairon 16 包最大** — God Module 拆分进行中 (wave 0-5 完成)
3. **GaC 96 规则** — 持续维护成本
4. **bus-foundation 被 7 项目 import** — 变更影响面大
5. **agora 刚清除 organs/nucleus 死代码** — 还有 stdlib 微导入

### 下一步建议

| 优先级 | 方向 |
|--------|------|
| 🥇 | OMO 模块清理 (173 → <100) |
| 🥈 | HTTP 覆盖率 80%→90% |
| 🥉 | 架构收敛度量化指标 |

---

*本报告由架构探索子代理基于全量源码扫描生成，可作为架构决策基线。*

---

## 13. 测试覆盖矩阵

### 13.1 各项目测试统计

| 项目 | 测试数 | 覆盖率 | 测试框架 | 备注 |
|------|:------:|:------:|---------|------|
| **agora** | 1331+ | — | pytest | 清除死代码后全量通过 |
| **ecos** | 890 | — | pytest | 性能测试治本修复后 0 failed |
| **cockpit** | 68 文件 / 722 tests | ~78% | pytest+cov | api_health 70%, api_knowledge 89%, api_sandbox 94%, api_osmos ~60% |
| **family-hub** | 44 | — | pytest | 29 单元 + 15 集成 |
| **kairon/kos** | 493+ | — | pytest | hybrid_search + context_engine + ontology |
| **kairon** | 3,071 | — | pytest | 16 包全量 |
| **omo** | — | — | pytest | 39 CLI 集成测试 |
| **runtime** | — | — | pytest | executor + scheduler + KEI |
| **l4-kernel** | — | — | pytest | 28 域健康检查 |

### 13.2 Cockpit HTTP 覆盖率详情

| 模块 | 覆盖率 | 关键缺口 |
|------|:------:|---------|
| api_health.py | 70% | — |
| api_knowledge.py | 89% | — |
| api_sandbox.py | 94% | — |
| api_omos.py | ~60% | violations/fix-drift 部分覆盖 |
| api_system_map.py | ~25% | 76 行未覆盖 |
| api_logs.py | ~80% | 新增 5 tests |
| api_tasks.py | ~85% | 新增 5 tests |

---

## 14. 计算节点

| 节点 | IP | 硬件 | VRAM | 角色 | 运行模型 |
|------|----|------|:----:|------|---------|
| **MBP-M5-Max** | 100.96.126.35 | Apple M5 Max | 64GB | coder, reasoner, vision | coder, reasoner, vision, vision-lite, embed-bge |
| **mac-mini-M4** | 100.99.210.78 | Apple M4 | 16GB | fast, embed, rerank | fast, mini-chat, embed, rerank, mini-9b |
| **Y7000P-4070** | — | NVIDIA GTX 4070 | — | mid, ocr, vision-lite | mid, ocr, vision-lite |

**分布式架构**: aetherforge mesh-router 智能路由 LLM 请求到最优节点

---

## 15. 外部依赖

### 15.1 推理服务

| 服务 | 端口/URL | 用途 |
|------|---------|------|
| **omlx gateway** | http://100.96.126.35:4000 | LLM 推理网关 |
| **ollama** | http://localhost:11434 | 本地 LLM 推理 |
| **MLX Serve** | :8181-8192, :8086-8089 | Apple Silicon 原生推理 (12+ 端口) |

### 15.2 知识源与 API

| 服务 | 用途 | 引用方 |
|------|------|--------|
| **DuckDuckGo** | 网页搜索 | kairon/minerva |
| **Semantic Scholar** | 学术论文 | kairon/minerva |
| **Jina Reader** | 网页转 Markdown | kairon/kronos |
| **OpenAlex** | 学术图谱 | kairon/minerva, paper-researcher |

### 15.3 系统工具

| 工具 | 用途 | 引用方 |
|------|------|--------|
| **tesseract** | OCR 文字识别 | kos/multimodal |
| **whisper** | 语音转写 | kos/multimodal |
| **ffmpeg** | 音视频处理 | kos/multimodal |

### 15.4 存储

| 存储 | 用途 | 引用方 |
|------|------|--------|
| **PostgreSQL** (pglite/postgres) | 知识数据库 | gbrain |
| **SQLite** | 索引/缓存/日志 | cockpit, runtime, family-hub |
| **LanceDB** | 向量索引 | kairon/kos |
| **Obsidian Vault** | 知识文档存储 | vault 域 |

---

## 16. 安全审计

> 最近审计: 2026-07-11

| 级别 | 数量 | 详情 |
|------|:----:|------|
| **CRITICAL** | 0 | — |
| **HIGH** | 0 | — |
| **MEDIUM** | 2 | GBrain admin proxy 无 auth, dashboard router 无 `_AUTH_DEPS` |

### 16.1 认证体系

| 层 | 机制 | 引用方 |
|----|------|--------|
| OAuth2 + PKCE | agora auth 模块 | MCP 工具调用 |
| HMAC-SHA256 | agora auth 模块 | API 签名 |
| Ed25519 | identity_ca.py | 节点身份 |
| Tenant 隔离 | agora tenant 模块 | 多租户数据隔离 |

### 16.2 防护机制

| 机制 | 实现 |
|------|------|
| SSRF 防护 | `validate_external_url` 三级检查 (blocked_hosts → internal → private_ip) |
| 限流 | 20 QPS/域令牌桶 (agora bos_middleware) |
| 熔断 | 失败计数 + 冷却 (CircuitBreaker) |
| KEI 沙箱 | sys.addaudithook C-level FS 审计 |

---

## 17. CI/CD 管线

### 17.1 本地门禁

| 命令 | 用途 |
|------|------|
| `make gac-local-gate` | 默认 (非严格) GaC _gate (GaC validate/drift + agent-workflow lint + MOF schema + doc-ssot) |
| `make gac-local-gate --strict` | CI 模式 (额外 project-layer-index + 全量检查) |
| `bin/gac/gac-local-gate.py --scope files --file <path>` | 文件级 AGCP 验证 |
| `bin/gac/gac-healthcheck.py` | GaC 13 点健康检查 |
| `bin/ssot/ssot-guardian.py` | SSOT 一致性守卫 |
| pre-push hook | ruff lint + 快速测试子集 (可 SKIP_GATE=true 跳过) |

### 17.2 分支保护

| 机制 | 状态 |
|------|:----:|
| blocking pre-push hook | ✅ 已启用 |
| main 分支保护 | ✅ 已启用 (direct push 双重拒绝) |
| PR worktree 隔离 | ✅ per-session worktree + PR |
| squash merge | ✅ 所有 main 变更 |

### 17.3 CI Workflow

| Workflow | 触发 | 内容 |
|----------|------|------|
| **GaC Gate** | push + PR | validate/drift/lint/integrations |
| **MOF Schema** | push + PR | m1/m2/schema 一致性 |
| **Doc SSOT** | push + PR | 文档注册表一致性 |
| **Module Interface** | push + PR | 模块接口契约 |
| **Submodule Reachability** | push + PR | 子模块可达性 |

---

## 18. L4 管理域清单 (28 域)

### 18.1 按类型分布

| 类型 | 数量 | 说明 |
|------|:----:|------|
| **document** | 8 | 文档域 (cockpit/vault/creative/personal/shared/family/work-*) |
| **config** | 3 | 配置域 (ai-config/agents-config/icloud-sharedconf) |
| **tool** | 2 | 工具域 (bin/toolbox-tools) |
| **workspace** | 2 | 工作域 (sharedwork/shareddisk) |
| **model** | 2 | 模型域 (model-volume/sharedmodel) |
| **engine** | 3 | 引擎域 (minerva/knowledge-engine/obsidian-vault) |
| **storage** | 1 | 存储域 (vault) |

### 18.2 完整域列表

| # | ID | 名称 | 类型 | KEMS 面 | 治理能力 |
|---|------|------|------|---------|:--------:|
| 1 | cockpit | @驾驶舱 | document | 6 面 | Tier 1 |
| 2 | vault | @学习进化 | document | 5 面 | Tier 1 |
| 3 | creative | @创意创作 | document | 5 面 | Tier 1 |
| 4 | personal | @个人 | document | 5 面 | Tier 1 |
| 5 | shared | @公共 | document | 5 面 | Tier 1 |
| 6 | family | @家庭生活 | document | 5 面 | Tier 1 |
| 7 | work-weijian | @工作文档-卫健 | document | 5 面 | Tier 1 |
| 8 | work-guozhuan | @工作文档-国转 | document | 5 面 | Tier 1 |
| 9 | work-docs | @工作文档 | document | 5 面 | Tier 1 |
| 10 | ai-config | AI 配置 | config | 4 面 | Tier 2 |
| 11 | agents-config | Agent 配置 | config | 4 面 | Tier 2 |
| 12 | icloud-sharedconf | iCloud 共享配置 | config | — | Tier 2 |
| 13 | bin | 脚本工具 | tool | — | Tier 2 |
| 14 | toolbox-tools | 工具箱 | tool | — | Tier 2 |
| 15 | sharedwork | 共享工作区 | workspace | — | Tier 2 |
| 16 | shareddisk | 共享磁盘 | workspace | — | Tier 2 |
| 17 | model-volume | 模型存储 | model | — | Tier 3 |
| 18 | sharedmodel | 共享模型 | model | — | Tier 3 |
| 19 | minerva | Minerva 研究 | engine | — | Tier 2 |
| 20 | knowledge-engine | 知识引擎 | engine | — | Tier 2 |
| 21 | obsidian-vault | Obsidian 库 | engine | — | Tier 2 |
| 22 | opc | OPC 域 | storage | — | Tier 2 |
| 23 | l4-kernel | L4 内核 | config | — | Tier 1 |
| 24 | ecos-workbench | eCOS 工作台 | tool | — | Tier 2 |
| 25 | omo-governance | OMO 治理 | config | — | Tier 1 |
| 26 | spaces | 空间配置 | config | — | Tier 2 |
| 27 | runtime | 运行时 | engine | — | Tier 2 |

### 18.3 KEMS 六面

| 面 | 说明 | 引用方 |
|----|------|--------|
| **state** | 当前状态快照 | health_monitor |
| **memory** | 历史记忆 | memory_tier L3 |
| **signals** | 信号总线 | l4_signal_emit/list |
| **timeline** | 时间线 | timeline_list |
| **status** | 健康状态 | status_read |
| **rules** | 规则引擎 | rules_read |

---

## 19. Kairon God Module 拆分进度

> 从单 god module (1945 行) 拆分为 16 个独立包

| Wave | 内容 | 状态 |
|------|------|:----:|
| Wave 0 | ontology schema 抽出 + 基础设施搭建 | ✅ |
| Wave 1 | extract 组抽到 extract.py | ✅ |
| Wave 2-5 | 持续拆分 + observability 测试补全 | ✅ |

### 19.1 16 包架构

| 层级 | 包 | 职责 |
|------|---|------|
| **基础层** | core-models | 共享数据模型 |
| | codeanalyze | AST/CRG 代码分析 |
| | kairon-utils | 通用工具 |
| | kairon-pipeline | 事件驱动管线 |
| | kairon-lib-events | 事件库 |
| | kairon-observability | 可观测性 |
| | kairon-plugin-sdk | 插件 SDK |
| | health-profile | 健康档案 |
| **引擎层** | kos | KOS 知识检索 |
| | eidos | Schema 统一记忆 API |
| | iris | 平台连接器 |
| | ontoderive | 渊衍推导框架 |
| **应用层** | minerva | 深度研究 |
| | kronos | 知识摄取 |
| | forge | 工具市场 |
| | sophia | 范式编译 |

**测试**: 3,071 tests, mypy strict 16/16 全绿

---

## 20. 用户场景视角

### 场景 1: 知识搜索 (Memory)
```
用户 → cockpit Web :8090 → /api/knowledge/search
     → cockpit → agora resolve_bos_uri("bos://memory/kos/search")
     → KOS (FTS5 + 向量 + 图谱)
     → 返回排序结果
```

**入口**: cockpit 搜索栏 / Claude Code MCP 工具

### 场景 2: 深度研究 (Analysis)
```
用户 → cockpit → /api/research
     → minerva (DuckDuckGo + Semantic Scholar)
     → sophia (范式编译)
     → 生成研究报告 → WPS Note 存储
```

**入口**: cockpit 研究命令 / minerva MCP tools

### 场景 3: 代码分析 (Analysis)
```
用户 → cockpit → /api/ecos/status
     → codeanalyze (AST/CRG)
     → 返回代码结构 / 依赖图 / 质量报告
```

**入口**: cockpit 代码分析 / codeanalyze MCP (31 tools)

### 场景 4: 治理审计 (Governance)
```
用户 → cockpit → /api/omos/violations
     → ecos contract_gatekeeper
     → 返回违规列表 + 自愈建议
```

**入口**: cockpit GaC 命令 / omo MCP (19 tools)

### 场景 5: 家庭任务游戏化 (Persona)
```
用户 → family-hub → create_quest("读一本书", wisdom, 100, parent)
     → OMO ingress-task (治理可见性)
     → 完成任务 → 积分 + 等级提升
```

**入口**: family-hub MCP (6 tools) / cockpit 任务面板

### 场景 6: 战略到执行 (Capability)
```
用户 → c2g brainstorm → Pitch markdown
     → c2g bet → bridge_import → OMO 任务
     → metaos gate → runtime KEI 沙箱执行
```

**入口**: c2g MCP (3 tools) / cockpit 迭代命令

---

## 21. 债务与 BET 状态

> SSOT: `.omo/_truth/registry/debt.yaml`

### 21.1 概况

| 维度 | 数量 |
|------|:----:|
| 总债务数 | 28 |
| 已关闭 | 24 |
| 开放中 | 4 |
| BET (架构演进) | 全部 done/archived |

### 21.2 已解决的关键 BET

| BET | 成果 |
|-----|------|
| DEBT-AGORA-MODULE-BLOAT | 51→34 模块 (-17) |
| DEBT-OMO-MODULE-BLOAT | 181→174 模块 (-7) |
| DEBT-GBRAIN-OPERATIONS-TS | 21 文件拆分完成 |
| DEBT-RUNTIME-BUILD-SYSTEM | hatchling + KEI FS |

### 21.3 开放债务

| 债务 | 优先级 | 说明 |
|------|:------:|------|
| KAIRON-TYPE-SAFETY | 中 | 类型安全改进 (mostly done) |
| OMO-MODULE-BLOAT | 低 | 173→<100 (可选) |
| 其他 | 低 | 小改进项 |

---

## 22. 本次会话工作摘要 (2026-07-12~13)

| 维度 | 成果 |
|------|------|
| **Quest 模块** | 44 tests (29 单元 + 15 集成) — SQLite + LLM + gbrain + MCP |
| **ecos 性能** | 治本修复: 3 failed → 0 failed, 新增 benchmark_l0.py |
| **agora 清理** | 清除 organs/nucleus 死代码 (406 行删除, 8 文件) |
| **分支清理** | ~85 远程 + ~30 本地分支删除, 4 个 PR 关闭 |
| **架构报告** | 全量深度剖析 (22 维度, 455+ 行) |

---

*本报告由架构探索子代理基于全量源码扫描生成，可作为架构决策基线。*
*最近更新: 2026-07-13*
