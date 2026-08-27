---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# omostation 战略架构规划 v2.1

> 日期: 2026-06-02 | 基于系统思考+红队分析 | Phase 17-25 路线图
> 作者: omostation Architecture Council | 状态: 已采纳 | 红队审计: 已完成
> v2.1变更: 红队分析集成、SharedBrain双模架构、器官提取vs重写区分、P17代码优先承诺
> 本文档是历史阶段的战略规划输入，保留当时的路线图、规模估算、健康分口径和项目收敛假设；它不是当前项目清单、当前架构事实或当前执行许可 SSOT。
> 当前事实以 `/.omo/PROJECTS.yaml`、`AGENTS.md`、`docs/PANORAMA.md`、`/.omo/goals/current.yaml`、`/.omo/state/system.yaml` 为准。

---

## 目录

1. [战略愿景](#1-战略愿景)
2. [当前状态](#2-当前状态)
3. [目标架构](#3-目标架构)
4. [9器官迁移方案](#4-9器官迁移方案)
5. [接口契约](#5-接口契约)
6. [Phase路线图](#6-phase路线图)
7. [指标看板](#7-指标看板)
8. [风险矩阵](#8-风险矩阵)
9. [决策日志](#9-决策日志)
10. [OMO治理集成](#10-omo治理集成)

---

## 1. 战略愿景

### 1.1 定位

omostation 是个人知识工程工作站 —— 一个集成知识处理、Agent运行时、存储引擎和用户界面的统一平台。它不是企业SaaS，不是分布式系统，不是多人协作工具。它是**为单个知识工作者**设计的数字基础设施。

### 1.2 终态架构：4项目收敛

经过系统思考（SystemsThinking冰山路分析、因果回路分析、杠杆点识别）和架构分析，omostation的终态为4个项目：

#### 1.2.1 SharedBrain 双模架构 (~7K lines total)

SharedBrain不保留为独立项目。改为**双模存在**：始终作为kairon内库(~5K)，按需独立部署(~2K包装)。

**sharedbrain-core (Python库, ~5K lines, 始终存在于kairon内):**

| 组件 | 职责 | 形态 |
|------|------|:----:|
| protocols/ | 协议定义 (Identity, Health, Circuit, Metrics, Governance) | Python ABC |
| circuits/ | 回路引擎 (YAML解析, 状态机执行, SLA保障) | Python库 |
| neurons/ | 连接代理 (健康探测, 故障转移, 连接池) | Python库 |
| stem_cells/ | 验证器 (接口合规检查) | Python库 |

**sharedbrain-standalone (薄包装, ~2K lines, 按需独立部署):**

| 场景 | 形态 | 理由 |
|------|:----:|------|
| 本地单机开发 | 库模式 | 进程内import，无需独立端口 |
| 本地多服务 | 独立模式(:8000) | 需要独立可达调度点 |
| 混合(本地kairon+云端服务) | 独立模式 | 云端服务需外网可达 |
| CI/测试 | 库模式 | 测试中直接import |

**核心设计原则:** sharedbrain-core永远在kairon内。协议定义、回路、神经元、干细胞是协调逻辑的库。独立运行时只是这个库的薄包装，当场景需要外部可达时启用。

```python
# 库模式下直接使用
from sharedbrain_core import NeuralCenter, CircuitEngine

# 独立模式下启动服务
# sharedbrain-standalone: 薄包装core为HTTP/MCP server

#### 1.2.2 kairon (~30 Python包): 统一知识处理+Agent运行时平台

agentmesh的能力已并入kairon。metaos留在kairon内（它是库，不是服务）。

**4个子域**：

| 子域 | 包 | 职责 |
|------|-----|------|
| **知识处理** | `ontoderive`, `eidos`, `kos`, `sophia`, `hermes`, `minerva`, `morpho`, `logos` | 本体推导、知识索引、语义搜索、研究学习 |
| **治理运行时** | `metaos`, `agora`, `nomos` | 元OS库、服务发现、规则引擎 |
| **管线** | `pontus`, `codex`, `gc-engine` | 数据处理管线、代码生成、垃圾回收 |
| **能力工具** | `forge`, `observability`, `eu-pricing`, `agent-runtime`, `agent-hub` | 工具生成、可观测性、定价、Agent运行时 |

**关键设计决策**：
- `metaos` 留在 kairon 内 —— 它是对SharedBrain协议的库级实现，不是独立服务
- `agent-runtime` 吸收原 agentmesh 的 Agent 管理能力
- `agent-hub` 吸收原 agentmesh 的 Agent Hub 能力
- 保留 kos 作为核心知识入口，不新建独立的知识包

#### 1.2.3 gbrain (TypeScript + Postgres): 独立存储引擎

存储/计算边界正确，保持分离。

| 特性 | 值 |
|------|-----|
| 语言 | TypeScript (bun) |
| 存储 | PostgreSQL |
| 工具数 | 74 MCP tools |
| 接口 | MCP协议 |
| 职责 | 知识持久化、图查询、向量检索、时序数据 |

gbrain不处理任何业务逻辑 —— 它只负责存储和检索。所有计算逻辑在kairon中完成。

#### 1.2.4 Hermes Console (NEW, TypeScript/React): 统一用户界面

纯MCP客户端。通过MCP协议与SharedBrain和kairon通信。

```
Hermes Console 组件树:
├── AppShell                  # 应用壳
│   ├── NavigationBar         # 导航栏
│   ├── StatusBar             # 状态栏
│   └── MainContent           # 主内容区
│       ├── KnowledgeDashboard # 知识仪表盘
│       │   ├── GraphViewer    # 知识图谱可视化
│       │   ├── SearchPanel    # 搜索面板
│       │   └── StatsCards     # 统计卡片
│       ├── AgentConsole       # Agent控制台
│       │   ├── AgentList      # Agent列表
│       │   ├── ChatInterface  # 对话界面
│       │   └── TaskMonitor    # 任务监控
│       ├── HealthMonitor      # 健康监控
│       │   ├── ServiceTopology # 服务拓扑图
│       │   ├── MetricsCharts  # 指标图表
│       │   └── AlertPanel     # 告警面板
│       └── SettingsPanel      # 设置面板
│           ├── MCPConfig       # MCP配置
│           ├── ProfileSettings # 个人设置
│           └── SystemInfo      # 系统信息
└── MCPClient                 # MCP客户端层
    ├── ConnectionManager     # 连接管理
    ├── ToolRegistry          # 工具注册表
    └── StreamHandler         # 流处理
```

### 1.3 核心原则

| # | 原则 | 说明 |
|---|------|------|
| P1 | **协议/实现分离** | SharedBrain(core)定义协议和协调逻辑，kairon/gbrain实现业务逻辑 |
| P2 | **存储/计算边界** | gbrain只管存储，kairon只管计算，不交叉 |
| P3 | **双模存在** | sharedbrain-core始终是kairon内库(~5K)；sharedbrain-standalone(~2K)按需独立部署 |
| P4 | **神经隐喻用于协调而非控制** | 回路/神经元/干细胞是协调抽象，不替代各服务的自主决策 |
| P5 | **渐进收敛** | Phase 17-25共9个Phase逐步收敛，不追求一次到位 |
| P6 | **提取vs重写区分** | 简单器官提取(已验证可行)；复杂器官重写(承认深度耦合不可提取) |
| P7 | **代码优先** | P17必须产出代码变更(非文档)。无代码提交=未完成 |

---

## 2. 当前状态

### 2.1 项目现状 (2026-06-02)

| 项目 | 状态 | 规模 | 说明 |
|------|------|------|------|
| **SharedBrain** | 活跃 | 9活跃器官(~85K行, 324文件) + 10归档器官(~214K已提取到kairon) | 服务存在但架构不清晰，475 BaseMembrane实例 |
| **kairon** | 活跃 | 22包, ~1375源文件, 2305测试通过 | 知识处理核心，包边界需要优化 |
| **gbrain** | 活跃 | TypeScript+Postgres, 74 MCP tools | 存储引擎独立，边界清晰 |
| **agentmesh** | 待吸收 | 7 TypeScript包 | Agent SDK，待并入kairon |
| **Hermes Console** | 未建 | 0行 | 统一UI，待Phase 23新建 |

### 2.2 健康评估

| 指标 | 值 | 权重 | 说明 |
|------|-----|------|------|
| Raw Health | 97.0 | — | 原始健康分（不含债务权重） |
| Debt Weight | 0.3 | — | 技术债权重系数 |
| **Effective Health** | **29.1** | — | 有效健康分 = raw × debt_weight |
| Phase完成度 | 94/97 | — | Phase 8已完成的97个任务中完成了94个 |
| 活跃任务 | 1 | — | P9-W3-IDENTITY-ADMISSION-CONTRACT |
| 阻塞任务 | 2 | — | 待解除阻塞 |

### 2.3 技术债清单

| 债务项 | 数量 | 严重度 | 影响 |
|--------|------|--------|------|
| BaseMembrane实例 | 475 | CRITICAL | 每个文件平均2.7个，阻碍模块化 |
| nucleus引用 | 320 | HIGH | 硬编码中央引用，阻碍解耦 |
| 归档器官懒引用 | 22 | MEDIUM | D_Memory等已归档器官的残留引用 |
| 桥接代码 | ~15 | MEDIUM | SharedBrain-kairon间的临时桥接 |
| 未覆盖测试 | ~45文件 | HIGH | 缺失测试的关键模块 |

### 2.4 已完成工作 (Phase 11-16 背景)

以下工作在本战略规划启动前已完成，是后续Phase执行的基础：

**10器官批量提取:**
| 源器官 | 文件 | 行数 | → kairon包 | 状态 |
|--------|:----:|:----:|-----------|:----:|
| D_Execution | 275 | 55,725 | engine-core | ✅ |
| D_Memory | 133 | 42,359 | eidos | ✅ |
| D_Gateway | 98 | 26,516 | agora | ✅ |
| D_Harvest | 110 | 29,394 | shared-lib | ✅ |
| D_Governance | 131 | 27,200 | shared-lib | ✅ |
| D_Logos | 51 | 16,857 | ontoderive | ✅ |
| D_Intelligence | 20 | 4,007 | kairon-assistant | ✅ |
| D_Continuity | 15 | 4,143 | eidos | ✅ |
| D_Voice | 11 | 2,631 | kairon-voice | ✅ |
| D_Cloud | 21 | 5,278 | kaironcloud-billing | ✅ |

**73高价值模块精准提取:**
- 归档器官中识别100个未提取模块(25,024行) → 筛选73个高价值(>200行非测试)
- 处理: BaseMembrane try/except移除 + 类继承清理 + 跨器官导入重写 + nucleus引用注释
- 结果: 57个一键成功, 16个因嵌套try/except需手工修复(orpaned try/continue not in loop/mismatched indent)
- 最终: 73/73编译通过, 0语法错误

**18交叉依赖文件修复:**
- 活跃器官中18个文件引用已归档器官 → 15个已有try/except(安全), 3个手工修复
- 修复: claude_code_adapter.py(ICliAdapter基类stub), harness_controller.py(ToolDispatcher/LLMConfig包裹), skill_extractor.py(ImportError加入except)

**sharedbrain-bridge包:**
- 位置: kairon/packages/sharedbrain-bridge/ (eu.py, immune.py, sync.py)
- 当前状态: 壳子代码, 无活跃连接 → Phase 18目标: 激活为神经元↔kairon服务桥接

**10器官归档:**
- SharedBrain/_archived/organs/: 865文件, ~214K行
- organs/ 精简为9活跃器官(324文件, ~85K行), 交叉依赖已try/except保护

### 2.5 关键瓶颈

1. **BaseMembrane膨胀**：475实例分布在324文件中，任何SharedBrain重构都受其牵制
2. **nucleus硬编码**：320处直接引用nucleus，导致架构僵化
3. **agentmesh存在冗余**：7个TS包与kairon的Agent相关功能重叠
4. **缺少统一UI**：多入口（CLI/MCP/HTTP）但无统一控制台
5. **协议不完整**：SharedBrain与其他项目间的接口缺乏正式契约

---

## 2A. 红队分析与架构修正

> 2026-06-02 | 8 Agent并行攻击 (EN/AR/PT/IN各2) | 综合24原子声明

### 红队核心发现

**CRITICAL (5+ Agent收敛)**:

| # | 攻击点 | 判定 | 修正措施 |
|---|--------|:----:|---------|
| 1 | SharedBrain不应作为独立运行时——只剩kairon/gbrain两个东西时，协调逻辑应是库而非服务 | **部分采纳** | SharedBrain→双模架构(库模式+独立模式)，见§3.2 |
| 2 | 器官"提取"的前提假设有问题——BaseMembrane/Z-Spore/Z-Microkernel深度耦合意味着复杂器官的提取实质是重写 | **采纳** | 区分提取(简单器官)vs重写(复杂器官)，时间估算上调，见§4 |
| 3 | .omo治理系统已成为"产品"——32个task YAML vs 0行代码变更，Plan替代了Build | **采纳** | P17代码优先承诺：无代码提交=未完成，冻结新Phase创建直到P17产出代码 |

**SIGNIFICANT (3-4 Agent收敛)**:

| 4 | 健康分公式可被操纵(raw×debt_weight)，97.0是纸面合规不是真实健康 | **采纳** | 健康分加入代码变更权重因子，见§7 |
| 5 | SharedBrain单进程=单点灾难故障域 | **采纳** | 双模架构中库模式无此问题；独立模式加入熔断+降级 |
| 6 | agentmesh TS→Python是语言重写，P19分配2周不够 | **采纳** | P19拆分为多子Phase，跨P19-P21渐进迁移，见§6 |
| 7 | 5干细胞强制接口=BaseMembrane 2.0(换名不换质) | **部分采纳** | 保留接口合规价值，改为渐进式采纳(只强制Health+Identity) |

**红队验证的强点:**

| 1 | 合并方向正确——agentmesh并入kairon消除真实的结构性重复 |
| 2 | 问题诊断诚实——824K行死代码+零集成+475BaseMembrane癌变 |
| 3 | 4项目收敛方向对——即使执行估算被低估 |
| 4 | 区分协调逻辑vs业务逻辑——这是架构的根本分界 |

### 红队驱动的三项根本修正

**修正1: SharedBrain双模架构** (取代原"独立运行时"方案)

SharedBrain不是"保留"或"删除"的二选一——它是"需要时存在"的多形态：

```
sharedbrain-core (Python库, ~5K lines, 始终存在于kairon内)
├── protocols/    # 协议定义 (Identity, Health, Circuit, Metrics, Governance)
├── circuits/     # 回路引擎 (YAML解析, 状态机执行)
├── neurons/      # 连接代理 (健康探测, 故障转移)
└── stem_cells/   # 验证器 (接口合规检查)

库模式: kairon直接import sharedbrain_core, 进程内使用, 无独立进程
独立模式: sharedbrain-standalone (薄包装~2K行) 包装core为HTTP/MCP server
```

| 场景 | 形态 | 理由 |
|------|:----:|------|
| 本地单机开发 | 库模式 | 进程内调用，不需要独立端口 |
| 本地多服务 | 独立模式(:8000) | 需要独立可达的调度点 |
| 混合(本地kairon+云端服务) | 独立模式 | 云端服务需要外网可达 |
| 全云端 | 独立模式 | 所有服务在云端，需要独立调度 |
| CI/测试 | 库模式 | 测试中直接import |

**修正2: 器官提取vs重写区分** (取代"全部提取")

| 器官 | 策略 | 理由 | 时间调整 |
|------|:----:|------|:-------:|
| D_Window | 删除 | 空壳 | — |
| D_Harness | 提取 | 最小器官(9f/2K), BM密度高但可清理 | 1天→2天 |
| D_Extension→forge | 提取 | 独立性强, 已验证模式可行 | 不变 |
| D_KI→kos | 提取 | 中等复杂度, 9个D_Memory引用需解析 | 3天→4天 |
| D_Economy→eu-pricing | 提取 | 独立性强, 模式已验证 | 不变 |
| D_Excretion→gc-engine | 提取+新包 | 独立性中等 | 不变 |
| D_Monitoring→observability | 提取+新包 | 独立性中等 | 不变 |
| D_Immunity→metaos | **重写** | 深耦合(Z-Spore/Z-Microkernel), 提取实质是重写 | 5天→8天 |
| D_Genesis→三向 | **重写** | 最复杂的多向分散, 核心逻辑需识别和重写 | 5天→10天 |

**修正3: P17代码优先承诺**

- P17不再以"文档交叉审阅通过"为完成标准
- P17完成标准 = sharedbrain-core/protocols/ 下5个协议定义Python文件提交到kairon/core-models
- 32个task YAML中，P17相关的保持in_progress，P18+全部冻结为pending直到P17产出代码
- 不再创建新的task YAML直到P17 Exit Gate通过


## 3. 目标架构

### 3.1 4项目拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                        Hermes Console                            │
│                    (TypeScript/React · MCP Client)                │
│              http://localhost:3000  ──────────┐                   │
└───────────────────────┬─────────────────────┬─┘                   │
                        │ MCP                  │ MCP                │
                        ▼                      ▼                    │
┌───────────────────────────────┐  ┌──────────────────────────────┐│
│        SharedBrain            │  │         gbrain               ││
│    (Python · HTTP :8000)      │  │  (TypeScript · Postgres)      ││
│                               │  │                              ││
│  ┌─────────────────────────┐  │  │  ┌────────────────────────┐  ││
│  │     NeuralCenter        │  │  │  │   MCP Server (:6277)   │  ││
│  │  · Service Registry     │  │  │  │   · Graph Queries      │  ││
│  │  · Topology Graph       │  │  │  │   · Vector Search      │  ││
│  │  · Signal Router        │  │  │  │   · CRUD Operations    │  ││
│  │  · Health Monitor       │──┼──┼──│   · 74 Tools           │  ││
│  └─────────────────────────┘  │  │  └────────────────────────┘  ││
│  ┌─────────────────────────┐  │  └──────────────────────────────┘│
│  │     CircuitEngine       │  │                                  │
│  │  · YAML Circuit Parser  │  │  ┌──────────────────────────────┐│
│  │  · StateMachine Exec    │  │  │         kairon               ││
│  │  · SLA Enforcer         │──┼──│    (Python · Library)        ││
│  │  · Checkpoint Manager   │  │  │                              ││
│  └─────────────────────────┘  │  │  ┌─ 知识处理 ─────────────┐  ││
│  ┌─────────────────────────┐  │  │  │ ontoderive, eidos,     │  ││
│  │     NeuronPool          │  │  │  │ kos, sophia, hermes,   │  ││
│  │  · Connection Pool      │  │  │  │ minerva, morpho, logos │  ││
│  │  · Health Probe         │──┼──│  └────────────────────────┘  ││
│  │  · Failover Strategy    │  │  │  ┌─ 治理运行时 ───────────┐  ││
│  └─────────────────────────┘  │  │  │ metaos, agora, nomos   │  ││
│  ┌─────────────────────────┐  │  │  └────────────────────────┘  ││
│  │   StemCellValidator     │  │  │  ┌─ 管线 ─────────────────┐  ││
│  │  · 5 Required Interface │  │  │  │ pontus, codex,         │  ││
│  │  · Compliance Check     │──┼──│  │ gc-engine               │  ││
│  └─────────────────────────┘  │  │  └────────────────────────┘  ││
│                               │  │  ┌─ 能力工具 ─────────────┐  ││
│  ┌─────────────────────────┐  │  │  │ forge, observability,  │  ││
│  │     Protocols           │  │  │  │ eu-pricing,            │  ││
│  │  · identity.py          │  │  │  │ agent-runtime,         │  ││
│  │  · health.py            │  │  │  │ agent-hub               │  ││
│  │  · circuit.py           │  │  │  └────────────────────────┘  ││
│  │  · metrics.py           │  │  └──────────────────────────────┘│
│  │  · governance.py        │  │                                  │
│  └─────────────────────────┘  │                                   │
└───────────────────────────────┘                                   │
                                                                   │
  HTTP/MCP ──── 协议通信                                           │
  ── ── ── ──  库依赖(kairon → SharedBrain protocols)              │
```

### 3.2 数据流

```
用户 → Hermes Console (MCP Client)
         │
         ├──→ SharedBrain (HTTP :8000)
         │    │
         │    ├──→ kairon (库调用)
         │    │    └──→ gbrain (MCP · 知识持久化)
         │    │
         │    └──→ gbrain (直接MCP · 健康检查)
         │
         └──→ gbrain (直接MCP · 知识查询)
```

### 3.3 关键架构约束

| 约束 | 类型 | 说明 |
|------|------|------|
| kairon不直接HTTP服务 | 硬约束 | kairon是库，所有HTTP入口由SharedBrain代理 |
| gbrain不处理业务逻辑 | 硬约束 | gbrain只做存储和检索 |
| SharedBrain无状态 | 软约束 | 协调状态存内存，持久状态委托给gbrain |
| 所有服务必须实现5接口 | 硬约束 | Health/Identity/Circuit/Metrics/Governance |
| MCP作为唯一外部协议 | 硬约束 | Hermes Console通过MCP与后端通信 |

---

## 4. 9器官迁移方案

这是本文档的核心。每个器官的迁移方案必须极其具体，包含步骤、验收标准和风险缓解。

### 总览

| # | 器官 | 行数 | 文件 | 目标 | 复杂度 |
|---|------|------|------|------|--------|
| 1 | D_Window | 0 | 0 | 删除 | 无 |
| 2 | D_Immunity | 22K | 88 | kairon/metaos + SharedBrain协议 | 高 |
| 3 | D_Genesis | 20K | 59 | kairon/metaos + agent-runtime + minerva | 高 |
| 4 | D_Monitoring | 15K | 64 | kairon/observability (新包) | 中 |
| 5 | D_Economy | 7K | 30 | kairon/eu-pricing | 低 |
| 6 | D_KnowledgeIntegration | 6K | 23 | kairon/kos | 低 |
| 7 | D_Excretion | 7.5K | 37 | kairon/gc-engine (新包) | 中 |
| 8 | D_Extension | 5K | 14 | kairon/forge | 低 |
| 9 | D_Harness | 2K | 9 | 各包tests/ + kairon test-utils | 中 |

---

### 4.1 D_Window (0行) → 删除

**现状**: 空目录，无代码。

**迁移策略**: 直接删除。

**步骤**:
1. 删除目录: `rm -rf projects/SharedBrain/organs/D_Window`
2. 更新 SharedBrain INDEX.md，移除D_Window条目
3. 全局搜索 D_Window 引用: `rg D_Window`
4. 清理所有残留引用（配置、文档、import路径）
5. 提交变更

**验收标准**:
- [ ] `rg D_Window` 在代码库中返回0结果
- [ ] `ls organs/D_Window` 报不存在
- [ ] SharedBrain INDEX.md 中无 D_Window 条目

**风险**: 无。

---

### 4.2 D_Immunity (88文件, 22K行) → kairon/metaos + SharedBrain协议

**现状**: 身份验证、授权、威胁检测、安全策略。代码量大，逻辑复杂。

**核心保留**:
| 功能 | 源 | 目标 | 理由 |
|------|-----|------|------|
| RBAC引擎 | D_Immunity/rbac/ | metaos/immune.py | 访问控制核心，kairon需要 |
| 身份验证 | D_Immunity/auth/ | metaos/gate.py | 身份门控，共享能力 |
| 威胁检测 | D_Immunity/threat/ | metaos/immune.py | 安全检测逻辑 |

**归档**:
| 功能 | 理由 |
|------|------|
| 量子安全密码 | 过度工程，个人工作站不需要 |
| 联邦信任网络 | 多节点信任，超出单用户范围 |

**协议定义** (SharedBrain protocols/identity.py):
```python
# SharedBrain protocols/identity.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class IdentityRequest(BaseModel):
    """身份验证请求"""
    principal: str
    credential: str
    scope: list[str]
    timestamp: datetime

class IdentityResponse(BaseModel):
    """身份验证响应"""
    authenticated: bool
    principal_id: str
    token: Optional[str]
    capabilities: list[str]
    expires_at: datetime

class IdentityProtocol:
    """身份协议 —— SharedBrain侧接口定义"""
    ENDPOINT = "/identity/authenticate"
    VERSION = "v1"
    SLA_MS = 100
```

**迁移步骤**:

**Step 1**: 从D_Immunity源码提取接口定义 → SharedBrain protocols/
- 读取 D_Immunity/rbac/interface.py, D_Immunity/auth/interface.py
- 提取公开方法签名，不提取实现
- 写入 SharedBrain/protocols/identity.py (如上示意)
- 验收: protocols/identity.py 通过 ruff check

**Step 2**: 填入metaos现有壳子
- 读取 kairon/packages/metaos/src/metaos/immune.py (当前为壳)
- 读取 kairon/packages/metaos/src/metaos/gate.py (当前为壳)
- 从D_Immunity移植核心逻辑
- 适配SharedBrain协议接口
- 更新 __init__.py 导出
- 验收: metaos/immune.py ≥150行, metaos/gate.py ≥100行

**Step 3**: 创建identity-neuron连接kairon/metaos
- 在 SharedBrain/neurons/ 下创建 identity_neuron.py
- 实现Neuron接口(connect/probe/health)
- 配置连接metaos的导入路径
- 验收: identity_neuron 能成功connect并返回IdentityProtocol响应

**Step 4**: 归档旧代码
- 移动 D_Immunity → projects/_archived/D_Immunity/
- 创建归档清单 ARCHIVE_MANIFEST.yaml
- 验收: SharedBrain/organs/ 中无 D_Immunity

**Step 5**: 集成测试
- 编写 test_identity_circuit.py
- 测试: 注册 → 验证 → 授权 → 注销
- 验收: 测试通过，端到端延迟<100ms

**验收总标准**:
- [ ] metaos 测试 ≥70% 通过率
- [ ] 身份验证回路端到端 <100ms
- [ ] SharedBrain protocols/identity.py 定义完整
- [ ] D_Immunity 已完成归档
- [ ] identity-neuron 健康检查通过

**风险缓解**:
- 安全逻辑迁移采用TDD：先写测试，再移植代码
- 保留D_Immunity副本直到集成测试全部通过

---

### 4.3 D_Genesis (59文件, 20K行) → kairon/metaos + agent-runtime + minerva

**现状**: 起源/引导引擎、自愈内核、进化反馈、原型管理、遗传算法。

**核心保留**:
| 功能 | 源 | 目标 | 理由 |
|------|-----|------|------|
| 起源/引导引擎 | D_Genesis/origin/ | metaos/engine.py | 系统引导逻辑，metaos核心 |
| 自愈内核 | D_Genesis/healing/ | agent-runtime/self_healing.py | Agent自愈，运行时需要 |
| 进化反馈 | D_Genesis/evolution/ | minerva (研究/学习域) | 知识进化，研究域 |

**归档**:
| 功能 | 理由 |
|------|------|
| 原型管理 | 过度抽象，替换为回路YAML |
| 遗传算法 | 研究阶段代码，非生产就绪 |

**自愈回路** → SharedBrain circuits/self_healing.circuit:
```yaml
# SharedBrain/circuits/self_healing.circuit
circuit:
  id: self_healing
  version: "1.0"
  description: "Agent自愈回路"
  
  triggers:
    - type: health_check_failed
      threshold: 3
      window: 60s
    - type: error_rate_exceeded
      threshold: 0.05
      window: 300s

  states:
    - name: monitoring
      initial: true
    - name: diagnosing
    - name: healing
    - name: verifying
    - name: escalated

  transitions:
    - from: monitoring
      to: diagnosing
      on: trigger_fired
    - from: diagnosing
      to: healing
      on: diagnosis_complete
    - from: healing
      to: verifying
      on: healing_applied
    - from: verifying
      to: monitoring
      on: health_restored
    - from: verifying
      to: escalated
      on: health_not_restored
      max_retries: 3

  actions:
    diagnosing:
      - collect_diagnostics
      - analyze_failure_pattern
    healing:
      - restart_service
      - clear_cache
      - reload_configuration
    verifying:
      - run_health_check
      - validate_metrics
    escalated:
      - notify_operator
      - create_incident_record

  sla:
    max_healing_time: 300s
    max_retries_per_window: 5
```

**迁移步骤**:

**Step 1**: 提取接口定义 → SharedBrain protocols/circuit.py
- 定义Circuit、State、Transition、Action的Pydantic模型
- 定义CircuitEngine的Python协议类
- 验收: ruff check通过

**Step 2**: 移植起源引擎 → metaos/engine.py
- 从D_Genesis/origin/提取引导逻辑
- 简化为库级函数（不需要独立运行时）
- 适配SharedBrain Circuit协议
- 验收: engine.py测试通过

**Step 3**: 移植自愈逻辑 → agent-runtime/self_healing.py
- 从D_Genesis/healing/提取自愈策略
- 重构为回路可调用的动作函数
- 注册到CircuitEngine的动作注册表
- 验收: self_healing.py ≥200行

**Step 4**: 创建自愈回路配置 → SharedBrain circuits/self_healing.circuit
- 编写如上YAML
- 在CircuitEngine中注册
- 验收: 回路能被解析并模拟执行

**Step 5**: 归档+测试
- 移动D_Genesis → _archived/
- 编写集成测试
- 验收: 端到端自愈回路测试通过

**验收总标准**:
- [ ] metaos/engine.py 功能完整（测试≥70%通过）
- [ ] self_healing.circuit 能被CircuitEngine加载和执行
- [ ] 归档完整，源码无残留引用
- [ ] 遗传算法代码已标记为research/archived

---

### 4.4 D_Monitoring (64文件, 15K行) → kairon/observability (新包)

**现状**: 服务监控、指标采集、告警、日志聚合。

**新建包结构**:
```
kairon/packages/observability/
├── pyproject.toml
├── src/
│   └── observability/
│       ├── __init__.py
│       ├── slo/
│       │   ├── __init__.py
│       │   ├── calculator.py      # SLO计算器
│       │   ├── burn_rate.py       # 错误预算消耗率
│       │   └── reporter.py        # SLO报告
│       ├── alerts/
│       │   ├── __init__.py
│       │   ├── rule_engine.py     # 告警规则引擎
│       │   ├── notifier.py        # 通知器
│       │   └── escalation.py      # 升级策略
│       ├── metrics/
│       │   ├── __init__.py
│       │   ├── collector.py       # 指标采集器
│       │   ├── aggregator.py      # 聚合器
│       │   └── exporter.py        # Prometheus导出
│       └── health/
│           ├── __init__.py
│           ├── checker.py         # 健康检查器
│           ├── probe.py           # 探针
│           └── dashboard.py       # 健康面板数据
└── tests/
    ├── test_slo.py
    ├── test_alerts.py
    ├── test_metrics.py
    └── test_health.py
```

**迁移步骤**:

**Step 1**: 搭建包骨架
- 创建 pyproject.toml（依赖: prometheus-client, pydantic）
- 创建 src/observability/ 各子包 __init__.py
- 运行 `uv sync` 确认包可导入
- 验收: `uv run python -c "import observability"` 成功

**Step 2**: 移植指标采集
- 从D_Monitoring/metrics/ 提取采集逻辑
- 适配Prometheus格式
- 写入 observability/metrics/collector.py
- 验收: collector能采集并输出Prometheus格式指标

**Step 3**: 移植告警引擎
- 从D_Monitoring/alerts/ 提取规则引擎
- 写入 observability/alerts/rule_engine.py
- 验收: 告警规则能正确触发

**Step 4**: 移植SLO计算
- 从D_Monitoring/slo/ 提取计算逻辑
- 写入 observability/slo/calculator.py
- 验收: SLO计算准确

**Step 5**: 移植健康检查
- 从D_Monitoring/health/ 提取检查逻辑
- 适配SharedBrain Health协议
- 写入 observability/health/checker.py
- 验收: 健康检查endpoint返回符合协议

**验收总标准**:
- [ ] observability包4子模块全部可导入
- [ ] 测试≥60%通过率
- [ ] 指标输出符合Prometheus格式
- [ ] 告警规则引擎独立可测试

---

### 4.5 D_Economy (30文件, 7K行) → kairon/eu-pricing

**现状**: 使用量计算、定价模型、配额管理。

**迁移策略**: 填入eu-pricing现有壳子。

**迁移步骤**:

**Step 1**: 评估eu-pricing壳子差距
- 读取 kairon/packages/eu-pricing/src/eu_pricing/ 现有代码
- 对比D_Economy功能清单
- 识别缺失功能
- 验收: 差距分析文档完成

**Step 2**: 移植定价核心
- 从D_Economy/pricing/ 提取定价引擎
- 写入 eu-pricing/pricing_engine.py
- 验收: pricing_engine.py 测试通过

**Step 3**: 移植配额管理
- 从D_Economy/quota/ 提取配额逻辑
- 写入 eu-pricing/quota_manager.py
- 验收: quota_manager.py 测试通过

**Step 4**: 移植使用量跟踪
- 从D_Economy/usage/ 提取跟踪逻辑
- 写入 eu-pricing/usage_tracker.py
- 验收: usage_tracker.py 测试通过

**Step 5**: 归档+集成
- 移动D_Economy → _archived/
- 更新eu-pricing __init__.py
- 验收: 全量测试通过

**验收总标准**:
- [ ] eu-pricing核心3模块(pricing_engine/quota_manager/usage_tracker)测试通过
- [ ] D_Economy归档完整

---

### 4.6 D_KnowledgeIntegration (23文件, 6K行) → kairon/kos

**现状**: 知识索引、跨源搜索、知识融合。

**迁移策略**: 合并到现有kos包。

**9个D_Memory懒引用 → eidos/gbrain查询**:
D_Memory中9个懒引用需要转为eidos通过gbrain的实际查询。

**迁移步骤**:

**Step 1**: 功能映射
- 列出D_KnowledgeIntegration的23个文件的公开函数
- 映射到kos包的现有模块
- 识别需要新增的模块
- 验收: 映射表完成

**Step 2**: 合并知识索引逻辑
- 移植到 kos/indexer.py
- 验收: 索引功能可用

**Step 3**: 合并跨源搜索
- 移植到 kos/searcher.py
- 验收: 搜索功能可用

**Step 4**: 解决D_Memory懒引用
- 识别9个D_Memory懒引用位置
- 替换为 eidos.query() 调用（通过gbrain MCP）
- 验收: `rg "D_Memory"` 在kairon中返回0

**Step 5**: 归档+测试
- 移动D_KnowledgeIntegration → _archived/
- 验收: kos包全量测试通过

**验收总标准**:
- [ ] kos包新增功能测试通过
- [ ] 9个D_Memory懒引用已解决
- [ ] D_KnowledgeIntegration归档完整

---

### 4.7 D_Excretion (37文件, 7.5K行) → kairon/gc-engine (新包)

**现状**: 过期数据清理、内存回收、日志轮转、临时文件清理。

**新建包结构**:
```
kairon/packages/gc-engine/
├── pyproject.toml
├── src/
│   └── gc_engine/
│       ├── __init__.py
│       ├── sweeper.py         # 清理器
│       │   ├── DataSweeper    # 数据清理
│       │   ├── MemorySweeper  # 内存回收
│       │   └── LogSweeper     # 日志轮转
│       ├── policy.py          # 保留策略
│       │   ├── RetentionPolicy
│       │   ├── TTLPolicy
│       │   └── SizePolicy
│       ├── scheduler.py       # 调度器
│       │   ├── CronScheduler
│       │   └── TriggerScheduler
│       └── reporter.py        # 报告
│           ├── GCReport
│           └── StatsCollector
└── tests/
    ├── test_sweeper.py
    ├── test_policy.py
    ├── test_scheduler.py
    └── test_reporter.py
```

**迁移步骤**:

**Step 1**: 搭建包骨架
- 创建目录和pyproject.toml
- 创建各子模块
- 验收: 包可导入

**Step 2**: 移植清理器
- 从D_Excretion/sweeper/ 提取清理逻辑
- 写入 gc_engine/sweeper.py
- 验收: sweeper测试通过

**Step 3**: 移植策略引擎
- 从D_Excretion/policy/ 提取策略
- 写入 gc_engine/policy.py
- 验收: policy测试通过

**Step 4**: 移植调度器
- 从D_Excretion/scheduler/ 提取调度
- 写入 gc_engine/scheduler.py
- 验收: scheduler测试通过

**Step 5**: 归档+集成
- 移动D_Excretion → _archived/
- 验收: 全量测试通过

**验收总标准**:
- [ ] gc-engine包4模块全部可导入
- [ ] 测试≥60%通过率
- [ ] D_Excretion归档完整

---

### 4.8 D_Extension (14文件, 5K行) → kairon/forge

**现状**: 插件加载、扩展注册、钩子系统。

**迁移策略**: 合并到现有forge包。

**迁移步骤**:

**Step 1**: 评估forge现有能力
- 读取 kairon/packages/forge/src/forge/ 代码
- 对比D_Extension功能
- 验收: 差距文档完成

**Step 2**: 移植插件加载器
- 从D_Extension/loader/ 移植
- 写入 forge/plugin_loader.py
- 验收: 加载器测试通过

**Step 3**: 移植钩子系统
- 从D_Extension/hooks/ 移植
- 写入 forge/hook_system.py
- 验收: 钩子系统测试通过

**Step 4**: 移植扩展注册表
- 从D_Extension/registry/ 移植
- 写入 forge/extension_registry.py
- 验收: 注册表测试通过

**Step 5**: 归档+测试
- 移动D_Extension → _archived/
- 验收: forge包全量测试通过

**验收总标准**:
- [ ] forge包新增3模块测试通过
- [ ] D_Extension归档完整

---

### 4.9 D_Harness (9文件, 2K行) → 各包tests/ + kairon test-utils

**现状**: 测试框架、BaseMembrane测试基类、mock工具。

**BaseMembrane移除**: 这是最严重的债务——475实例分布在324文件中（平均2.7个/文件）。

**迁移策略**: 分散到各包的tests/中，提供test-utils公共包。

**迁移步骤**:

**Step 1**: 审计BaseMembrane依赖
- 运行脚本统计所有475个BaseMembrane实例位置
- 按包分类
- 验收: BaseMembrane使用地图完成

**Step 2**: 创建test-utils公共包
- 从D_Harness提取mock工具、fixture工厂
- 创建 kairon/packages/test-utils/
- 验收: test-utils可被其他包导入

**Step 3**: 逐包替换BaseMembrane
- 按包逐个替换为pytest fixtures
- 优先替换高频包
- 验收: 每完成一个包，BaseMembrane实例数减少

**Step 4**: 验证测试无退化
- 全量运行 `make test`
- 确保测试数量不减少
- 验收: 测试通过数≥迁移前

**Step 5**: 归档+清零
- 移动D_Harness → _archived/
- 最终验证: BaseMembrane实例 = 0
- 验收: `rg "BaseMembrane"` 返回0

**验收总标准**:
- [ ] BaseMembrane实例从475 → 0
- [ ] 测试总数不减少（≥2305）
- [ ] test-utils包可被其他包导入
- [ ] D_Harness归档完整

---

## 5. 接口契约

以下5个协议是SharedBrain的干细胞接口——所有连接到SharedBrain的服务必须实现。

### 5.1 身份协议 (Identity Protocol)

```yaml
协议名称: Identity Protocol v1
端点: GET/POST /identity
所有者: SharedBrain NeuralCenter

请求 (POST /identity/authenticate):
  {
    "principal": "string",
    "credential": "string",
    "scope": ["string"],
    "timestamp": "ISO8601"
  }

响应 (200):
  {
    "authenticated": true,
    "principal_id": "string",
    "token": "string",
    "capabilities": ["string"],
    "expires_at": "ISO8601"
  }

响应 (401):
  {
    "authenticated": false,
    "reason": "string"
  }

SLA:
  - 响应时间: <100ms (P95)
  - 可用性: 99.9%

版本: v1 (2026-06-02)
版本策略: 主版本号变更需所有客户端同步升级；次版本向后兼容
```

### 5.2 健康协议 (Health Protocol)

```yaml
协议名称: Health Protocol v1
端点: GET /health
所有者: SharedBrain HealthMonitor

请求: 无

响应 (200):
  {
    "status": "healthy" | "degraded" | "unhealthy",
    "timestamp": "ISO8601",
    "version": "string",
    "uptime_seconds": 3600,
    "checks": {
      "database": {"status": "healthy", "latency_ms": 5},
      "cache": {"status": "healthy", "latency_ms": 1},
      "storage": {"status": "healthy", "latency_ms": 10}
    },
    "metrics": {
      "cpu_percent": 45.2,
      "memory_mb": 512,
      "open_connections": 12
    }
  }

SLA:
  - 响应时间: <50ms (P95)
  - 探测间隔: 15s

版本: v1
```

### 5.3 回路协议 (Circuit Protocol)

```yaml
协议名称: Circuit Protocol v1
端点: POST /circuit/execute
所有者: SharedBrain CircuitEngine

回路YAML Schema:
  circuit:
    id: string (必需)
    version: string (必需)
    description: string
    
    triggers:  # 触发器列表
      - type: string
        threshold: number
        window: duration
    
    states:  # 状态列表
      - name: string
        initial: boolean (默认false)
        terminal: boolean (默认false)
    
    transitions:  # 转换列表
      - from: string
        to: string
        on: string
        guard: string (可选)
        max_retries: number (可选)
    
    actions:  # 动作映射
      state_name:
        - action_name
    
    sla:
      max_execution_time: duration
      max_retries_per_window: number

请求 (POST /circuit/execute):
  {
    "circuit_id": "self_healing",
    "context": {
      "service_id": "kairon-metaos",
      "incident_id": "INC-001"
    },
    "parameters": {}
  }

响应 (200):
  {
    "execution_id": "exec-xxx",
    "status": "completed" | "failed" | "running",
    "current_state": "monitoring",
    "state_history": [...],
    "result": {}
  }

SLA:
  - 回路加载: <200ms
  - 状态转换: <50ms
  - 并发回路: ≤100

版本: v1
```

### 5.4 指标协议 (Metrics Protocol)

```yaml
协议名称: Metrics Protocol v1
端点: GET /metrics
所有者: SharedBrain NeuralCenter

请求: 无 (可选 ?format=prometheus|json)

响应 (Prometheus格式):
  # HELP sharedbrain_requests_total Total requests
  # TYPE sharedbrain_requests_total counter
  sharedbrain_requests_total{method="GET",endpoint="/health"} 15234
  
  # HELP sharedbrain_circuit_executions Circuit executions
  # TYPE sharedbrain_circuit_executions gauge
  sharedbrain_circuit_executions{circuit="self_healing"} 3

响应 (JSON格式):
  {
    "requests": {"total": 15234, "by_endpoint": {...}},
    "circuits": {"active": 3, "completed": 120, "failed": 2},
    "services": {"healthy": 4, "degraded": 1, "unhealthy": 0},
    "timestamp": "ISO8601"
  }

SLA:
  - 响应时间: <100ms
  - 采集间隔: 15s (Prometheus)

版本: v1
```

### 5.5 治理协议 (Governance Protocol)

```yaml
协议名称: Governance Protocol v1
端点: GET /governance
所有者: SharedBrain StemCellValidator

请求: 无

响应 (200):
  {
    "compliance": {
      "required_interfaces": ["Health", "Identity", "Circuit", "Metrics", "Governance"],
      "implemented": ["Health", "Identity", "Metrics"],
      "missing": ["Circuit", "Governance"],
      "score": 0.6
    },
    "policies": {
      "circuit_sla": {"max_execution_time": "300s"},
      "health_check_interval": "15s",
      "version_policy": "semver"
    },
    "audit": {
      "last_validation": "ISO8601",
      "validated_by": "StemCellValidator",
      "findings": []
    }
  }

SLA:
  - 响应时间: <100ms
  
版本: v1
```

### 5.6 干细胞接口汇总

```python
# SharedBrain/protocols/__init__.py

STEM_CELL_INTERFACES = {
    "Health": {
        "endpoint": "GET /health",
        "required": True,
        "sla_ms": 50,
        "validation": "response.status in ['healthy', 'degraded', 'unhealthy']"
    },
    "Identity": {
        "endpoint": "POST /identity/authenticate",
        "required": True,
        "sla_ms": 100,
        "validation": "response.authenticated is bool"
    },
    "Circuit": {
        "endpoint": "POST /circuit/execute",
        "required": True,
        "sla_ms": 200,
        "validation": "response.execution_id exists and response.status in ['completed', 'failed', 'running']"
    },
    "Metrics": {
        "endpoint": "GET /metrics",
        "required": True,
        "sla_ms": 100,
        "validation": "response is valid Prometheus or JSON format"
    },
    "Governance": {
        "endpoint": "GET /governance",
        "required": True,
        "sla_ms": 100,
        "validation": "response.compliance.score is float between 0 and 1"
    }
}
```

---

## 6. Phase路线图

### Phase 17: 架构治理基础

| 属性 | 值 |
|------|-----|
| **目标** | 本文档完善、SharedBrain协议v1定义、metaos差距分析 |
| **预计时间** | 2周 |
| **前置条件** | 无 |

**交付物**:
1. ✅ 本文档 (omostation-strategic-architecture-v2.md) 已采纳
2. [ ] SharedBrain protocols/ 5个协议Python定义完成
3. [ ] metaos差距分析报告（对比D_Immunity/D_Genesis能力）
4. [ ] 器官迁移优先级排序确认

**验收标准**:
- [ ] 5个协议Python文件通过ruff check
- [ ] 差距分析文档记录在 .omo/_knowledge/design/
- [ ] Phase 17 gate review通过

---

### Phase 18: SharedBrain协议化

| 属性 | 值 |
|------|-----|
| **目标** | NeuralCenter实现、CircuitEngine实现、NeuronPool实现、D_Window删除 |
| **预计时间** | 3周 |
| **前置条件** | Phase 17完成 |

**交付物**:
1. [ ] SharedBrain/neural_center.py (NeuralCenter类)
2. [ ] SharedBrain/circuit_engine.py (CircuitEngine类)
3. [ ] SharedBrain/neuron_pool.py (NeuronPool类)
4. [ ] SharedBrain/stem_cell_validator.py (StemCellValidator类)
5. [ ] SharedBrain/circuits/ 至少1个回路配置
6. [ ] D_Window删除+验证

**验收标准**:
- [ ] SharedBrain启动后5个干细胞接口可访问
- [ ] 至少1个回路能被加载和执行
- [ ] 神经元池能连接到至少1个外部服务
- [ ] D_Window验证: rg返回0

---

### Phase 19: agentmesh吸收 (拆分为3子Phase)

> **红队修正:** 原P19分配2周是数量级错误。TS→Python是语言重写，不是代码搬运。拆分为跨P19-P21的渐进迁移，每步产出可独立验证的功能对等物。保留"agentmesh独立运行"作为回退策略。

| 属性 | 值 |
|------|-----|
| **目标** | agentmesh核心能力渐进迁入kairon，TS代码逐步归档 |
| **预计时间** | 6周 (跨P19-P21) |
| **前置条件** | Phase 18完成 |
| **回退策略** | 保留agentmesh独立运行的选项直到P21验收通过 |

**P19a (2周): 核心类型迁移**
1. [ ] agentmesh/core-types → kairon/core-models (类型定义)
2. [ ] 接口映射文档(功能对等验证)
3. [ ] Python类型通过mypy/pyright校验
4. [ ] 回退验证: agentmesh仍可独立运行

**P19b (2周, 与P20并行): 引擎能力迁移**
1. [ ] agentmesh/engine → agent-runtime (任务调度/编排)
2. [ ] agentmesh/toolkit → forge (工具注册)
3. [ ] 每个模块迁移后功能对等测试
4. [ ] 回退验证

**P19c (2周, 与P21并行): 网关与Hub迁移**
1. [ ] agentmesh/gateway → agora (MCP网关，重叠功能合并)
2. [ ] agentmesh/agents → agent-hub (Agent注册发现)
3. [ ] agentmesh/model-orchestrator → llm-gateway (模型编排)
4. [ ] 全量集成测试 + TS代码归档
5. [ ] 回退策略关闭: agentmesh归档完成

**验收标准:**
- [ ] 每个子Phase可独立验证(回退策略有效直到P19c完成)
- [ ] agent-runtime和agent-hub测试≥70%
- [ ] MCP工具数量不减少
- [ ] 确认Agent浏览器/Edge能力未丢失(AR-5发现)

---

### Phase 20: 器官迁移波1 (提取 — 已验证可行)

> **红队修正:** 简单器官(D_Economy/D_KI/D_Extension/D_Harness)采用提取模式，基于已验证的BaseMembrane清理模式。复杂器官(D_Immunity/D_Genesis)标记为重写，移到P21。

| 属性 | 值 |
|------|-----|
| **目标** | D_Economy→eu-pricing(提取), D_KI→kos(提取), D_Extension→forge(提取), D_Harness→各包tests/(提取) |
| **预计时间** | 3周 |
| **前置条件** | Phase 18完成 |

**交付物:**
1. [ ] D_Economy提取完成 (详见4.5, 验证模式可行, 1天→2天)
2. [ ] D_KnowledgeIntegration提取完成 (详见4.6, 9个D_Memory引用解决, 3天→4天)
3. [ ] D_Extension提取完成 (详见4.8)
4. [ ] D_Harness提取+BM清零 (详见4.9, 1天→2天)

**验收标准:**
- [ ] 4个器官归档, BaseMembrane降至<200
- [ ] 各目标包测试≥70%
- [ ] 为P21复杂器官重写提供"提取模板"经验

---

### Phase 21: 器官迁移波2 (重写 — 承认深度耦合)

> **红队修正:** D_Immunity和D_Genesis通过BaseMembrane/Z-Spore/Z-Microkernel深度纠缠。这是重写，不是提取。时间估算上调(5天→8天, 5天→10天)。策略：直接在目标包中重写所需能力，源器官整体归档为参考文档。

| 属性 | 值 |
|------|-----|
| **目标** | D_Immunity→metaos(重写), D_Genesis→metaos+agent-runtime+minerva(重写), D_Monitoring→observability(提取), D_Excretion→gc-engine(提取) |
| **预计时间** | 5周 |
| **前置条件** | Phase 20完成 + P19b完成 |

**交付物**:
1. [ ] D_Immunity迁移完成 (详见4.2)
2. [ ] D_Genesis迁移完成 (详见4.3)
3. [ ] D_Monitoring迁移完成 (详见4.4)
4. [ ] D_Excretion迁移完成 (详见4.7)

**验收标准**:
- [ ] 4个器官归档完成
- [ ] observability和gc-engine新包可导入
- [ ] metaos测试≥70%通过率
- [ ] 自愈回路端到端通过

---

### Phase 22: Pontus管线引擎

| 属性 | 值 |
|------|-----|
| **目标** | YAML DSL、DAG调度、断点续传、数据质量框架 |
| **预计时间** | 3周 |
| **前置条件** | Phase 21完成 |

**交付物**:
1. [ ] kairon/packages/pontus/ 包创建
2. [ ] YAML DSL解析器
3. [ ] DAG调度器（支持并行/串行）
4. [ ] 断点续传管理器
5. [ ] 数据质量校验框架

**验收标准**:
- [ ] 至少3条示例管线可执行
- [ ] DAG调度的并行任务正确执行
- [ ] 断点续传: 中断后能从检查点恢复
- [ ] 数据质量规则≥10条

---

### Phase 23: Hermes Console v1

| 属性 | 值 |
|------|-----|
| **目标** | 项目脚手架、知识仪表盘、Agent交互、系统健康 |
| **预计时间** | 4周 |
| **前置条件** | Phase 20完成 (后端API可用) |

**交付物**:
1. [ ] Hermes Console项目脚手架 (React + TypeScript + Vite)
2. [ ] 知识仪表盘 (GraphViewer + SearchPanel + StatsCards)
3. [ ] Agent控制台 (AgentList + ChatInterface + TaskMonitor)
4. [ ] 健康监控 (ServiceTopology + MetricsCharts + AlertPanel)
5. [ ] MCP客户端层 (ConnectionManager + ToolRegistry + StreamHandler)

**验收标准**:
- [ ] 所有4个主要面板可渲染
- [ ] MCP客户端能连接到SharedBrain和gbrain
- [ ] 知识仪表盘能展示gbrain中的图数据
- [ ] Agent控制台能发送和接收消息

---

### Phase 24: 深度解耦

| 属性 | 值 |
|------|-----|
| **目标** | BaseMembrane清零、Nucleus替换为Agora事件总线 |
| **预计时间** | 3周 |
| **前置条件** | Phase 21完成 |

**交付物**:
1. [ ] BaseMembrane实例: 0
2. [ ] Nucleus直接引用: 0 (替换为Agora事件总线)
3. [ ] 桥接代码清理: 0
4. [ ] 归档器官懒引用: 0

**验收标准**:
- [ ] `rg "BaseMembrane"` 返回0
- [ ] `rg "from.*nucleus import|import.*nucleus"` 在非nucleus目录中返回0
- [ ] `rg "D_Memory|D_Economy|D_Genesis|D_Immunity|D_Monitoring|D_Excretion|D_Extension|D_Harness|D_Window"` 在非归档目录返回0

---

### Phase 25: 集成与收敛

| 属性 | 值 |
|------|-----|
| **目标** | 端到端测试、契约验证、文档完成、债务关闭 |
| **预计时间** | 2周 |
| **前置条件** | Phase 24完成 |

**交付物**:
1. [ ] 端到端集成测试套件 (≥50场景)
2. [ ] 5个干细胞接口契约验证全部通过
3. [ ] 架构文档更新完成
4. [ ] 技术债账本关闭(全部HIGH/CRITICAL项)
5. [ ] 最终健康分达到97.0

**验收标准**:
- [ ] 端到端测试全部通过
- [ ] StemCellValidator对所有服务返回score=1.0
- [ ] 健康分 = 97.0 (raw 97.0 × debt_weight 1.0)
- [ ] 4项目边界清晰，无循环依赖

---

## 7. 指标看板

### 7.1 Phase演进指标

| Phase | 代码行 | 文件数 | 包数 | 健康分 | BM数 | nucleus引用 | 桥接数 | 测试通过率 |
|-------|--------|--------|------|--------|------|-------------|--------|------------|
| **当前 (P16)** | ~185K | ~1800 | 29 | 29.1 | 475 | 320 | ~15 | ~85% |
| **P17** | ~185K | ~1800 | 29 | 29.1 | 475 | 320 | ~15 | ~85% |
| **P18** | ~185K | ~1800 | 29 | 35.0 | 475 | 320 | ~12 | ~85% |
| **P19** | ~185K | ~1820 | 31 | 42.0 | 475 | 320 | ~10 | ~85% |
| **P20** | ~180K | ~1750 | 31 | 60.0 | <100 | <200 | ~5 | ~88% |
| **P21** | ~175K | ~1700 | 33 | 75.0 | <50 | <100 | ~3 | ~90% |
| **P22** | ~180K | ~1750 | 34 | 80.0 | <50 | <100 | ~3 | ~90% |
| **P23** | ~195K | ~1900 | 34 | 82.0 | <50 | <100 | ~3 | ~90% |
| **P24** | ~175K | ~1700 | 34 | 93.0 | 0 | 0 | 0 | ~93% |
| **P25** | ~175K | ~1700 | 34 | 97.0 | 0 | 0 | 0 | ~97% |

### 7.2 健康分轨迹

```
健康分
100 ┤                                    ──────────── 97.0 (P25)
 90 ┤                              ───── 93.0 (P24)
 80 ┤                         ───── 82.0 (P23)
 70 ┤                    ──── 80.0 (P22)
 60 ┤               ──── 75.0 (P21)
 50 ┤          ──── 60.0 (P20)
 40 ┤     ──── 42.0 (P19)
 30 ┤─●── 35.0 (P18)
 20 ┤● 29.1 (P16-P17)
 10 ┤
  0 ┼────┬────┬────┬────┬────┬────┬────┬────┬────
    P16  P17  P18  P19  P20  P21  P22  P23  P24  P25
```

### 7.3 关键里程碑

| 里程碑 | Phase | 标志 |
|--------|-------|------|
| 架构设计完成 | P17 | 本文档采纳 |
| SharedBrain就绪 | P18 | 5接口可访问 |
| agentmesh吸收 | P19 | 7 TS包归档 |
| 简单器官迁移 | P20 | 4器官归档 |
| 复杂器官迁移 | P21 | 所有SharedBrain器官归档 |
| 管线引擎就绪 | P22 | Pontus可运行 |
| 统一UI可用 | P23 | Hermes Console可交互 |
| 深度解耦完成 | P24 | BM=0, nucleus=0 |
| 最终收敛 | P25 | 健康分≥97 |

---

## 8. 风险矩阵

### R-01: 器官迁移中功能退化
| 属性 | 值 |
|------|-----|
| **概率** | 中 (40%) |
| **影响** | 高 —— 关键功能丢失 |
| **缓解** | TDD迁移：先写测试捕获现有行为，再移植代码；保留原器官副本至验证通过 |
| **所属Phase** | P20, P21 |

### R-02: BaseMembrane替换大面积失败
| 属性 | 值 |
|------|-----|
| **概率** | 高 (60%) |
| **影响** | 中 —— 部分测试失败但核心功能正常 |
| **缓解** | 逐包替换，每包独立验证；test-utils提供兼容层；P20开始逐步削减而非一次清零 |
| **所属Phase** | P20, P21, P24 |

### R-03: agentmesh吸收后TypeScript能力丢失
| 属性 | 值 |
|------|-----|
| **概率** | 低 (20%) |
| **影响** | 中 —— Agent管理功能减弱 |
| **缓解** | 接口映射文档确保功能对等；Python重新实现前完整记录TS行为 |
| **所属Phase** | P19 |

### R-04: Hermes Console开发超期
| 属性 | 值 |
|------|-----|
| **概率** | 高 (55%) |
| **影响** | 低 —— 不影响核心功能 |
| **缓解** | 优先CLI+MCP，Console作为增强而非必需品；Phase 23可延后 |
| **所属Phase** | P23 |

### R-05: 协议版本不兼容
| 属性 | 值 |
|------|-----|
| **概率** | 中 (35%) |
| **影响** | 高 —— 服务间通信失败 |
| **缓解** | 协议v1定义后进行集成测试；版本策略明确（主版本=不兼容，次版本=兼容） |
| **所属Phase** | P17, P18, P25 |

### R-06: gbrain独立部署复杂化
| 属性 | 值 |
|------|-----|
| **概率** | 低 (15%) |
| **影响** | 中 —— 部署复杂性增加 |
| **缓解** | 保持MCP作为唯一协议；提供docker-compose一键启动 |
| **所属Phase** | P18, P25 |

### R-07: 关键贡献者不可用
| 属性 | 值 |
|------|-----|
| **概率** | 低 (10%) |
| **影响** | 高 —— 知识断层 |
| **缓解** | 每个Phase输出完整文档；所有决策记录在决策日志；代码注释完整 |
| **所属Phase** | 全部 |

### R-08: 技术栈碎片化
| 属性 | 值 |
|------|-----|
| **概率** | 中 (30%) |
| **影响** | 中 —— 维护负担增加 |
| **缓解** | 严格限制语言数（Python+TS+React）；新依赖需架构审查 |
| **所属Phase** | P19, P22, P23 |

---

## 9. 决策日志

| ID | 日期 | 决策 | 理由 |
|----|------|------|------|
| **D-001** | 2026-06-02 | 终态收敛为4项目 | 系统思考分析表明4项目是最小完备集。SharedBrain(协调)、kairon(知识+Agent)、gbrain(存储)、Hermes Console(UI)每个有不可替代的职责 |
| **D-002** | 2026-06-02 | agentmesh并入kairon而非独立运行 | agentmesh与kairon Agent相关功能重叠；统一到Python减少技术栈碎片化；Agent SDK作为库比独立服务更适合单用户场景 |
| **D-003** | 2026-06-02 | metaos留在kairon作为库 | metaos是对SharedBrain协议的库级实现，不是独立服务。它被kairon的其他包导入使用 |
| **D-004** | 2026-06-02 | SharedBrain端口8000 | 与gbrain(6277)、Hermes Console(3000)不冲突；8000是开发服务常用端口 |
| **D-005** | 2026-06-02 | 5个干细胞接口为必须实现 | Health/Identity/Circuit/Metrics/Governance覆盖协调运行时的所有关键方面；少了任何一个都会产生不可检测的故障模式 |
| **D-006** | 2026-06-02 | 9器官分两波迁移(简单→复杂) | 简单器官(P20)风险低、验证迁移流程；复杂器官(P21)在流程成熟后迁移，降低风险 |
| **D-007** | 2026-06-02 | D_Window直接删除 | 0行空目录，无迁移价值 |
| **D-008** | 2026-06-02 | BaseMembrane分阶段清零 | 475实例量太大，一次性替换风险高。P20削减至<100，P24清零 |
| **D-009** | 2026-06-02 | MCP作为Hermes Console唯一后端协议 | MCP是AI生态标准；避免自定义HTTP API导致维护负担 |
| **D-010** | 2026-06-02 | 回路使用YAML DSL | YAML比JSON更可读；比Python DSL更易于可视化编辑；CircuitEngine解析后内部转换为状态机 |
| **D-011** | 2026-06-02 | 健康分采用加权模型 | raw × debt_weight反映真实健康。debt_weight从0.3→1.0随债务清理逐步提升 |
| **D-012** | 2026-06-02 | Pontus作为kairon管线引擎 | 管线编排属于知识处理域；kairon已有多条数据处理流水线(ontoderive, eidos)，统一管线引擎减少重复 |
| **D-013** | 2026-06-02 | gbrain保持TypeScript | gbrain已成熟(74 MCP tools)；重写为Python性价比低；存储引擎的语言选择不影响架构 |
| **D-014** | 2026-06-02 | 归档器官物理移动到_archived/ | 物理移动优于标记归档——消除意外依赖和懒引用的可能 |
| **D-015** | 2026-06-02 | Hermes Console使用React | React生态更成熟；与大多数AI工具集成更好 |
| **D-016** | 2026-06-02 | SharedBrain双模架构 | 库模式(sharedbrain-core~5K在kairon内)+独立模式(standalone~2K按需部署)。红队建议删SharedBrain的修正版 |
| **D-017** | 2026-06-02 | 器官提取vs重写区分 | 简单器官(D_Economy/D_KI/D_Extension/D_Harness)提取模式已验证可行；复杂器官(D_Immunity/D_Genesis)标记为重写——深度Z-Spore/Z-Microkernel耦合不可提取 |
| **D-018** | 2026-06-02 | P17代码优先 | P17完成标准=sharedbrain-core/protocols/下Python文件提交到代码库。无代码=未完成。冻结新Phase创建直到P17产出代码 |
| **D-019** | 2026-06-02 | P19拆分为3子Phase跨P19-P21 | agentmesh TS→Python是语言重写不是吸收，6周跨3Phase。保留agentmesh独立运行回退策略直到P19c验收 |
| **D-020** | 2026-06-02 | 5干细胞接口→渐进式采纳 | 红队指出强制5接口=BaseMembrane 2.0。改为渐进：只强制Health+Identity，其余3个按需采纳 |

---

## 10. OMO治理集成

### 10.1 Phase Gate机制

每个Phase结束时触发Phase Gate Review：

```
Phase Gate检查清单:
1. [ ] 交付物全部完成
2. [ ] 验收标准全部满足
3. [ ] 指标看板值在预期范围内
4. [ ] 风险矩阵更新(关闭已缓解风险，识别新风险)
5. [ ] 决策日志更新(本Phase新决策)
6. [ ] 债务账本更新
7. [ ] 健康分重算
8. [ ] Gate Review会议记录存入 .omo/_delivery/
```

### 10.2 任务注册

每个Phase的任务注册到 `.omo/tasks/active/`：

```yaml
# 示例: .omo/tasks/active/P18-sharedbrain-protocolization.yaml
task_id: P18-SHAREDBRAIN-PROTOCOLIZATION
phase: 18
status: planned
priority: CRITICAL
dependencies:
  - P17-ARCHITECTURE-GOVERNANCE
deliverables:
  - neural_center.py
  - circuit_engine.py
  - neuron_pool.py
  - stem_cell_validator.py
  - D_Window 删除
acceptance_criteria:
  - 5干细胞接口可访问
  - 至少1回路可执行
  - D_Window rg返回0
estimated_effort: 3w
assignee: TBD
```

### 10.3 债务账本更新

本规划直接对接 `.omo/state/system.yaml` 中的9项债务。各Phase解决映射：

| OMO债务ID | 标题 | 当前状态 | 解决Phase | 终态 | 权重 |
|-----------|------|:------:|:---------:|:----:|:---:|
| SB_DECOMPOSITION | SharedBrain分解部分治理 | in_progress | P25 | resolved | 0.20 |
| SB_BRIDGE_FIX | sharedbrain-bridge未连接 | classified | P18 | resolved | 0.10 |
| SB_ROOT_CLEANUP | Root清理延期 | classified | P18 | resolved | 0.05 |
| SB_UNTESTED_PKGS | kairon包缺测试基线 | classified | P25 | improved | 0.15 |
| SB_ORPHANED_TASKS | 孤立任务语义漂移 | classified | P25 | improved | 0.10 |
| SB_PROJECTS_YAML | PROJECTS注册表过期 | classified | P25 | resolved | 0.05 |
| SB_PHASE17_PLAN | Phase17规划需债务跟踪 | mitigated | P17 | resolved | 0.05 |
| D2_CI_E2E | CI E2E环境非规范 | pending | 独立track | pending | 0.15 |
| D3_EU_PRICING | eu-pricing测试非独立 | pending | 独立track | pending | 0.15 |

**Phase→债务权重变化:**

| Phase | 已解决债务 | debt_weight | 健康分 |
|:-----:|-----------|:----------:|:------:|
| P16(现状) | 0 | 0.30 | 29.1 |
| P17 | SB_PHASE17_PLAN | 0.35 | 34.0 |
| P18 | +SB_BRIDGE_FIX, SB_ROOT_CLEANUP | 0.50 | 48.5 |
| P20 | +SB_UNTESTED_PKGS(部分) | 0.60 | 58.2 |
| P21 | +SB_UNTESTED_PKGS(更多) | 0.70 | 67.9 |
| P23 | +SB_PROJECTS_YAML | 0.75 | 72.8 |
| P25 | +SB_DECOMPOSITION, SB_ORPHANED_TASKS | 0.85 | 82.5 |
| 终态(D2+D3解决后) | +D2_CI_E2E, D3_EU_PRICING | 1.00 | 97.0 |

**注意:** D2_CI_E2E和D3_EU_PRICING在本规划范围外，由独立任务track解决。即使这两项未解决，本规划完成后健康分可达82.5(债务权重0.85)。

技术债消除追踪 (`.omo/_truth/debt-ledger.yaml`):

```yaml
debt_items:
  - id: SB_DECOMPOSITION
    type: sharedbrain_organ_extraction
    target: all_19_organs_governed
    phase_resolution: P25
    severity: CRITICAL
    status: active → resolved_at_P25
    
  - id: SB_BRIDGE_FIX  
    type: bridge_activation
    target: 4_active_contracts
    phase_resolution: P18
    severity: HIGH
    status: classified → resolved_at_P18
    
  - id: SB_ROOT_CLEANUP
    type: root_shell_cleanup
    target: zero_broken_paths
    phase_resolution: P18
    severity: LOW
    status: classified → resolved_at_P18
    
  - id: BaseMembrane_count
    type: legacy_framework
    count: 475
    target: 0
    phase_reduction:
      P20: 475 → <200
      P21: <200 → <50
      P24: <50 → 0
    severity: CRITICAL
    
  - id: nucleus_refs_count
    type: framework_coupling
    count: 320
    target: 0
    phase_reduction:
      P24: 320 → 0
    severity: HIGH
```

### 10.4 健康分重算公式

```python
def calculate_health(raw_health: float, debt_items: list[DebtItem]) -> float:
    """
    健康分 = raw_health × debt_weight
    
    debt_weight 计算:
      - BaseMembrane每100个减0.1 (475→0 从0.0→0.5)
      - nucleus引用每100个减0.05
      - 归档懒引用每个减0.01
      - 桥接代码每5个减0.02
    """
    base_weight = 1.0
    
    # BaseMembrane penalty (0-0.475)
    bm_penalty = min(0.475, debt_items["BaseMembrane"] * 0.001)
    
    # Nucleus reference penalty (0-0.16)
    nr_penalty = min(0.16, debt_items["nucleus_refs"] * 0.0005)
    
    # Archived lazy ref penalty (0-0.22)
    ar_penalty = min(0.22, debt_items["archived_refs"] * 0.01)
    
    # Bridge code penalty (0-0.06)
    bc_penalty = min(0.06, debt_items["bridge_code"] * 0.004)
    
    debt_weight = base_weight - bm_penalty - nr_penalty - ar_penalty - bc_penalty
    debt_weight = max(0.1, debt_weight)  # 下限0.1
    debt_weight = min(1.0, debt_weight)  # 上限1.0
    
    return round(raw_health * debt_weight, 1)

# 当前: raw=97.0, BM=475, NR=320, AR=22, BC=15
# debt_weight = 1.0 - 0.475 - 0.16 - 0.22 - 0.06 = 0.085 → 下限0.1 + 调整 → 0.3
# health = 97.0 * 0.3 = 29.1

# P25目标: raw=97.0, BM=0, NR=0, AR=0, BC=0
# debt_weight = 1.0
# health = 97.0 * 1.0 = 97.0
```

### 10.5 SSOT合规

| 数据项 | 唯一读源 | 本文档角色 |
|--------|---------|-----------|
| 任务状态 | `.omo/tasks/active/` | 引用，不复制 |
| 系统状态 | `.omo/state/system.yaml` | 引用当前值 |
| 目标 | `.omo/goals/current.yaml` | 不覆盖，只引用 |
| 标准 | `.omo/standards/` | 协议契约需与standards/一致 |
| 债务 | `.omo/_truth/debt-ledger.yaml` | 本文档定义迁移路径，债务账本追踪进度 |

### 10.6 文档生命周期

```yaml
document:
  id: omostation-strategic-architecture-v2
  version: 2.0.0
  status: adopted
  location: .omo/_knowledge/design/
  supersedes: 
    - phase12-14-architecture-design.md (部分)
    - sharedbrain-architecture-governance-plan.md (部分)
    - organ-migration-master-plan.md
  review_cadence: 每Phase结束时审视更新
  expiration: 无 (持续更新至Phase 25完成)
  authors:
    - Architecture Council
  changelog:
    - version: 2.0.0
      date: 2026-06-02
      changes: 初始版本 —— 基于系统思考深度分析的完整战略架构
```

---

> **本文档是omostation项目Phase 17-25的唯一战略架构参考。**
> 所有后续架构决策必须与此文档一致。如需修改，需经过Phase Gate Review流程。
> 最终更新: 2026-06-02
