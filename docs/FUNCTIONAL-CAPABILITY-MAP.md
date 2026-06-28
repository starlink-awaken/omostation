# omostation 全量功能能力地图

> **SSOT**: 本文档是 omostation 系统功能能力的唯一全景地图 (聚焦 WHAT: 谁提供什么能力)
> **更新**: 2026-06-28 | **范围**: 17 项目 (5+4+1+1 架构) | **方法**: 4 组 subagent 并行扫描 + 缺口修复
> **状态**: 8 域 32 能力全覆盖, 5 缺口全部修复, 3 重叠 (互补/分层)
> **配套文档**: `docs/ARCHITECTURE-DETAILED-MAP.md` (聚焦 HOW: 架构层次/依赖矩阵/内部模块/数据流/控制流/逻辑流)

---

## 0. 能力总览统计

| 维度 | 数量 |
|------|------|
| 功能域 | 8 |
| 能力项 | 32 |
| CLI 命令 (入口+子命令) | ~120+ |
| MCP 工具总数 | ~280+ |
| HTTP 端点 | ~30+ |
| 核心源文件 | ~800+ |
| M1 元模型节点 | 1315 (含 118 GacRule 实例 + 1 元模型) |
| GaC 治理规则 | 118 |
| BOS 声明式服务 | 100 (9 域) |
| L4 管理域 | 28 |

---

## 1. 知识摄取与持久化 (Knowledge Ingestion)

> 从外部世界获取信息, 结构化存储到系统知识库

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| 多层抓取 | kronos | L2 | `kronos fetch` | `kronos_fetch` / `kronos_browser_fetch` | 5 层抓取引擎 (L0 HTTP → L2 Jina → L4 CloakBrowser), 智能路由 |
| 内容抽取 | kronos | L2 | `kronos extract` | `kronos_extract` | 正文/元数据抽取, 压缩 |
| 摄取洞察 | kronos | L2 | `kronos insight` | `kronos_insight` | 摄取后自动生成洞察 |
| 知识摄取 | gbrain | L2 | `gbrain import` / `sync` / `embed` | `put_page` / `put_raw_data` / `sync_brain` / `log_ingest` | Postgres-native 知识库, 向量化, chunk 分割 |
| 本体构建 | kos | L2 | `kos indexer` | `ontology_rebuild` / `run_indexer` / `full_sync` | FTS5 中文分词 + 本体图谱构建 |
| 数据管线 | kairon-pipeline | L2 | (lib) | — | D-Harvest 数据管线, bus-foundation 事件驱动 |
| 连接器同步 | iris | L2 | `iris sync` | `sync` / `sync_bidirectional` / `validate` | 20+ 平台连接器 (WPS Note / Notion / ...) |

**数据流**:
```
URL/文件 → kronos fetch (5层路由) → kronos extract → gbrain import (向量化)
                                                    ↓
                                          kos indexer (本体图谱)
                                                    ↓
                                          iris sync (外部平台同步)
```

---

## 2. 知识检索与推理 (Knowledge Retrieval)

> 从知识库中检索信息, 进行推理和推导

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| 跨域搜索 | kos | L2 | `kos search` | `search_knowledge` / `semantic_search` / `search_entity` | 6 域知识语义搜索 (jieba + FTS5) |
| 混合 RAG | gbrain | L2 | `gbrain search` / `recall` | `search` / `query` / `search_by_image` / `recall` | 向量+关键词+多查询扩展, 图搜图 |
| 代码理解 | codeanalyze | L2 | `codeanalyze scan` | `codegraph_search` / `ast_search` / `rg_search` / `codegraph_callers` / `codegraph_callees` | AST/调用图/影响半径, 28 MCP tools |
| 语义搜索 | eidos | L2 | `eidos` | `eidos_list` / `eidos_validate` / `eidos_define` / `eidos_export` | 统一记忆 API + 语义索引, CRDT |
| 深度研究 | minerva | L2 | `minerva research` | `research_now` / `cross_domain_research` / `minerva_bfs_search` / `research_schedule` | 多源搜索 (DuckDuckGo + Semantic Scholar), 知识图谱, cron 调度 |
| 知识推导 | ontoderive | L2 | `ontoderive derive` | `derive` / `trace` / `validate` / `pipeline_status` | 事实驱动推导, 元演化, 15 推理器 |
| 范式编译 | sophia | L2 | `sophia` | — | 状态机驱动研究方法运行时, 符号系统 |
| 图遍历 | gbrain | L2 | `gbrain traverse` | `traverse_graph` / `get_backlinks` / `get_links` / `get_tags` | 知识图谱遍历, 标签/链接/时间线 |
| 事实记忆 | gbrain | L2 | `gbrain facts` | `extract_facts` / `recall` / `forget_fact` / `memory_tree` | 热记忆事实抽取与召回 |
| 矛盾检测 | gbrain | L2 | `gbrain contradictions` | `find_contradictions` / `find_anomalies` | 知识矛盾自动检测 |
| 代码智能 | gbrain | L2 | — | `code_callers` / `code_callees` / `code_def` / `code_refs` / `code_blast` / `code_flow` | 持久化代码图 (callers/callees/blast) |

**检索路径**:
```
用户查询 → kos search (跨域) → gbrain query (混合RAG) → 结果
           ↓                    ↓
           eidos validate       gbrain traverse (图遍历)
           ↓
           ontoderive derive (推导) → sophia (范式编译)
```

---

## 3. 治理与合规 (Governance)

> 规则定义, 审计执行, 债务管理, 漂移检测, 自愈修复

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| 治理审计 | omo | L2 | `omo governance` | — | 7 项审计 (lint/test/debt/ADR/task/agora/doc) |
| 任务管理 | omo | L2 | `omo task` / `worker` | `omo_worker_dispatch` / `omo_worker_reclaim` / `omo_yield_task` | 任务调度/晋升/让出/回收 |
| 债务管理 | omo + omo-debt | L2/X | `omo debt` / `omo-debt score` | `omo_debt_list` / `omo_debt_summary` | v2 生命周期感知评分 (Honestesty+Legacy) |
| 规则注册 | GaC | meta | `gac-validate` / `gac-drift` / `gac-m1-sync` | `check_gac_rule` | 118 规则声明式注册 + 6 层 drift + M1 实例同步 |
| BOS URI | agora | I0 | `agora bos` | `resolve_bos_uri` / `mutate_resource` / `list_bos_resources` | 100 声明式服务路由 (9 域) |
| 入口写入 | c2g | X | `c2g bet` | `c2g_bet` | 战略需求 → OMO Planned Task (唯一 ingress) |
| 审计追踪 | omo | L2 | `omo audit-rollout` | `acquire_lock` / `release_lock` / `check_lock` / `list_locks` | AppendOnlyLog + fcntl 锁 + AdvisoryLock |
| 自愈引擎 | omo | L2 | `omo healing` | — | 修复规则 + fix-run + fix-list + 趋势 |
| 事件发射 | omo | L2 | `omo event emit` | — | 用户面向事件样板 (knowledge/governance/...) |
| 可观测日志 | omo | L2 | `omo observability log` | — | 多文件 tail + metric |
| 治理面 | omo | L2 | `omo governance surfaces` | — | 写入面注册表 (mutation-surfaces/internal-write/task-policies) |
| Lint 静态校验 | omo | L2 | `omo lint` (16 子命令) | — | direct-omo-io/schemas/yaml-bypass/god-module/... |

**治理闭环**:
```
规则声明 (gac.rules 118) → M1 实例 (118) → mof-schema-validate (OK)
       ↓                                          ↓
drift 检测 (6 层) → 0 drift → gac-m1-sync (registry↔M1)
       ↓
omo governance (7 项审计) → 100 A+ → omo healing (自愈)
```

---

## 4. 编排与执行 (Orchestration)

> 决策门控, DAG 编排, 免疫监控, Agent 调度

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| 决策门控 | metaos | L2 | `metaos gate` | `metaos_gate` | 红/黄/绿灯判定 (外部规则 decision_matrix.json) |
| DAG 编排 | metaos + runtime | L2/L1 | `metaos` / `runtime agent` | `runtime_agent_run_task` / `runtime_agent_execute` | 8-Phase DAG + SQLite 断点续跑 |
| 免疫监控 | metaos | L2 | `metaos status` | `metaos_health` | 三层: 提醒 → 冻结 → 熔断 |
| 认知框架 | metaos | L2 | `metaos morning` / `evening` | `metaos_morning` / `metaos_evening` / `metaos_review` | BDSK / Six Hats 动态加载 |
| 工作流引擎 | ecos | L0 | `cockpit workflow` | `workflow_run` / `workflow_validate` / `workflow_list` / `workflow_show` | loader/validator/executor + 熔断器 + 缓存 |
| Agent 准入 | metaos | L2 | `metaos admit` | — | 准入网关 (T3.2), CI gate (G3 修复) |
| 群体编排 | aetherforge | X | `cockpit compute swarm` | `forge_generate_mesh` | GraphWorkflow DAG 多 Agent 协调 |
| Agent 管理 | runtime | L1 | `runtime agent` | `runtime_agent_list` / `runtime_agent_status` / `runtime_agent_chat` | Agent 列表/状态/对话 |
| 死锁检测 | metaos | L2 | — | — | 死锁检测器 (deadlock_detector.py) |
| L2 控制 | metaos | L2 | — | — | PID 控制器 (l2_controller.py) |
| 日课仪式 | metaos | L2 | `metaos day <1-7>` | `metaos_day` | 启动指南日课 (7 天) |
| 微粒复盘 | metaos | L2 | `metaos review` | `metaos_review` | 归因分析 (action/expected/actual) |

**执行路径**:
```
c2g bet → OMO Planned Task → omo worker dispatch → metaos gate (门控)
                                                            ↓
                                           runtime agent execute (KEI 沙箱)
                                                            ↓
                                           omo evidence → omo task complete → 晋升
```

---

## 5. 算力与基础设施 (Compute)

> LLM 网关, 算力网格, 服务注册, 健康监控, 沙箱执行, 定时调度

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| LLM 网关 | aetherforge | X | `cockpit compute gateway generate` | `forge_generate` | 多 Provider 路由 / 负载均衡 / 重试 |
| LLM 模型列表 | aetherforge | X | `cockpit compute gateway list` | — | 可用 LLM 模型列表 |
| 算力网格 | aetherforge | X | `cockpit compute mesh list` | `forge_list_nodes` / `forge_mesh_status` / `forge_health_check` / `forge_cost_report` | 节点注册/健康/拓扑发现/成本 |
| 服务注册 | runtime | L1 | `runtime matrix list` / `get` / `resolve` | `runtime_matrix_list` | Matrix YAML 服务注册表 |
| 健康监控 | runtime | L1 | `runtime health` | `runtime_health` | 15s 心跳 + auto-heal |
| 沙箱执行 | runtime | L1 | — | `runtime_agent_execute` | KEI `sys.addaudithook` (FS mutation hooks) |
| 定时调度 | runtime | L1 | — | (Cron Service API) | FastAPI + SQLite cron (7 HTTP 路由) |
| KV 存储 | runtime | L1 | — | `runtime_kv_get` | 键值读取 |
| 本体查询 | runtime | L1 | — | `runtime_ontology` | 本体查询 |

**算力拓扑**:
```
cockpit compute gateway generate → aetherforge gateway → LLM Provider (Ollama/OpenAI/...)
cockpit compute mesh list → aetherforge mesh → 算力节点池 (健康/拓扑/成本)
runtime matrix → 服务注册表 → runtime health (15s 心跳)
runtime agent execute → KEI 沙箱 (sys.addaudithook 审计)
```

---

## 6. 通信与路由 (Communication)

> MCP Hub, BOS URI 路由, A2A 协议, 事件总线, 联邦

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| MCP Hub | agora | I0 | `agora mcp` | 48+ tools (7 模块) | 服务发现/路由/代理, SmartRouter |
| BOS 路由 | agora | I0 | `agora bos` | `resolve_bos_uri` / `read_resource` / `mutate_resource` / `list_bos_resources` / `list_bos_domains` / `get_bos_schema` | 9 域 100 服务 (memory/governance/analysis/persona/capability/meta/omo/swarm/system) |
| BOS 中间件 | agora | I0 | — | `bos_middleware_status` / `bos_metrics_status` / `bos_health` | 限流/熔断/缓存, p50/p95/p99 指标 |
| A2A 协议 | agora | I0 | `agora instance` | `a2a_send_task` / `a2a_get_task` / `a2a_cancel_task` / `a2a_list_tasks` / `list_agent_cards` / `get_agent_card` | Agent-to-Agent 任务协议 |
| 事件总线 | bus-foundation | X | (lib) | — | Omni-Bus 三平面: Data (ring buffer) / Event (扇出) / Control (ACK/NACK + DLQ) |
| 联邦路由 | agora | I0 | `agora converge` | — | 跨节点联邦 |
| 代理工具 | agora | I0 | `agora repo` | `proxy_connect` / `proxy_list_tools` / `proxy_add_service` / `proxy_backend_health` | MCP 代理连接管理 |
| 工作区审计 | agora | I0 | — | `check_health` / `lifecycle_status` / `lifecycle_start_watch` / `lifecycle_stop_watch` | 工作区健康与生命周期 |
| API Key 管理 | agora | I0 | `agora` | (3 tools) | API Key 认证管理 |
| 蜂群协调 | agora | I0 | — | (3 tools) | UDP :7455 蜂群发现 |

**通信架构**:
```
Agent → agora MCP :7431 → resolve_bos_uri → 后端服务
                         ↓
                    BOS 中间件 (限流/熔断/缓存)
                         ↓
                    bus-foundation (Data/Event/Control)
                         ↓
                    A2A 协议 (Agent-to-Agent)
```

---

## 7. 协议与元模型 (Protocol)

> MOF 元模型, SSB 签名链, 生命周期引擎, Trigger 管理, X 轴治理

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| MOF 元模型 | ecos | L0 | `cockpit mof` | `ssot_check` / `ssot_derive` / `ssot_compile` / `ssot_evolve` / `ssot_stats` / `ssot_sync` / `ssot_extract` | M3→M2→M1 三层元模型, 1315 M1 节点 |
| MOF 工具集 | ecos | L0 | (34 个 mof-*.py) | — | validate/audit/derive/bridge-sync/state-bridge/enforce/reason/extract/scan/model/schema-validate/... |
| SSB 签名链 | ecos | L0 | `cockpit ssb` | `ssot_compile` | 不可篡改认知操作记录 (auth/client/dump/init/integrity) |
| 生命周期引擎 | model-driven | M0 | `model-driven lifecycle` | `lifecycle-create` / `lifecycle-advance` / `lifecycle-status` / `lifecycle-dashboard` / `lifecycle-blockers` | 7 阶段 + 4 门禁 + 3 PipelinePhase |
| Spec/ADR/OKR | model-driven | M0 | `model-driven spec` / `adr` / `okr` | `spec-create` / `spec-list` / `adr-create` / `adr-list` / `okr-create` / `okr-progress` | 管理面 (Spec/ADR/OKR) |
| Trigger 管理 | model-driven | M0 | `model-driven trigger` | `trigger-status` / `trigger-derive` / `trigger-heal` / `trigger-dashboard` / `trigger-drift` / `trigger-reload` | 10 种触发机制, M1↔M0 漂移检测 |
| 推导引擎 | model-driven | M0 | — | `model-execute` / `model-tools` / `ssot-drift-check` / `cross-stage-check` / `value-roi` | 15 DR 规则 + 工具执行总线 |
| OMO 桥接 | model-driven | M0 | — | `debt-register` / `task-create` / `audit-record` / `collab-create` / `collab-assign` / `collab-status` | OMO 事件/审计/协作桥接 |
| X 轴治理 | ecos + omo | L0/L2 | `omo x-axis` | — | X1 审计 / X2 抗熵 / X3 价值 / X4 一致 |
| 域树 | ecos | L0 | — | `domain_list` / `domain_stats` / `domain_validate` / `domain_resolve` / `domain_read` / `domain_search` / `domain_tree` | M1 域查询 |

**元模型层次**:
```
M3 (元元模型) → m3_extended.py: STANDARD_STAGES (7) + STANDARD_GATES (4) + PipelinePhase (3)
       ↓ mof-derive
M2 (schema)   → m2/*.yaml: 48 个类型 schema (含 GacRule)
       ↓ mof-schema-validate
M1 (实例)     → m1/**/*.yaml: 1315 节点 (含 118 GacRule 实例 + 1 元模型 + 96 OMOTask + 25 GOV-* + ...)
       ↓ gac-m1-sync
SSOT          → governance-checks.yaml::gac.rules (118 规则)
```

---

## 8. 自我与入口 (Self & Entry)

> 统一入口, 域管理, 健康聚合, Web 控制台, 可观测性, 家庭枢纽

| 能力 | 提供者 | 层 | CLI | MCP Tools | 描述 |
|------|--------|:--:|-----|-----------|------|
| 统一入口 | cockpit | L3 | `cockpit` (24 子命令) | 33 tools | CLI + Web (:8090) + MCP, 唯一人类入口 |
| 研究管线 | cockpit | L3 | `cockpit research` (16 子命令) | `research_list` / `research_search` / `research_create` / `research_ask` / `research_archive` / ... | 深度研究管理 (ask/audit/digest/dossier/publish/...) |
| Web Dashboard | cockpit | L3 | `cockpit dashboard` | — | FastAPI :8090, 15 个 API router 模块 |
| C2G 编排流 | cockpit | L3 | `cockpit iterate` | — | C2G 双擎迭代流 (MetaOS → Model-Driven → OMO) |
| 域管理 | l4-kernel | L4 | `l4-kernel` | 42 tools (20 域) | 28 域注册 + KEMS 六面 + 生命周期 + 信号 |
| 健康聚合 | l4-kernel | L4 | `l4-kernel` | `l4_health_*` | 跨域全局 DASHBOARD |
| CARDS 管理 | cockpit + l4-kernel | L3/L4 | `cockpit cards` | `cards_status` / `cards_check` / `cards_create` / `cards_update` | 卡片状态/检查/创建/更新 |
| Vault 搜索 | cockpit | L3 | `cockpit vault` | `vault_search` | L4 Vault 知识库搜索 |
| Web 控制台 | cockpit-ui | X | (Vite) | — | 24+ 视图组件 (Dashboard/C2G/Compute/Assets/Mesh/Engines/L4Health/Task/Alert/Quest/Debt/...) |
| 可观测性 | observability | X | (Docker) | — | Langfuse trace (HTTP :3000, OTLP) |
| 家庭枢纽 | family-hub | X | `mcp_server.py` | `get_health` / `get_profiles` / `get_active_quests` / `create_quest` / `complete_quest` / `generate_smart_quests` | 任务游戏化 + LLM 生成, OMO 治理接入 (G2) |
| 每日简报 | cockpit | L3 | `cockpit daily` | `daily_summary` | 研究简报 |
| 治理健康 | cockpit | L3 | `cockpit gac` | `governance_check` / `governance_status` / `governance_sla` / `governance_leaderboard` / `governance_dashboard` / `governance_history` | GaC 治理健康检查 |
| HITL 审批 | cockpit | L3 | — | — | `/api/v1/proposals/*` approve/reject |
| 事件流 | cockpit | L3 | `cockpit events` | — | Agora SSE 实时事件流 |

**入口架构**:
```
人类用户 → cockpit CLI (24 子命令) / Web (:8090, 15 routers) / cockpit-ui (24+ 视图)
AI Agent → agora MCP :7431 → resolve_bos_uri → 后端
Web/API  → cockpit HTTP :8090 → /api/* (services/compute/health/events/knowledge/...)
```

---

## 9. 用户场景 × 功能覆盖矩阵

| 场景 | 涉及能力 | 覆盖状态 |
|------|---------|:--------:|
| **S1. 人类知识管理** | kronos fetch + gbrain import + kos search + minerva research + iris sync | ✅ 闭环完整 |
| **S2. Agent 自治执行** | agora MCP + omo task + runtime execute + omo audit + GaC + metaos admit | ✅ G3 修复 |
| **S3. 战略需求落地** | c2g brainstorm + c2g bet + omo task + metaos gate + aetherforge gateway | ✅ G1 修复 |
| **S4. 代码库理解** | codeanalyze scan + codegraph + gbrain code-intel + architecture diagram | ✅ 闭环完整 |
| **S5. 治理审计自愈** | omo governance + gac-validate + gac-drift + gac-m1-sync + omo healing + mof-state-bridge | ✅ G4 修复 |
| **S6. 家庭场景** | family-hub quest + aetherforge gateway + cockpit-ui QuestBoard + omo ingress-task | ✅ G2 修复 |

---

## 10. 功能缺口与重叠 (最终状态)

### 缺口 (5/5 全部修复)

| # | 缺口 | 修复 | Commit |
|---|------|------|--------|
| G1 | aetherforge CLI deprecated, 无 cockpit 替代 | cockpit `compute` 子命令 | cockpit `93fcc37` |
| G2 | family-hub 独立 SQLite, 不受治理 | create_quest 接入 omo ingress-task | family-hub `69bd51e` |
| G3 | Agent 准入未在 CI 强制 | governance-check.yml 加 admit | root |
| G4 | 61 处 M1↔.omo 字段漂移 | 61 个 M1 OMOTask priority/status 修正 | ecos `8357628` |
| G5 | minerva 后台研究无 MCP 暴露 | research_schedule 已存在 (cron 调度) | 无需改动 |

### 重叠 (3 项, 互补/分层, 可接受)

| # | 重叠 | 涉及项目 | 判定 |
|---|------|---------|------|
| O1 | 代码图 | codeanalyze (AST 分析) + gbrain (持久化) | 互补: 分析 vs 存储 |
| O2 | 搜索 | kos (跨域) + eidos (统一记忆) + gbrain (RAG) | 分层: 各有侧重 |
| O3 | 任务调度 | omo (生命周期) + runtime (执行沙箱) | 分层: 管理 vs 执行 |

---

## 11. BOS URI 域映射

> BOS 声明式注册表 SSOT: `projects/agora/etc/bos-services.yaml` (100 服务, 9 域)
> 运行时调用图 (调用方→被调方): 见 [`ARCHITECTURE-DETAILED-MAP.md` §2.3](./ARCHITECTURE-DETAILED-MAP.md#23-bos-uri-运行时调用图)

| BOS 域 | 前端项目 | 核心能力 |
|--------|---------|---------|
| `bos://memory/` | kos, kronos, gbrain, sot-bridge | 记忆与事实源 |
| `bos://governance/` | omo, metaos, eidos, cockpit | 治理与律法 |
| `bos://analysis/` | ontoderive, minerva, codeanalyze | 认知与推演 |
| `bos://persona/` | sot-bridge | 人格与心智 |
| `bos://capability/` | aetherforge, runtime, bus | 能力与生态 |
| `bos://meta/` | ecos, model-driven | 元治理 |
| `bos://omo/` | omo (内省) | OMO 自有 |
| `bos://swarm/` | agora (蜂群) | 蜂群协调 |
| `bos://system/` | ecos, runtime | 系统级 |

---

## 12. 三大核心闭环

> 详细数据流/控制流/逻辑流图: 见 [`ARCHITECTURE-DETAILED-MAP.md` §4-6](./ARCHITECTURE-DETAILED-MAP.md#4-数据流-data-flow)

| 闭环 | 一句话 | 详细位置 |
|------|--------|---------|
| **知识闭环** | URL→kronos→gbrain→kos→minerva→ontoderive (摄取→存储→检索→研究→推导) | [§4.1 数据流](./ARCHITECTURE-DETAILED-MAP.md#41-url--知识库-kronos--gbrain) |
| **治理闭环** | gac.rules→M1→validate→drift→m1-sync→governance→healing (声明→校验→检测→自愈) | [§4.4 + §5.3](./ARCHITECTURE-DETAILED-MAP.md#44-治理事件--审计日志-omo--appendonlylog) |
| **执行闭环** | c2g→omo task→metaos gate→runtime KEI→evidence→晋升 (需求→任务→门控→执行→证据) | [§4.2 + §5.2](./ARCHITECTURE-DETAILED-MAP.md#42-用户需求--任务-c2g--omo) |

---

*全量功能能力地图 · 2026-06-28 · 8 域 32 能力 · 17 项目全覆盖 · 5 缺口全修复*
