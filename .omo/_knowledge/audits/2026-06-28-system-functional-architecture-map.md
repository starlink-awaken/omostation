# omostation 系统功能架构梳理 + 能力地图 + 用户场景分析

> 日期: 2026-06-28 | 范围: 全量 17 项目 (5+4+1+1 架构) | 方法: 4 组 subagent 并行扫描
> 数据源: CLI 入口 + MCP 工具 + API 端点 + 核心模块目录结构

---

## 一、功能体系分类 (8 域 32 能力)

将 17 项目的所有功能能力按用户场景归入 8 个功能域:

### 1. 知识摄取与持久化 (Knowledge Ingestion)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| 多层抓取 | kronos | `kronos fetch` | `kronos_fetch`/`kronos_browser_fetch` | 5 层抓取引擎 (HTTP→Jina→CloakBrowser), URL 路由决策 |
| 内容抽取 | kronos | `kronos extract` | `kronos_extract` | 正文/元数据抽取 |
| 知识摄取 | gbrain | `gbrain import`/`sync`/`embed` | `put_page`/`put_raw_data`/`sync_brain` | Postgres-native 知识库, 混合 RAG (向量+FTS) |
| 本体构建 | kos | `kos indexer` | `ontology_rebuild`/`run_indexer` | FTS5 中文分词 + 本体图谱 |
| 数据管线 | kairon-pipeline | (lib) | — | D-Harvest 数据管线, bus-foundation 事件 |
| 连接器同步 | iris | `iris sync` | `sync`/`sync_bidirectional` | 20+ 平台连接器 (WPS Note/Notion/...) |
| 摄取洞察 | kronos | `kronos insight` | `kronos_insight` | 摄取后洞察生成 |

### 2. 知识检索与推理 (Knowledge Retrieval)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| 跨域搜索 | kos | `kos search` | `search_knowledge`/`semantic_search` | 6 域知识语义搜索 |
| 混合 RAG | gbrain | `gbrain search`/`recall` | `search`/`query`/`search_by_image` | 向量+关键词+多查询扩展 |
| 代码理解 | codeanalyze | `codeanalyze scan` | `codegraph_search`/`ast_search` | AST/调用图/影响半径 |
| 语义搜索 | eidos | `eidos` | `eidos_list`/`eidos_validate` | 统一记忆 API + 语义索引 |
| 深度研究 | minerva | `minerva research` | `research_now`/`cross_domain_research` | 多源搜索 (DuckDuckGo+Semantic Scholar) |
| 知识推导 | ontoderive | `ontoderive derive` | `derive`/`trace`/`validate` | 事实驱动推导, 元演化 |
| 范式编译 | sophia | `sophia` | — | 状态机驱动研究方法运行时 |
| 图遍历 | gbrain | `gbrain traverse` | `traverse_graph`/`get_backlinks` | 知识图谱遍历 |

### 3. 治理与合规 (Governance)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| 治理审计 | omo | `omo governance` | `validate_task`/`check_gac_rule` | 7 项审计 (lint/test/debt/ADR/task/agora/doc) |
| 任务管理 | omo | `omo task`/`worker` | `omo_worker_dispatch`/`omo_yield_task` | 任务调度/晋升/让出 |
| 债务管理 | omo + omo-debt | `omo debt`/`omo-debt score` | `omo_debt_list`/`omo_debt_summary` | v2 生命周期感知评分 |
| 规则注册 | GaC | `gac-validate`/`gac-drift` | — | 118 规则声明式注册 + 6 层 drift |
| BOS URI | agora | `agora bos` | `resolve_bos_uri`/`mutate_resource` | 100 声明式服务路由 |
| 入口写入 | c2g | `c2g bet` | `c2g_bet` | 战略需求→OMO Planned Task |
| 审计追踪 | omo | `omo audit-rollout` | `acquire_lock`/`release_lock` | AppendOnlyLog + fcntl 锁 |
| 自愈引擎 | omo | `omo healing` | — | 修复规则 + fix-run + 趋势 |

### 4. 编排与执行 (Orchestration)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| 决策门控 | metaos | `metaos gate` | `metaos_gate` | 红/黄/绿灯判定 |
| DAG 编排 | metaos + runtime | `metaos`/`runtime agent` | `runtime_agent_run_task` | 8-Phase DAG + 断点续跑 |
| 免疫监控 | metaos | `metaos status` | `metaos_health` | 提醒→冻结→熔断三层 |
| 认知框架 | metaos | — | `metaos_morning`/`metaos_evening` | BDSK/Six Hats 动态加载 |
| 工作流引擎 | ecos | `cockpit workflow` | `workflow_run`/`workflow_validate` | loader/validator/executor + 熔断 |
| Agent 准入 | metaos | `metaos admit` | — | 准入网关 (T3.2) |
| 群体编排 | aetherforge | `aetherforge swarm` | `forge_generate_mesh` | GraphWorkflow DAG 多 Agent |

### 5. 算力与基础设施 (Compute)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| LLM 网关 | aetherforge | `aetherforge gateway generate` | `forge_generate` | 多 Provider 路由/负载均衡 |
| 算力网格 | aetherforge | `aetherforge mesh` | `forge_list_nodes`/`forge_cost_report` | 节点注册/健康/拓扑 |
| 服务注册 | runtime | `runtime matrix` | `runtime_matrix_list` | Matrix YAML 服务注册表 |
| 健康监控 | runtime | `runtime health` | `runtime_health` | 15s 心跳 + auto-heal |
| 沙箱执行 | runtime | — | `runtime_agent_execute` | KEI sys.addaudithook |
| 定时调度 | runtime | — | (Cron Service API) | FastAPI + SQLite cron |

### 6. 通信与路由 (Communication)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| MCP Hub | agora | `agora mcp` | `resolve_bos_uri`/`read_resource` | 48+ tools, 服务发现/路由/代理 |
| BOS 路由 | agora | `agora bos` | `list_bos_resources`/`get_bos_schema` | 9 域 100 服务 |
| A2A 协议 | agora | `agora instance` | `a2a_send_task`/`list_agent_cards` | Agent-to-Agent |
| 事件总线 | bus-foundation | (lib) | — | Omni-Bus 三平面 (Data/Event/Control) |
| 联邦路由 | agora | `agora converge` | — | 跨节点联邦 |

### 7. 协议与元模型 (Protocol)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| MOF 元模型 | ecos | `cockpit mof` | `ssot_check`/`ssot_derive` | M3→M2→M1 三层元模型 |
| SSB 签名链 | ecos | `cockpit ssb` | `ssot_compile` | 不可篡改认知操作记录 |
| 生命周期引擎 | model-driven | `model-driven lifecycle` | `lifecycle-create`/`lifecycle-advance` | 7 阶段 + 4 门禁 |
| Trigger 管理 | model-driven | `model-driven trigger` | `trigger-status`/`trigger-heal` | 10 种触发机制 |
| X 轴治理 | ecos + omo | `omo x-axis` | — | X1审计/X2抗熵/X3价值/X4一致 |

### 8. 自我与入口 (Self & Entry)

| 能力 | 提供者 | CLI | MCP Tools | 描述 |
|------|--------|-----|-----------|------|
| 统一入口 | cockpit | `cockpit` | 33 tools | CLI + Web (:8090) + MCP |
| 域管理 | l4-kernel | `l4-kernel` | 42 tools | 28 域注册 + KEMS 六面 |
| 健康聚合 | l4-kernel | `l4-kernel` | `l4_health_*` | 跨域全局 DASHBOARD |
| Web 控制台 | cockpit-ui | (Vite) | — | 24+ 视图组件 |
| 可观测性 | observability | (Docker) | — | Langfuse trace |
| 家庭枢纽 | family-hub | `mcp_server.py` | 6 tools | 任务游戏化 + LLM 生成 |
| 每日简报 | cockpit | `cockpit daily` | `daily_summary` | 研究简报 |

---

## 二、能力地图 (Capability Map)

```
                    ┌─────────────────────────────────────────────────────┐
                    │           L3 入口层 (cockpit + cockpit-ui)            │
                    │  CLI · Web :8090 · MCP 33 tools · 24 视图组件          │
                    └──────────────┬──────────────────────────┬───────────┘
                                 │                          │
                    ┌────────────▼────────┐    ┌────────────▼──────────┐
                    │   I0 织层 (agora)    │    │   L4 自我层 (l4-kernel) │
                    │  MCP Hub 48+ tools   │    │  42 tools · 28 域      │
                    │  BOS URI · A2A · 联邦 │    │  KEMS · 健康 · 信号    │
                    └─────────┬───┬───────┘    └───────────────────────┘
                              │   │
         ┌────────────────────┘   └─────────────────────┐
         │                                              │
┌────────▼─────────┐    ┌──────────────┐    ┌──────────▼──────────┐
│  L2 知识引擎       │    │  L2 治理面    │    │  L2 编排引擎          │
│  kairon (16 包)   │    │  omo          │    │  metaos              │
│  gbrain (70 ops)  │    │  c2g          │    │  决策门控 · DAG · 免疫  │
│  搜索/摄取/推导     │    │  审计/任务/债务 │    └─────────────────────┘
└────────┬─────────┘    └──────────────┘
         │
┌────────▼─────────┐    ┌──────────────┐    ┌──────────────────────┐
│  L1 运行时         │    │  X 算力框架    │    │  X 横切框架            │
│  runtime          │    │  aetherforge  │    │  model-driven (M0)   │
│  Matrix · KEI ·   │    │  LLM网关·网格  │    │  7阶段·门禁·Trigger    │
│  Cron · Executor  │    │  swarm        │    │  bus-foundation       │
└────────┬─────────┘    └──────────────┘    │  omo-debt · observ.   │
         │                                    │  family-hub           │
┌────────▼─────────┐                        └──────────────────────┘
│  L0 协议层         │
│  ecos             │
│  MOF·SSB·BOS URI  │
│  1196 M1 节点     │
│  34 mof-* 工具     │
└──────────────────┘
```

### 能力统计

| 维度 | 数量 |
|------|------|
| CLI 命令 (入口+子命令) | ~120+ |
| MCP 工具总数 | ~280+ |
| HTTP 端点 | ~30+ |
| 核心源文件 | ~800+ |
| M1 元模型节点 | 1315 (含 119 GacRule) |
| GaC 治理规则 | 118 |
| BOS 声明式服务 | 100 (9 域) |
| L4 管理域 | 28 |

---

## 三、用户场景分析 (6 类用户 × 场景)

### 场景 1: 人类用户日常知识管理

```
用户 → cockpit CLI/Web → kos search / gbrain search → 知识检索
     → kronos fetch → URL 抓取 → gbrain import → 持久化
     → minerva research → 深度研究 → gbrain put_page → 存储
     → iris sync → 同步到 WPS Note/Notion
```

**覆盖能力**: 知识摄取 (kronos) + 检索 (kos/gbrain) + 研究 (minerva) + 同步 (iris)
**缺口**: 无明显缺口, 闭环完整

### 场景 2: AI Agent 自治执行

```
Agent → agora MCP :7431 → resolve_bos_uri → 路由到后端
     → omo task → 获取任务 → runtime agent execute → KEI 沙箱执行
     → omo audit → 记录 → omo debt → 注册债务 (如有)
     → gac-drift → 规则校验 → git commit → mof-extract
```

**覆盖能力**: 路由 (agora) + 任务 (omo) + 执行 (runtime) + 审计 (omo) + 治理 (GaC)
**缺口**: Agent 准入 (metaos admit) 尚未在 CI 强制

### 场景 3: 战略需求→任务落地

```
用户 → c2g brainstorm → 生成 Pitch (Upstream + Appetite)
     → c2g bet → OMO Planned Task (.omo/tasks/planned/)
     → omo worker dispatch → 分配 Worker
     → metaos gate → 决策门控
     → 执行 → omo evidence → 证据收集
     → omo task complete → 晋升
```

**覆盖能力**: 需求建模 (c2g) + 任务管理 (omo) + 决策 (metaos)
**缺口**: c2g brainstorm 的 LLM 集成依赖 aetherforge gateway, 需确保可用性

### 场景 4: 代码库理解与影响分析

```
Agent → codeanalyze scan → AST + 调用图
     → codegraph_search → 符号搜索
     → codegraph_callers/callees → 影响半径
     → architecture_generate_diagram → 架构图
     → gbrain code_callers/callees → 持久化
```

**覆盖能力**: 代码分析 (codeanalyze) + 持久化 (gbrain code-intel)
**缺口**: 无, 闭环完整

### 场景 5: 治理审计与自愈

```
omo governance → 7 项审计 → 100 A+ 目标
     → gac-validate → 规则校验
     → gac-drift → drift 检测 (6 层)
     → gac-m1-sync → M1 实例同步
     → omo healing → 自愈修复
     → mof-state-bridge → .omo/tasks ↔ M1 对齐
```

**覆盖能力**: 审计 (omo) + 规则 (GaC 118) + drift (6 层) + 自愈 (omo)
**缺口**: 61 处字段漂移 (priority P0→P2, 历史数据) 未修复

### 场景 6: 家庭场景应用

```
家庭成员 → family-hub React UI → 查看 quest
     → complete_quest → 积分/等级
     → generate_smart_quests → LLM 生成个性化任务
     → cockpit-ui QuestBoard → 展示
```

**覆盖能力**: 任务游戏化 (family-hub) + LLM (aetherforge gateway) + UI (cockpit-ui)
**缺口**: family-hub 与 omo 任务系统未打通 (独立 SQLite)

---

## 四、功能覆盖度评估

### 能力密度热力图

| 功能域 | 项目数 | MCP Tools | 成熟度 | 备注 |
|--------|:------:|:---------:|:------:|------|
| 知识摄取 | 4 | ~20 | ★★★★ | kronos 5 层抓取成熟 |
| 知识检索 | 6 | ~40 | ★★★★★ | gbrain 70 ops 最完整 |
| 治理合规 | 3 | ~25 | ★★★★★ | GaC 118 规则 + 6 层 drift |
| 编排执行 | 3 | ~20 | ★★★★ | metaos DAG + runtime Executor |
| 算力基础 | 2 | ~12 | ★★★ | aetherforge CLI 已 deprecated |
| 通信路由 | 2 | ~50 | ★★★★★ | agora 48+ tools 最丰富 |
| 协议元模型 | 2 | ~35 | ★★★★★ | ecos 1315 M1 节点 |
| 自我入口 | 4 | ~85 | ★★★★ | l4-kernel 42 tools + cockpit 33 |

### 识别的功能缺口 (5 项)

| # | 缺口 | 影响 | 建议 |
|---|------|------|------|
| G1 | aetherforge CLI 已 deprecated, 但无替代 cockpit 子命令 | LLM 生成只能走 MCP | cockpit 加 `cockpit compute generate` 子命令 |
| G2 | family-hub 独立 SQLite, 未接入 omo 任务系统 | 家庭任务不受治理 | family-hub 接入 omo ingress-task |
| G3 | Agent 准入 (metaos admit) 未在 CI 强制 | 任意 Agent 可执行 | CI gate 加 admit 检查 |
| G4 | 61 处 M1↔.omo 字段漂移 (priority P0→P2) | mof-state-bridge 报告噪音 | 批量修正或调整 M1 priority 默认值 |
| G5 | minerva daemon 后台研究无 MCP 暴露 | Agent 无法调度后台研究 | minerva MCP 加 `research_schedule` |

### 识别的功能重叠 (3 项)

| # | 重叠 | 涉及项目 | 建议 |
|---|------|---------|------|
| O1 | 代码图: codeanalyze CRG vs gbrain code-intel | codeanalyze + gbrain | gbrain 持久化, codeanalyze 分析, 不重叠 (互补) |
| O2 | 搜索: kos semantic_search vs eidos nks_semantic_search vs gbrain query | kos + eidos + gbrain | kos 跨域, eidos 统一记忆, gbrain RAG (各有侧重) |
| O3 | 任务调度: omo worker_dispatch vs runtime agent_run_task | omo + runtime | omo 管理任务生命周期, runtime 管理执行 (分层) |

---

## 五、架构功能流转图

### 知识闭环 (数据→记忆→检索)

```
URL/文件 ──kronos fetch──→ 内容抽取 ──gbrain import──→ Postgres 知识库
                                                         ↓
用户查询 ──kos search──→ 语义搜索 ──gbrain query──→ 混合 RAG 结果
                                                         ↓
深度研究 ──minerva research──→ 多源搜索 ──gbrain put_page──→ 知识图谱更新
                                                         ↓
知识推导 ──ontoderive derive──→ 事实推导 ──eidos validate──→ Schema 校验
```

### 治理闭环 (规则→检测→自愈)

```
规则声明 ──gac.rules (118)──→ M1 实例 (118) ──mof-schema-validate──→ 校验 OK
       ↓                                                         ↓
drift 检测 ──gac-drift (6层)──→ 0 drift ──gac-m1-sync──→ registry↔M1 同步
       ↓                                                         ↓
omo governance ──7 项审计──→ 100 A+ ──omo healing──→ 自愈修复
```

### 执行闭环 (需求→任务→执行→证据)

```
c2g brainstorm → Pitch → c2g bet → OMO Planned Task
    ↓
omo worker dispatch → Worker 认领 → metaos gate → 决策门控
    ↓
runtime agent execute → KEI 沙箱 → 执行结果
    ↓
omo evidence → 证据收集 → omo task complete → 晋升
    ↓
omo audit → 审计记录 → gac-drift → 规则校验
```

---

## 六、总结

omostation 是一个功能密集的多项目融合工作区, 17 个项目提供 ~280+ MCP 工具、~120+ CLI 命令、~30+ HTTP 端点, 覆盖 8 个功能域 32 项能力。核心闭环 (知识/治理/执行) 均已打通, 主要缺口集中在边缘场景 (family-hub 治理接入、aetherforge CLI 替代、Agent 准入 CI 强制)。

功能体系完整度: **8/8 域全覆盖, 32/32 能力有实现, 5 项缺口 + 3 项重叠 (可接受)**

---

*功能架构梳理报告 · 2026-06-28 · 4 组 subagent 并行调研 · 17 项目全覆盖*
