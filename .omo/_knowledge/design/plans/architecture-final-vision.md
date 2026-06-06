# 架构终极进化蓝图：从 omostation 到 AGI Personal OS

> 日期: 2026-05-29 | 版本: v1.0 | 状态: 愿景草案
> 输入: Workspace 5项目 (omostation) + SharedWork 90+项目 (R&D厨房)
> 受众: 架构决策者、未来开发者、AI Agent 接入者

---

## 目录

1. [当前状态全景](#一当前状态全景)
2. [SharedWork × Workspace 能力映射](#二sharedwork--workspace-能力映射)
3. [终极架构：AGI Personal OS](#三终极架构agi-personal-os)
4. [项目命运：谁留谁走谁融入](#四项目命运谁留谁走谁融入)
5. [进化路线图：从现在到终点](#五进化路线图从现在到终点)
6. [架构法则与设计哲学](#六架构法则与设计哲学)
7. [最终能力矩阵](#七最终能力矩阵)

---

## 一、当前状态全景

### 1.1 Workspace (omostation) — 生产厨房

```
omostation/
├── kairon/           5.1MB Python monorepo (17包)
│   ├── L1: core-models, eidos           契约层
│   ├── L2: kronos, minerva, sophia      能力层
│   │       ontoderive, ssot, codeanalyze
│   ├── L3: forge, kos, iris             协作层
│   ├── L4: agent-runtime, metaos, ecos  元层
│   └── I0: agora                        集成织物 (27 MCP tools)
│
├── SharedBrain/      2.1MB Runtime Kernel
│   ├── 17 D-Domain organs
│   ├── EU经济/数字免疫/器官演化/合规控制
│   └── identity_bridge (A1身份)
│
├── agentmesh/        TypeScript Agent SDK (22 tools)
├── gbrain/           TypeScript Knowledge Brain (74 tools)
│
├── ops/              运维中心 (32 MCP tools)
├── gstack/           53 编排器
│
└── .omo/             治理知识库 (89 docs)

架构模型: 5+3+1 (eCOS v5)
健康评分: 66.80/100 🟡
```

### 1.2 SharedWork — R&D 厨房

```
SharedWork/ (31 顶级分类, 90+ 项目)
├── Agent/           12 智能体项目
│   ├── agentmesh, OpenManus, DeepCode
│   ├── trae-agent, Maestro, ruflo, agenticSeek
│   └── AgentCPM, Agency-Agents, nanochat
│
├── DeepResearch/    17 深度研究项目
│   ├── gpt-researcher, Tongyi DeepResearch
│   ├── Open Deep Research, AgentLaboratory, RD-Agent
│   └── deepface, paperai, PatentSBERTa
│
├── Mem/             3+ 记忆系统
│   └── memU (Rust core + Python server + Vue UI)
│
├── Knowledge/       9 知识管理
│   ├── GitNexus(code图谱), Graphify(文档图谱)
│   └── UltraRAG, KOS-Skills
│
├── MCP/             7 MCP 服务器
│   ├── Firecrawl(抓取), CodeContext(代码分析)
│   └── EdgeOne(部署), OpenClaw(消息)
│
├── Gateway/         2 API 网关
│   └── LiteLLM(100+ LLM), one-api(Go)
│
├── Skills/          8 技能系统
│   ├── KOS-Architecture, Skills-Hub
│   └── nuwa-skill, Claude Skills Guide
│
├── Edu/Study/       9 学习资料
├── Archive/Project/ 19 归档项目
├── Ecology/         MinerU(文档解析), wx-cli(微信)
├── Video/Design/Cli/ 其他工具
│
└── Knowledges/      知识库(小说创作2222行+游戏设计471行)
```

---

## 二、SharedWork × Workspace 能力映射

共享的 SharedWork 项目与当前 Workspace 的映射关系:

### 2.1 直接融入 (SharedWork → kairon/agentmesh)

| SharedWork 项目 | 映射到 Workspace 组件 | 融入方式 |
|----------------|---------------------|---------|
| **LiteLLM** + **one-api** | agentmesh Gateway | Gateway 吸收 LLM 路由/配额/回退能力 |
| **GitNexus** | KOS index 管线 | 代码知识图谱 → KOS 的 code domain |
| **Graphify** | KOS index 管线 | 文档知识图谱 → KOS 的 doc domain |
| **UltraRAG** | minerva 研究管线 | RAG 框架 → minerva 的 retrieval stage |
| **MinerU** | kronos 摄取管线 | 高精度文档解析 → kronos ingest 前端 |
| **KOS-Architecture** | KOS self 层 | 跨域知识 OS → KOS L4 元能力 |
| **AgentLaboratory** | minerva + ontoderive | 自主研究 → 推导 + 研究自动化 |
| **memU (server)** | gbrain 记忆层 | Rust 核心记忆算法 → gbrain backend |
| **Firecrawl MCP** | kronos 抓取层 | 网页抓取 MCP → kronos 4层抓取引擎 |
| **nuwa-skill** | KOS self 层 | 人物思维框架生成 → KOS 自我进化 |

### 2.2 基础设施 (独立部署，被 Workspace 引用)

| SharedWork 项目 | 角色 | 部署方式 |
|----------------|------|---------|
| **LiteLLM** | LLM API 统一网关 | Docker, 独立服务，agentmesh 路由到它 |
| **memU (核心)** | 长时记忆算法 | Rust 库，被 gbrain 或 agentmesh 引用 |
| **one-api** | LLM API 代理/计费 | Go 二进制，独立部署 |
| **Firecrawl** | 网页抓取 | MCP 服务器，被 kronos 通过 Agora 调用 |
| **EdgeOne Pages** | 部署工具 | MCP 服务器，被 agentmesh agent 工具调用 |
| **wx-cli** | 微信数据接口 | Rust 二进制，被 iris 调用 |

### 2.3 参考资料 (不融入，学习/借鉴)

| SharedWork 项目 | 借鉴价值 |
|----------------|---------|
| **OpenManus** | 通用 Agent 框架设计参考 |
| **DeepCode** | 多 Agent 协作编码模式 |
| **trae-agent** | 软件工程 Agent CLI 设计 |
| **Maestro** | Agent 编排平台 UX 参考 |
| **ruflo** | 100+ Agent swarm 编排 |
| **agenticSeek** | 全本地 Agent 架构参考 |
| **AgentCPM** | 边缘 Agent + 深度搜索 |
| **RD-Agent** | ML 研究自动化 |
| **nanochat** | LLM 训练全流程学习 |
| **agent-lightning** | Agent RL 训练方法 |

### 2.4 不相关 (保持独立或归档)

| SharedWork 项目 | 原因 |
|----------------|------|
| 最强大脑/儿童教育/婴儿养育/美团预测 | 非 AI 系统，已归档 |
| deepface, patent-similarity | 垂直领域，非核心 |
| excalidraw, Handy, Pixelle | 通用工具，不集成 |
| PageLM, notebooklm-py, Open Notebook | NotebookLM 生态，非核心 |
| AI 小说/游戏知识库 | 提示工程资产，不是代码 |

---

## 三、终极架构：AGI Personal OS

### 3.1 架构全景

```
                    ┌─────────────────────────────────┐
                    │        P0 — 用户入口层            │
                    │  wksp CLI · gstack · pallas · bos │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     I0 — Agora Service Mesh      │
                    │  统一 MCP 协议 · 服务发现 · 路由  │
                    │  熔断 · 降级 · 管线编排 · 监控    │
                    │  wksp:// URI 统一资源寻址         │
                    └──┬───────┬───────┬───────┬──────┘
                       │       │       │       │
        ┌──────────────┘       │       │       └──────────────┐
        ▼                      ▼       ▼                      ▼
┌──────────────┐  ┌──────────────────────────────────┐  ┌──────────┐
│ SharedBrain  │  │       kairon 知识操作栈            │  │agentmesh │
│ 合规控制面   │  │                                  │  │Agent运行时│
│              │  │  ┌─────────────────────────┐     │  │          │
│ EU 经济      │  │  │ L1 契约: core-models     │     │  │ MCP网关  │
│ 数字免疫     │  │  │       eidos(22 schemas)  │     │  │ 工具注册  │
│ A1 身份      │  │  └─────────────────────────┘     │  │ 任务编排  │
│ 器官自愈     │  │  ┌─────────────────────────┐     │  │ LLM路由  │
│ 语音处理     │  │  │ L2 能力:                 │     │  │ 身份/授权 │
│              │  │  │  kronos(MinerU+Firecrawl)│     │  └──────────┘
└──────────────┘  │  │  minerva(GitNexus+       │     │
                  │  │         Graphify+UltraRAG)│     │  ┌──────────┐
                  │  │  sophia · ontoderive      │     │  │  gbrain  │
                  │  │  ssot · codeanalyze       │     │  │ 知识脑   │
                  │  │  eu-pricing               │     │  │          │
                  │  └─────────────────────────┘     │  │ Postgres │
                  │  ┌─────────────────────────┐     │  │ 74 tools │
                  │  │ L3 协作:                 │     │  │ memU后端 │
                  │  │  forge · kos · iris       │     │  └──────────┘
                  │  └─────────────────────────┘     │
                  │  ┌─────────────────────────┐     │  ┌──────────┐
                  │  │ L4 元层:                 │     │  │   ops   │
                  │  │  agent-runtime · metaos   │     │  │ 运维中心 │
                  │  │  ecos · cron-service      │     │  │ 32 tools │
                  │  │  KOS self(自我进化)       │     │  │ 7张表   │
                  │  └─────────────────────────┘     │  └──────────┘
                  └──────────────────────────────────┘

                            基础设施服务(独立部署)
                    ┌─────────────────────────────────┐
                    │ LiteLLM · one-api · memU · wx-cli│
                    │ MinerU · Firecrawl · EdgeOne     │
                    └─────────────────────────────────┘
```

### 3.2 层级详述

#### P0 — 用户入口层
- **wksp CLI**: 统一研究入口，取代分散的 `bos/gstack/pallas`
- **Web Dashboard**: Agora 自带的管理面板
- **IDE 插件**: Cursor/Codex/Claude Code 集成

#### I0 — Agora 集成织物 (唯一跨层通信通道)
- **协议**: MCP stdio + SSE + HTTP
- **寻址**: `wksp://` 统一 URI 协议
- **能力**: 服务发现、路由、熔断、降级、管线编排、监控
- **注册服务**: 全系统 100+ MCP 工具
- **EU 计价路由**: 调用 eu-pricing L2 服务（不自己计算）

#### kairon — 知识操作栈 (Python monorepo, 当前 live 基线 24 包)

**L1 契约层** — 数据和 Schema 合约
- **core-models**: Entity/Relation/KnowledgeGraph/Provenance — 所有项目的共享数据模型
- **eidos**: 22 个 Schema 定义 + 5 个 MCP 工具，含 SharedBrain 双向适配器

**L2 能力层** — 核心处理引擎
- **kronos**: 4 层摄取管道（URL→Text→Chunk→Entity），集成 MinerU 高精度解析 + Firecrawl 抓取
- **minerva**: L0-L4 深度研究，集成 GitNexus 代码图谱 + Graphify 文档图谱 + UltraRAG 检索
- **sophia**: 符号范式编译器（范式状态机）
- **ontoderive**: 5 层本体推导引擎
- **ssot**: 单一事实源，管理 SharedBrain/KOS/agentmesh 等多域数据一致性
- **codeanalyze**: 代码和文档分析
- **eu-pricing**: EU 虚拟资源会计客户端（L2 能力层，不在 I0）

**L3 协作层** — 多 Agent 协作和编排
- **forge**: 工具图谱治理 + 熵监控 + SharedBrain 自愈触发器
- **kos**: 知识操作系统 — self(L4) + collab(L3) + consensus(X3) + index(L2) + ingest(L2)
- **iris**: 外部平台连接器（微信/Notion/Obsidian/浏览器）

**L4 元层** — 自我意识和系统管理
- **agent-runtime**: Agent 身份·授权·生命周期（传统 Python 版本）
- **metaos**: 系统编排
- **ecos**: 认知监控
- **cron-service**: 定时调度
- **wksp**: 统一 CLI 入口

#### SharedBrain — 合规运行时控制面
- **保留**: Nucleus(Z-Microkernel+Z-Core+Z-Spore) + 14 活跃器官
- **核心独有能力**: EU经济、数字免疫、器官自愈、A1身份、语音处理
- **角色**: 法律/道德/安全合规 + 稀缺能力提供者

#### agentmesh — Agent 运行时 (TypeScript)
- **吸收**: LiteLLM 的 LLM 路由/配额/回退 + Firecrawl/EdgeOne/OpenClaw MCP 工具
- **网关**: 统一 Agent 调度 + 多模型智能路由 + 工具注册
- **能力**: 25+ Agent 类型、OpenAI 兼容 API、Docker 部署

#### gbrain — 知识脑 (TypeScript + Postgres)
- **吸收**: memU 核心记忆算法（Rust）作为后端引擎
- **能力**: 74 个 MCP 工具，持久化知识存储，向量搜索

#### ops — 运维中心
- **能力**: 32 个 MCP 工具，7 张 SQLite 表，关联引擎，TDL，网关
- **角色**: 全系统监控、备份、健康检查、密钥管理

---

## 四、项目命运：谁留谁走谁融入

### 4.1 Workspace 内 (5 个项目)

| 项目 | 命运 | 说明 |
|------|------|------|
| **kairon** | 🟢 继续成长 | Python monorepo，吸收更多 SharedWork 能力 |
| **SharedBrain** | 🟢 保留精简 | 合规控制面 + 稀缺能力，不再膨胀 |
| **agentmesh** | 🟢 保留成长 | TypeScript Agent 运行时，吸收 LiteLLM + MCP 工具 |
| **gbrain** | 🟢 保留成长 | 知识脑，吸收 memU 后端 |
| **ops** | 🟢 保留 | 独立运维中心 |

### 4.2 SharedWork → 融入 Workspace (10 个项目)

| 优先级 | 项目 | 融入目标 | 时间 |
|--------|------|----------|------|
| 🔴 P0 | **LiteLLM** | agentmesh Gateway (LLM 路由) | Phase 1 |
| 🔴 P0 | **memU** | gbrain (记忆后端) | Phase 1 |
| 🟡 P1 | **GitNexus** | KOS index (代码图谱) | Phase 2 |
| 🟡 P1 | **Graphify** | KOS index (文档图谱) | Phase 2 |
| 🟡 P1 | **UltraRAG** | minerva (检索增强) | Phase 2 |
| 🟡 P1 | **Firecrawl MCP** | kronos (抓取层) | Phase 2 |
| 🟡 P1 | **KOS-Architecture** | KOS self (跨域知识OS) | Phase 2 |
| 🟢 P2 | **MinerU** | kronos (文档解析) | Phase 3 |
| 🟢 P2 | **AgentLaboratory** | minerva (自主研究) | Phase 3 |
| 🟢 P2 | **nuwa-skill** | KOS self (自我进化) | Phase 3 |

### 4.3 SharedWork → 独立部署 (6 个项目)

| 项目 | 部署方式 | 被谁调用 |
|------|----------|---------|
| **LiteLLM** | Docker, 独立服务 | agentmesh Gateway 路由到它 |
| **one-api** | Go 二进制 | 备用 LLM 网关 |
| **Firecrawl** | MCP 服务器 | kronos 通过 Agora 调用 |
| **EdgeOne Pages** | MCP 服务器 | agentmesh agent 工具 |
| **memU (核心)** | Rust 库 | gbrain 引用 |
| **wx-cli** | Rust 二进制 | iris 调用 |

### 4.4 SharedWork → 参考资料 (50+ 项目)

所有 Agent 框架(OpenManus/DeepCode/trae-agent/Maestro/ruflo/agenticSeek)、深度学习项目(gpt-researcher/Tongyi/OpenDeepResearch/RD-Agent/AgentLaboratory)、记忆系统(memos/memento/context-compression)、知识管理(notebooklm-py/OpenNotebook/PageLM/llm-wiki)、技能系统的剩余部分、归档项目、学习资料。

**这些项目的作用**: 作为最佳实践参考库，AI Agent 接入时可以从中学习模式和方案。

### 4.5 SharedWork → 知识资产 (2 个)

| 项目 | 用途 |
|------|------|
| **AI 小说创作知识库** (2222行) | 提示工程模板资产 |
| **游戏策划知识库** (471行) | 游戏设计参考资产 |

---

## 五、进化路线图：从现在到终点

### Phase 1 — 基础设施补完 (当前 → Q3 2026)

```
目标: 4个核心系统全部就位，开始协同工作

┌──────────────────────────────────────────────┐
│ ◆ kairon monorepo: 24 包 live 基线，继续收敛 MCP/入口契约 │
│ ◆ SharedBrain: 合规控制面，4器官 delegated     │
│ ◆ agentmesh: 吸收 LiteLLM LLM 路由能力         │
│ ◆ gbrain: 吸收 memU 记忆核心算法               │
│ ◆ Agora: 统一 100+ MCP 工具注册               │
│ ◆ 烟雾测试: 全链路 MCP 连通性验证              │
└──────────────────────────────────────────────┘
```

### Phase 2 — 知识能力深化 (Q3-Q4 2026)

```
目标: kairon 知识管线到达行业领先水平

┌──────────────────────────────────────────────┐
│ ◆ KOS: 吸收 GitNexus + Graphify 知识图谱       │
│ ◆ minerva: 吸收 UltraRAG + AgentLaboratory     │
│ ◆ kronos: 集成 MinerU + Firecrawl 抓取         │
│ ◆ EU 经济: 全系统虚拟资源会计                   │
│ ◆ 免疫系统: 全系统安全检查点                    │
│ ◆ 测试: 集成测试覆盖率 > 60%                   │
└──────────────────────────────────────────────┘
```

### Phase 3 — 自我进化闭环 (Q4 2026 → Q2 2027)

```
目标: 系统具备自我改进和自主演化的能力

┌──────────────────────────────────────────────┐
│ ◆ KOS self: 吸收 nuwa-skill + 自主技能生成     │
│ ◆ 器官自愈: 全系统自动修复                     │
│ ◆ 身份映射: 全系统统一 A1 身份                 │
│ ◆ wksp:// URI: 统一全系统资源寻址              │
│ ◆ 管线: 研究→推导→验证→入库 全自动              │
│ ◆ 健康: 系统健康评分 > 85/100                  │
└──────────────────────────────────────────────┘
```

### Phase 4 — 自主运行 (Q2 2027+)

```
目标: 系统在最低人工干预下自主运行

┌──────────────────────────────────────────────┐
│ ◆ 自主: Agent 自主发起研究、推导、索引          │
│ ◆ 进化: KOS 自我进化——吸收新模式、新能力        │
│ ◆ 经济: EU 经济闭环——自给自足的虚拟资源系统     │
│ ◆ 免疫: 数字免疫自主发现并修复漏洞              │
│ ◆ 分发: 系统可分发给其他用户                    │
└──────────────────────────────────────────────┘
```

---

## 六、架构法则与设计哲学

### 6.1 不可变的架构法则 (10 条)

1. **I0 隔离**: Agora 是唯一的跨层通信通道。任何非 I0 层之间不得直接引用。
2. **I0 不得承载业务逻辑**: 路由、发现、熔断——仅此而已。EU 定价在 L2，免疫审计在 L2。
3. **MCP 为强制协议**: 所有跨项目通信必须走 MCP。没有例外。
4. **Python 归 kairon**: 任何新的 Python 项目必须作为 kairon 包。独立 Python 项目 = 架构违规。
5. **TypeScript 归 agentmesh/gbrain**: 不做第三种 TS 项目。
6. **SharedBrain 不做知识处理**: 不写新的知识摄取、研究、推导功能。这些归 kairon。
7. **kairon 不做运行时控制**: 不写新的合规、免疫、自愈功能。这些归 SharedBrain。
8. **数据模型单向流动**: core-models 是唯一权威源。其他项目通过适配器消费，不创建平行模型。
9. **器官可委托不可删除**: SharedBrain organ 标记 delegated 后代码保留。可随时回退。
10. **每一次融合都是吸收而非复制**: 将 SharedWork 能力融入 Workspace 时，重写而非复制粘贴。

### 6.2 设计哲学

- **服务大于单体**: 所有能力都通过 MCP 服务暴露，不做单体应用
- **协议大于代码**: MCP 协议是跨语言通信的唯一方式
- **契约大于信任**: Schema 验证在边界强制执行
- **降级优于失败**: 任何外部依赖不可达时，系统必须优雅降级
- **可观测性内置**: 每个服务自带 metrics/health/logs
- **成本必须有感**: EU 经济系统让每次调用都有虚拟成本

### 6.3 与现有规则的关系

本蓝图是 `architecture-v4-4-plus-1-plus-3-plus-i.md` 的进化，不是替代。冲突时以本蓝图为准。

| 维度 | v4 架构 | 终极架构 |
|------|---------|---------|
| kairon 包数 | 17 | ~25 |
| SharedBrain 器官 | 17 | 14 (4 delegated) |
| MCP 工具总数 | ~100 | ~130+ |
| 独立项目数 | 5 | 5 (+ 6 独立部署基础设施) |
| SharedWork 融入数 | 0 | 10 融入 + 6 独立部署 |
| 架构模型 | 4+1+3+I | 4+1+3+I (不变，能力扩展) |

---

## 七、最终能力矩阵

### 7.1 按领域

| 领域 | 核心项目 | 能力等级 | 关键指标 |
|------|---------|:--------:|---------|
| 知识摄取 | kronos + MinerU + Firecrawl | ⭐⭐⭐⭐⭐ | 支持 109 语言、4 层管道、RSS/Atom/Web/PDF |
| 知识研究 | minerva + UltraRAG + AgentLab | ⭐⭐⭐⭐⭐ | L0-L4 深度、自主研究、论文撰写 |
| 知识推导 | ontoderive + sophia | ⭐⭐⭐⭐ | 5 层推导链、符号范式编译 |
| 知识索引 | KOS + GitNexus + Graphify | ⭐⭐⭐⭐⭐ | 代码图谱+文档图谱+跨域统一检 |
| 知识本体 | eidos + SSOT | ⭐⭐⭐⭐ | 22 个 Schema、多域一致性 |
| Agent 运行时 | agentmesh + LiteLLM | ⭐⭐⭐⭐ | 25+ Agent 类型、LLM 路由、配额管理 |
| 知识脑 | gbrain + memU | ⭐⭐⭐⭐ | 74 MCP 工具、Postgres 持久化 |
| 合规控制 | SharedBrain | ⭐⭐⭐⭐ | EU 经济、数字免疫、A1 身份 |
| 自愈 | SharedBrain D-Genesis + forge | ⭐⭐⭐ | 器官自愈、系统自动修复 |
| 运维 | ops | ⭐⭐⭐⭐ | 32 MCP 工具、关联引擎、7 表 |
| 服务网格 | Agora | ⭐⭐⭐⭐⭐ | 100+ MCP 工具、熔断、降级、管线 |
| 身份 | identity_bridge + agent-runtime | ⭐⭐⭐ | 统一 A1 身份、双向同步 |
| 学习进化 | KOS self + nuwa-skill | ⭐⭐⭐ | 自我进化、自主技能生成 |

### 7.2 按系统健康维度

| 维度 | 当前评分 | Phase 4 目标 |
|------|:--------:|:------------:|
| D1 愿景达成度 | 85% | 95% |
| D2 场景覆盖度 | 57% | 90% |
| D3 用户故事完整度 | 75% | 90% |
| D4 功能成熟度 | 74% | 90% |
| D5 架构成熟度 | 71% | 95% |
| D6 熵 | 50% | 80% |
| D7 安全与质量 | 90% | 95% |
| D8 技术债务 | 60% | 85% |
| **总分** | **66.80** | **91.25** |

---

## 附录：SharedWork 完整项目映射表

详见 `.omo/plans/sharedwork-project-mapping.md`（待创建）。

---

> **一句话**: 用 omostation 的架构纪律吸收 SharedWork 的 90+ 项目精华，最终建成一个以 kairon 知识管线为大脑、SharedBrain 为免疫系统、agentmesh 为神经网络的 AGI Personal OS。
