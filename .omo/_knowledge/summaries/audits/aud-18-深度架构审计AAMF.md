---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# AI OS 深度架构审计

> 审计日期: 2026-05-26
> 审计目标: 建立外层架构模式→元模型驱动→每层架构模式支撑→功能解耦→可热插拔
> 审计范围: Workspace 全部 30+ 项目，5+2 层架构体系，Agent Runtime, Eidos, Agora, Hermes

---

## 一、核心发现

### 🔴 发现1: 无统一架构宪法文档

`WORKSPACE_ARCHITECTURE_CONSTITUTION.md` 存在于对话记忆中但未落盘。当前架构知识分散在：
- `AGENTS.md`（30+个，分散定位）
- `README.md`（各项目自描述）
- `eidos/src/eidos/meta/__init__.py`（8×4元模型，最接近宪法）
- `metacog/01-theories/personal-ontology/protocol.md`（概念层本体）
- `.omo/`（治理文件，但无架构宪法）

**影响**: 没有单一权威文档定义"什么是架构节点""节点间如何通信""接口契约是什么"。

### 🔴 发现2: Eidos 元模型只有骨架，没有肉身

当前 Eidos 8×4 元模型状态：

| 维度 | 状态 | 问题 |
|------|------|------|
| 8 MetaTypes | ✅ 定义 | PROCESSOR 类型无具体映射 |
| 4 MetaRelationTypes | ✅ 定义 | 但只有4条内置约束(8×4=32组合，用上12.5%) |
| 类型→具体 Schema 映射 | 🟡 部分 | 仅有 KnowledgeCard/Fact/OntologyNode |
| 可热插拔机制 | ❌ 无 | 元模型没有定义"如何注册新节点" |
| 跨项目约束 | ❌ 无 | 各项目不校验是否遵循元模型 |

**影响**: 元模型有了但没有被真正使用——各项目仍在自定接口。

### 🔴 发现3: 项目间通信缺乏统一枚举/标识/能力模型

| 跨层通信 | 当前方式 | 问题 |
|----------|---------|------|
| 工具调用 | MCP (stdlib/SSE/HTTP) | 工具名、参数、返回值无统一 schema |
| Agent 间通信 | A2A (Agora AgentCard) | 仅有基础 AgentCard，无能力协商 |
| 事件 | Agora EventBus | 事件类型无统一注册和版本控制 |
| 配置 | 各项目自有一套 | 无 SSOT-derived 配置 schema |
| 身份 | 各项目自有一份 | 无统一 IdentityEnvelope |

**影响**: 任何模块更换都涉及 N 个点的适配修改。

### 🟡 发现4: 5+2 层架构的各层实现完整度

| 层 | 实现 | 元模型覆盖度 |
|----|------|-------------|
| L1 内核与资源 | Eidos + SSOT | 🟡 元模型定义了 MetaTypes 但未绑定到具体实现 |
| L2 服务总线 | Agora (注册/路由/事件/熔断/A2A) | 🔴 Agora 自身无元模型约束 |
| L3 资产与能力 | Forge(工具) + Toolkit(能力) + KOS(知识) | 🔴 三套独立的资产语义 |
| L4 智能编排 | agentmesh Engine + MetaOS + Agent Runtime | 🔴 三个编排引擎无统一设计 |
| L5 应用协作 | eCOS(认知脚本) | 🟡 有 STATE/HANDOFF 但非架构级 |
| S1 治理安全 | Agora Governance + SharedBrain 免疫 | 🟡 治理规则未对齐元模型 |
| S2 持续进化 | ❌ 自动进化引擎不存在(只有手动复盘) | 🔴 完全缺位 |

### 🟡 发现5: Agent Runtime 是"游离节点"

Agent Runtime (675 LOC) 功能完整但：
- 无 Eidos MetaType 绑定（它是"什么类型"？MetaType.PROCESSOR？）
- 无架构级接口契约（它的入口/出口没有在 Agora 注册中声明）
- 工具名扁平化是技术限制（DeepSeek 不支持点号），但无架构层面的工具命名规范
- 没有 A2A AgentCard（无法被其他 Agent 发现和协商）

---

## 二、根因分析

### 根因1: 先有项目，后有架构

```
时间线:
AgentMesh → Agora → KOS → Minerva → Eidos → Agent Runtime
        ↑                                    ↑
     先做                               后来才想要元模型
```

元模型是事后补的，不是事前定义的。所以现有项目没有一个是"从元模型实例化而来"。

### 根因2: 元模型层次单一

当前元模型只有一层（8 MetaType × 4 MetaRelation），缺少：

```
元元模型层 (Meta-Meta-Model): 定义"模型是什么"
    ↓ 实例化
元模型层 (Meta-Model): 8×4 实体-关系
    ↓ 实例化
模型层 (Model): 具体 Schema (KnowledgeCard/Fact/OntologyNode)
    ↓ 实例化
实例层 (Instance): 具体数据 (这条知识/这个工具/这个Agent)
```

### 根因3: 缺少"架构节点"这个概念

当前每个项目是一个文件夹。但"架构节点"应该是：

```yaml
architecture_node:
  id: "agent-runtime"
  meta_type: PROCESSOR
  implements: ["runtime.chat", "runtime.run_task"]
  depends_on: ["deepseek-llm", "eidos-schemas"]
  provides: ["mcp:tools", "http:endpoints", "a2a:agent-card"]
  interface_protocol: "mcp" | "http" | "a2a" | "cli"  # 统一枚举
  lifecycle: "launchd" | "cron" | "manual" | "ephemeral"
```

没有这个概念，就无法建立"每个模块都是某个架构节点的实现"这一约束。

---

## 三、对标: 业界成熟方案

### 3.1 Archimate (The Open Group)

| 特性 | Archimate | 我们当前 | 差距 |
|------|-----------|---------|------|
| 3 层 (Business/Application/Technology) | ✅ | 5+2 层但无层级约束 | 缺少跨层映射 |
| 关系类型 (Composition/Assignment/Realization/etc) | 6 种 | 4 种 MetaRelation | 需要扩展 |
| 视图(Viewpoint) | 多视角 | 无 | 架构应该从多个视角查看 |

### 3.2 本体工程: Ontology Web Language (OWL)

| 特性 | OWL | 我们当前 | 差距 |
|------|-----|---------|------|
| 类层次推理 | Class A ⊑ Class B | 仅平面 MetaType | 无层级 |
| 属性约束 | ObjectProperty + DataProperty | 只定义了 Realtion | 缺属性层面的约束 |
| 推理 | DL Reasoner | 仅有内置约束列表 | 没有自动推理 |

### 3.3 Simon Brown C4 Model

| 级别 | C4 | 我们对应 | 差距 |
|------|----|---------|------|
| Context | 系统边界 | AGENTS.md 的定位 | 缺少可视化 |
| Container | 进程/服务 | 各项目 | 缺少容器级映射 |
| Component | 类/模块 | 各模块 | 缺少组件级约束 |
| Code | 实现 | 代码本身 | 无 |

### 3.4 差异总结

| 维度 | 业界标准 | 我们的现状 | 优先级 |
|------|---------|-----------|--------|
| 元元模型 | OWL/RDF(S) 有形式化定义 | 无 | P0 |
| 元模型 | Archimate 有 3 层 × 6 关系 | 1 层 × 4 关系 | P0 |
| 接口契约 | OpenAPI / AsyncAPI / Protobuf | 自定 MCP 扩展 | P1 |
| 节点注册 | Service Registry + Discovery | Agora 已有 | P1 |
| 架构宪法 | 单一权威文档 | 不存在 | P0 |

---

## 四、新架构设计: AAMF (Agent Architecture Meta-Framework)

### 4.1 三层元模型体系

```
元元层 (M3): ArchitectureObject
  - 定义"什么是一个架构对象"
  - 属性: id, name, meta_type, relations, lifecycle, contracts

元层 (M2): 8MetaType × 4MetaRelation + 扩展
  - DOMAIN | FACT | INFERENCE | RELATION | STATE | DOCUMENT | CONSTRAINT | PROCESSOR
  - 新增: TOOL | CAPABILITY | SERVICE | ASSET | AGENT | EVENT
  - 4MetaRelation → 扩展到 8 种:
    COMPOSE | DEPEND | DERIVE | BEHAVE | JUSTIFY |
    CONFIGURE | DELEGATE | MONITOR

模型层 (M1): 具体 Schema
  - 每个项目/模块是一个 ArchitectureNode 实例
  - 界面契约: MCP | A2A | HTTP | CLI | Event (统一枚举)
  - 生命周期: build | run | monitor | evolve | retire

实例层 (M0): 运行中的具体实体
  - Agent Runtime 是 MetaType.PROCESSOR 的一个实例
  - Agora 是 MetaType.SERVICE 的一个实例
  - KOS 是 MetaType.DOMAIN 的一个实例

┌─────────────────────────────────────────────────────────┐
│  M3: ArchitectureObject (元元模型)                      │
│  ┌─────────────────────────────────────────────────────┐│
│  │  M2: 8+6 MetaTypes × 8 MetaRelations (元模型)       ││
│  │  ┌───────────────────────────────────────────────┐  ││
│  │  │  M1: ArchitectureNode (Schema 层)             │  ││
│  │  │  ┌─────────────────────────────────────────┐  │  ││
│  │  │  │  M0: 具体实例 (AgentRuntime/Agora/KOS)   │  │  ││
│  │  │  └─────────────────────────────────────────┘  │  ││
│  │  └───────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 4.2 架构节点 (ArchitectureNode) 定义

```yaml
architecture_node:
  # 身份
  id: "agent-runtime"               # 全局唯一 ID
  name: "Agent Runtime"             # 人类可读名
  type: PROCESSOR                   # 元模型类型 (8+6 枚举)
  version: "1.0.0"                  # 语义化版本

  # 元数据
  meta:
    created_by: "user:laowang"
    description: "独立 LLM 任务执行引擎"
    tags: ["llm", "execution", "cron", "mcp"]

  # 依赖
  depends_on:
    - type: SERVICE
      id: "deepseek-llm"
      interface: "http"
    - type: DOMAIN
      id: "kos"
      interface: "mcp:tools"

  # 提供的能力
  provides:
    - id: "runtime.run-task"
      interface: "mcp:tools"        # 接口类型
      target: "run_task"            # 具体的端点/方法
      schema: "TaskDefinition"      # 遵循的 Eidos Schema
    - id: "runtime.chat"
      interface: "http:endpoint"
      target: "POST /chat"
      schema: "ChatRequest"

  # 生命周期
  lifecycle:
    manager: "launchd"             # 进程管理器
    health_check: "/health"        # 健康检查端点
    restart_policy: "always"
    log_path: "~/Workspace/agent-runtime/server.log"

  # 治理
  governance:
    audit_events: true
    rate_limit: 100/1m
    allowed_networks: ["127.0.0.1"]
```

### 4.3 接口契约 (InterfaceContract)

所有架构节点之间的通信遵循统一枚举：

```yaml
interface_contract:
  protocols:
    - mcp:tools       # 工具调用 (stdio/SSE)
    - mcp:resources   # 资源发现 (SSE)
    - http:endpoint   # REST API
    - http:webhook    # 事件推送
    - a2a:agent       # Agent 间通信
    - a2a:task        # 任务路由
    - event:publish   # 事件发布
    - event:subscribe # 事件订阅
    - cli:command     # CLI 入口
    - cli:subprocess  # 子进程调用
    - db:query        # 数据库查询
    - db:store        # 数据库写入
```

---

## 五、迭代方案: 3 Phase Roadmap

### Phase 1 — 建立宪法与元模型 (1-2 周)

| # | 任务 | 产出 | 涉及项目 |
|---|------|------|---------|
| 1 | 落盘 WORKSPACE_ARCHITECTURE_CONSTITUTION.md | 单一权威宪法文档 | 新建 |
| 2 | 扩展 Eidos 元模型 (8+6 × 8) | 新增 TOOL/CAPABILITY/SERVICE/ASSET/AGENT/EVENT 六个 MetaType | eidos |
| 3 | 扩展 MetaRelation 到 8 种 | COMPOSE/DEPEND/DERIVE/BEHAVE/JUSTIFY/CONFIGURE/DELEGATE/MONITOR | eidos |
| 4 | 定义 ArchitectureNode Schema | 标准节点描述模型 | eidos |
| 5 | 定义 InterfaceContract | 统一接口枚举 | eidos |
| 6 | 实现在 Agora 注册时校验元模型 | 新注册的服务必须带 ArchitectureNode | agora |
| 7 | 定义 IdentityEnvelope | 统一跨项目身份模型 | eidos + ssot |

### Phase 2 — 现有项目对齐 (2-3 周)

| # | 任务 | 产出 |
|---|------|------|
| 1 | Agent Runtime 绑定 MetaType.PROCESSOR | 提供 ArchitectureNode 声明 |
| 2 | Agent Runtime 注册到 Agora（带元模型校验） | Agora 注册条目 |
| 3 | Agora 自身绑定 MetaType.SERVICE | 提供 ArchitectureNode 声明 |
| 4 | AgentMesh Engine 绑定 MetaType.PROCESSOR | 提供 ArchitectureNode 声明 |
| 5 | Forge 工具注册绑定 MetaType.TOOL | 整合到 Asset Registry |
| 6 | KOS 绑定 MetaType.DOMAIN | 提供 ArchitectureNode 声明 |
| 7 | 所有项目生成统一 ArchitectureNode 声明文件 | 30+ `ARCH_NODE.yaml` 文件 |

### Phase 3 — 热插拔与进化 (3-4 周)

| # | 任务 | 产出 |
|---|------|------|
| 1 | ArchitectureNode Registry (Agora 扩展) | 所有节点在 Agora 注册 |
| 2 | 依赖图自动推导 | 从 ArchitectureNode 自动生成依赖关系 |
| 3 | 接口兼容性检查 | 更换模块时自动检查接口契约是否匹配 |
| 4 | 进化引擎（S2层） | 自动检测架构漂移并建议修复 |
| 5 | 多视角视图生成 | C4 + Archimate 视图自动生成 |

---

## 六、优先级与影响矩阵

| 任务 | 影响 | 工作量 | 优先级 |
|------|------|--------|--------|
| 宪法落盘 | 🔴 所有决策缺少参考点 | 半天 | P0 |
| 元模型扩展 | 🔴 12% → 100% 覆盖 | 2天 | P0 |
| ArchitectureNode Schema | 🟡 模块可发现/可替换的前提 | 1天 | P0 |
| 现有项目对齐 | 🟡 需要更改 30+ 项目 | 2-3周 | P1 |
| 热插拔机制 | 🟢 长期价值大但短期不急 | 3-4周 | P2 |
| 进化引擎 | 🟢 终极差异化 | 4周+ | P3 |

---

## 七、关键决策

1. **ArchitectureNode 的权威来源**: Eidos Schema → Agora Registry → 各项目投影
2. **InterfaceContract 不新建协议**: 使用现有 MCP/A2A/HTTP 标准，只用元模型约束其使用方式
3. **元模型生命周期**: Eidos 管理定义，Agora 管理运行时校验，各项目负责实现
4. **替换策略**: 新节点注册 → 依赖图检查 → 老节点优雅下线 → 新节点接管
5. **不加层，只加约束**: 现有的 5+2 层架构不变，只增加元模型层的约束

---

## 八、总结

当前架构有坚实基础（Eidos 元模型、Agora 服务总线、MCP 协议体系、5+2 层架构），但缺少三层关键约束：

1. **元元模型** — "架构节点是什么"没有形式化定义
2. **接口契约枚举** — 模块间通信方式没有统一列举
3. **注册时校验** — 模块注册到体系时没有校验是否遵循元模型

这三个约束建好，现有所有项目自动成为"架构节点的某个实现"，热插拔自然可达成。
