# eCOS v5 系统全景

> 架构 · 应用场景 · 能力地图 · 核心链路 · 子项目详情

---

## 一、系统架构全景

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            eCOS v5 系统架构                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  L4 自我层 · 21域管理 · KEMS v7.0                                       │   │
│  │  ┌─────────────┐ ┌─────────────┐                                       │   │
│  │  │  l4-kernel  │ │model-driven │                                       │   │
│  │  │ 21域·43工具 │ │24类型·7阶段 │                                       │   │
│  │  └─────────────┘ └─────────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  L3 入口层 · 统一交互面                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │                      cockpit                                    │   │   │
│  │  │  CLI 18命令 + MCP 20工具 + Web Dashboard + 治理仪表板          │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  I0 织层 · 服务网格                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │                       agora                                     │   │   │
│  │  │  MCP Hub · 服务发现 · 路由代理 · 健康监控 · 治理审计            │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  L2 引擎面 · 知识/治理/编排                                             │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                      │   │
│  │  │ kairon  │ │  gbrain │ │   omo   │ │ metaos  │                      │   │
│  │  │ 16包    │ │ 67 MCP  │ │ 治理OS  │ │ 编排引擎│                      │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  L1 运行时 · 基础设施                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │                       runtime                                   │   │   │
│  │  │  服务注册 · 健康监控 · KEI沙箱 · 调度器 · 30 MCP tools          │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  L0 协议层 · 底层抽象                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │                        ecos                                     │   │   │
│  │  │  SSB签名链 · 涌现度量 · MOF元模型 · X1-X4治理框架 · 治理注册表  │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  算力层 · 分布式计算                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │                      aetherforge                                │   │   │
│  │  │  算力网格 · LLM网关 · 群体智能 · 资源调度                       │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  X 轴保障 · 贯穿所有层                                                  │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                                     │   │
│  │  │ X1  │ │ X2  │ │ X3  │ │ X4  │                                     │   │
│  │  │审计链│ │抗熵 │ │价值栈│ │一致性│                                     │   │
│  │  └─────┘ └─────┘ └─────┘ └─────┘                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 BOS URI 命名空间

| 域 | 命名空间 | 承载项目 |
|----|---------|---------|
| 记忆与事实源 | `bos://memory` | kos, kronos, gbrain, sot-bridge |
| 治理与律法 | `bos://omo` | metaos, eidos, protocols-layer, omo |
| 认知与推演 | `bos://analysis` | ontoderive, minerva, codeanalyze |
| 人格与心智 | `bos://persona` | sot-bridge |
| 能力与生态 | `bos://forge` | forge, runtime |

---

## 二、子项目详情

### 2.1 L4 自我层

#### l4-kernel

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 21域管理·43 MCP tools |
| 测试 | 30 |
| 能力地图 | ✅ |

**核心能力**:
- 域管理: 21 个域的生命周期管理
- MCP 工具: 43 个 MCP 工具
- KEMS 治理: 知识工程管理系统
- 信号总线: 事件驱动信号

#### model-driven

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 24类型·7阶段·12工具 |
| 测试 | 28 |
| 能力地图 | ✅ |

**核心能力**:
- M2 类型: 24 个元模型类型
- 7 阶段: 生命周期阶段管理
- 12 工具: 模型操作工具
- Pipeline: 数据处理管线

---

### 2.2 L3 入口层

#### cockpit

| 指标 | 值 |
|------|-----|
| 版本 | 0.4.0 |
| 功能 | CLI 18命令 + MCP 20工具 + Web |
| 测试 | 74 |
| 能力地图 | ✅ |

**核心能力**:
- CLI: 18 个子命令
- MCP: 20 个工具 (含 6 个治理工具)
- Web: FastAPI + Vue Dashboard
- 治理: X1-X4 检查 + 仪表板

**MCP 工具**:
- governance_check: X1-X4 治理检查
- governance_status: 治理状态
- governance_sla: SLA 达成
- governance_leaderboard: 排行榜
- governance_dashboard: 仪表板数据
- governance_history: 历史数据

---

### 2.3 I0 织层

#### agora

| 指标 | 值 |
|------|-----|
| 版本 | 3.0.0 |
| 功能 | MCP Hub·服务发现·路由代理 |
| 测试 | 92 |
| 能力地图 | ✅ |

**核心能力**:
- 服务注册: MCP 服务动态注册/发现
- 路由代理: BOS URI 路由/代理
- 健康监控: 服务健康检查/心跳
- 治理审计: 操作审计/日志

---

### 2.4 L2 引擎面

#### kairon

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 16包知识引擎 |
| 测试 | 2,593 |
| 能力地图 | ✅ |

**16 个包**:

| 包名 | 功能 | 测试数 |
|------|------|--------|
| codeanalyze | AST分析/代码图 | 13 |
| core-models | 实体/关系/知识图谱 | 6 |
| eidos | Schema定义/验证 | 24 |
| forge | 资产管理 | 11 |
| health-profile | 健康档案 | 2 |
| iris | 连接器(WPS/微信读书) | 10 |
| kairon-lib-events | 事件库 | 2 |
| kairon-observability | 可观测性 | 3 |
| kairon-pipeline | 数据处理管线 | 3 |
| kairon-plugin-sdk | 插件SDK | 1 |
| kairon-utils | 工具库 | 10 |
| kos | 知识操作系统 | 23 |
| kronos | 知识摄取 | 9 |
| minerva | 深度研究 | 37 |
| ontoderive | 本体推导 | 48 |
| sophia | 符号化研究 | 3 |

#### gbrain

| 指标 | 值 |
|------|-----|
| 版本 | 0.39.0 |
| 功能 | Postgres知识数据库·67 MCP tools |
| 测试 | 888 |
| 能力地图 | ✅ |

**核心能力**:
- Postgres 存储: 原生 Postgres 支持
- 混合 RAG: 关键词 + 语义搜索
- MCP 工具: 67 个 MCP 工具
- 知识图谱: 实体/关系/图谱

#### omo

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | AI Agent OS·治理·任务·债务 |
| 测试 | 145 |
| 能力地图 | ✅ |

**核心能力**:
- 治理引擎: X1-X4 治理框架
- 任务管理: 任务注册/执行/追踪
- 债务管理: 债务登记/评分/追踪
- 状态管理: 系统状态/健康度

#### metaos

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 编排引擎·决策门控·免疫 |
| 测试 | 41 |
| 能力地图 | ✅ |

**核心能力**:
- 决策门控: 决策分级/门控
- 免疫监控: 异常检测/熔断
- 路由: 任务路由
- 工作流引擎: DAG 执行/重试

---

### 2.5 L1 运行时

#### runtime

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 服务注册·健康·KEI沙箱 |
| 测试 | 46 |
| 能力地图 | ✅ |

**核心能力**:
- 服务注册: 服务发现/注册
- 健康监控: 心跳/健康检查
- 协议管理: 协议验证/执行
- KEI 沙箱: 安全沙箱执行

---

### 2.6 L0 协议层

#### ecos

| 指标 | 值 |
|------|-----|
| 版本 | 0.8.0 |
| 功能 | SSB签名链·MOF·X1-X4治理 |
| 测试 | 39 |
| 能力地图 | ✅ |

**核心能力**:
- SSB 签名链: 不可变日志/签名/验证
- 涌现度量: 系统涌现度计算
- MOF 元模型: M0-M3 元模型定义
- 治理框架: X1-X4 检查器/告警/历史

**L0 治理模块**:
- primitives: 治理原语
- checkers: X1-X4 检查器
- event_bus: 事件总线
- registry: 注册表
- optimization: 优化原语
- alert_engine: 告警引擎
- history_store: 历史存储

---

### 2.7 算力层

#### aetherforge

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 算力网格·LLM网关·群体智能 |
| 测试 | 23 |
| 能力地图 | ✅ |

**核心能力**:
- 算力网格: 分布式算力管理
- LLM 网关: LLM 路由/代理
- 群体智能: 多 Agent 协作
- 资源调度: 资源分配/调度

---

### 2.8 其他项目

#### omo-debt

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 技术债务评分 CLI |
| 测试 | 14 |
| 能力地图 | ✅ |

**核心能力**:
- 债务评分: Pattern 09 v2.0 评分算法
- 优先级: 债务优先级排序
- 对比: 多债务对比
- 健康度: 项目健康度分析

#### compute-mesh （已归档）

> `compute-mesh` 子模块已于 2026-06-16 归档。其 mesh-specific 代码（拓扑、调度、Worker、API）已并入 `projects/aetherforge/packages/mesh/`，`provider/` 层与 `aetherforge-gateway` 合并，不再作为独立子模块维护。
>
> 归档快照：`/_archived/compute-mesh/` · 新位置：`projects/aetherforge/packages/mesh/`

#### family-hub

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 家庭中心·家庭管理 |
| 测试 | 171 |
| 能力地图 | ✅ |

**核心能力**:
- 家庭管理: 家庭成员/信息管理
- 日程安排: 家庭日程/提醒
- 健康追踪: 健康数据追踪
- 财务管理: 家庭财务记录

#### hermes-console

| 指标 | 值 |
|------|-----|
| 版本 | 1.0.0 |
| 功能 | 控制台 UI |
| 测试 | 170 |
| 能力地图 | ✅ |

**核心能力**:
- 仪表板: 系统状态仪表板
- 任务管理: 任务列表/追踪
- 监控: 实时监控
- 配置: 系统配置

#### llm-gateway (已归档)

> **状态**: 已归档 — 能力已并入 [aetherforge/packages/gateway](../projects/aetherforge/packages/gateway/)  
> **最后版本**: 1.0.0  
> **归档日期**: 2026-06-16

**迁移说明**:
- LLM 网关核心能力迁移至 `aetherforge/packages/gateway/src/llm_gateway/`
- 历史代码保留在 `aetherforge/packages/gateway/src/llm_gateway/_legacy/`
- 新入口: `aetherforge gateway *` CLI / `aetherforge-mcp`

#### swarm-engine （已归档）

> `swarm-engine` 子模块已于 2026-06-16 归档。其群体智能模块已并入 `projects/aetherforge/packages/swarm/src/swarm_engine/`，不再作为独立子模块维护。
>
> 归档快照：`/_archived/swarm-engine/` · 新位置：`projects/aetherforge/packages/swarm/`

#### aetherforge-swarm-ext （已归档）

> `aetherforge-swarm-ext` 子模块已于 2026-06-16 归档。14 个唯一扩展模块已并入 `projects/aetherforge/packages/swarm/src/swarm_engine/ext/`，其余模块已由 `swarm-engine` 合并覆盖，不再作为独立子模块维护。
>
> 归档快照：`/_archived/aetherforge-swarm-ext/` · 新位置：`projects/aetherforge/packages/swarm/src/swarm_engine/ext/`

---

## 三、应用场景

### 3.1 知识管理场景

```
用户需求: "帮我搜索关于'治理框架'的所有文档"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: kos search "治理框架"                      │
│  2. cockpit MCP: governance_check(dimension="X1")           │
│  3. KOS 跨域搜索 → 返回相关文档                              │
│  4. 展示搜索结果 + 相关实体                                  │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, kos, gbrain
```

### 3.2 深度研究场景

```
用户需求: "帮我研究 X1-X4 治理框架的最佳实践"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: minerva research "X1-X4 治理框架"          │
│  2. Minerva 调用 8 引擎 + 4 LLM                            │
│  3. 生成研究报告 + 引用来源                                  │
│  4. 保存到 KOS 索引                                         │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, minerva, kos, gbrain
```

### 3.3 代码分析场景

```
用户需求: "分析 kairon 项目的代码质量"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: codeanalyze scan projects/kairon            │
│  2. AST 分析 + 代码图生成                                    │
│  3. 输出: 复杂度/依赖/审查建议                               │
│  4. 生成 Mermaid 代码图                                      │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, codeanalyze
```

### 3.4 治理检查场景

```
用户需求: "检查系统的治理状态"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: make x1-x4-check                           │
│  2. cockpit MCP: governance_check(dimension="all")          │
│  3. 运行 X1-X4 检查器                                       │
│  4. 输出: 检查结果 + 告警                                    │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, ecos, omo
```

### 3.5 资产管理场景

```
用户需求: "管理我的数字资产"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: forge list                                 │
│  2. 列出所有资产 + 状态                                      │
│  3. 同步资产到知识库                                        │
│  4. 生成资产报告                                            │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, forge, iris
```

### 3.6 平台集成场景

```
用户需求: "连接 WPS Note 和微信读书"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: iris connect wps                           │
│  2. iris 连接 WPS Note MCP                                  │
│  3. 同步笔记到 KOS                                          │
│  4. 跨平台搜索                                              │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, iris, kos
```

### 3.7 深度研究场景 (扩展)

```
用户需求: "帮我研究 AI Agent 的发展趋势"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. cockpit CLI: minerva research "AI Agent 发展趋势"       │
│  2. Minerva 调用 Semantic Scholar + ArXiv                   │
│  3. 交叉验证多个来源                                        │
│  4. 生成研究报告 + 预测                                      │
└─────────────────────────────────────────────────────────────┘

涉及项目: cockpit, minerva, iris
```

### 3.8 知识图谱场景

```
用户需求: "构建项目知识图谱"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. ontoderive derive projects/kairon                       │
│  2. 提取实体/关系                                           │
│  3. 生成知识图谱                                            │
│  4. 保存到 gbrain                                           │
└─────────────────────────────────────────────────────────────┘

涉及项目: ontoderive, gbrain
```

---

## 四、核心链路

### 4.1 知识搜索链路

```
用户 → cockpit CLI/MCP → agora (路由) → kos (搜索) → gbrain (存储)
                                  │
                                  └→ 返回结果 → cockpit 展示
```

### 4.2 深度研究链路

```
用户 → cockpit CLI → minerva (研究)
        │               │
        │               ├→ 8 引擎并行
        │               └→ 4 LLM 生成
        │
        └→ 保存到 KOS → gbrain 存储
```

### 4.3 治理检查链路

```
用户 → cockpit CLI/MCP → governance_check()
        │
        ├→ X1 审计链检查
        ├→ X2 抗熵检查
        ├→ X3 价值栈检查
        └→ X4 一致性检查
                │
                └→ 检查结果 → 告警处理 → 日志/Webhook
```

### 4.4 服务调用链路

```
Agent → agora MCP (resolve_bos_uri)
        │
        ├→ bos://memory/kos/search → kos
        ├→ bos://analysis/minerva/research → minerva
        ├→ bos://omo/eidos/validate → eidos
        └→ bos://forge/runtime/execute → runtime
```

### 4.5 数据流链路

```
数据源 → kronos (摄取) → kos (索引) → gbrain (存储)
                                        │
                                        └→ 搜索/查询 → 返回结果
```

### 4.6 资产同步链路

```
外部平台 → iris (连接) → forge (管理) → gbrain (存储)
                │
                ├→ WPS Note
                ├→ 微信读书
                └→ 其他平台
```

### 4.7 知识图谱构建链路

```
代码/文档 → ontoderive (推导) → eidos (Schema) → gbrain (存储)
                │
                └→ 提取实体/关系 → 生成图谱
```

### 4.8 群体智能协作链路

```
任务 → aetherforge/packages/swarm (编排) → aetherforge (算力) → 多 Agent 协作
                │
                └→ 结果聚合 → 返回
```

---

## 五、系统指标

### 5.1 项目统计

| 指标 | 值 |
|------|-----|
| 项目总数 | 17 |
| 活跃项目 | 15 |
| 归档项目 | 2 |

### 5.2 代码统计

| 指标 | 值 |
|------|-----|
| 测试文件 | 4,402 |
| 估算测试用例 | ~35,000+ |
| 能力地图 | 17/17 |
| CHANGELOG | 109 |
| Git Hooks | 18 |

### 5.3 治理指标

| 指标 | 值 |
|------|-----|
| debt_weight | 1.0 |
| debt_health | 100.0 |
| X1-X4 检查器 | 4 个 |
| 治理 MCP 工具 | 6 个 |

---

## 六、技术栈

### 6.1 Python 项目

| 工具 | 版本 | 项目 |
|------|------|------|
| Python | 3.13+ | kairon, agora, metaos, omo, ecos, runtime, aetherforge |
| 包管理器 | uv | 全部 Python 项目 |
| 格式化/Lint | ruff | kairon, agora, metaos, ecos |
| 测试框架 | pytest | 全部 Python 项目 |

### 6.2 TypeScript 项目

| 工具 | 版本 | 项目 |
|------|------|------|
| 运行时 | Bun | gbrain, family-hub, hermes-console |
| 构建 | Vite | family-hub, hermes-console |
| 测试 | bun test | gbrain |

---

## 七、部署架构

### 7.1 本地开发

```bash
# 安装
cd projects/kairon && uv sync
cd projects/gbrain && bun install

# 运行
cockpit status
kos search "关键词"
```

### 7.2 服务部署

```
agora:7431 (MCP SSE)
cockpit:8090 (Web Dashboard)
ecos:9090 (Dashboard)
runtime: FastAPI (服务注册)
```

---

## 八、文档索引

| 文档 | 说明 |
|------|------|
| ARCHITECTURE.md | 系统架构详细设计 |
| SYSTEM-OVERVIEW.md | 本文档 |
| CAPABILITY-MAP.md | 各项目能力地图 |
| USAGE-GUIDE.md | kairon 使用指南 |
| CHANGELOG.md | 版本变更记录 |
| CONTRIBUTING.md | 贡献指南 |
| LICENSE | MIT 许可证 |

---

## 九、子项目能力地图索引

| 项目 | 能力地图路径 |
|------|-------------|
| kairon | projects/kairon/CAPABILITY-MAP.md |
| agora | projects/agora/CAPABILITY-MAP.md |
| cockpit | projects/cockpit/CAPABILITY-MAP.md |
| ecos | projects/ecos/CAPABILITY-MAP.md |
| gbrain | projects/gbrain/CAPABILITY-MAP.md |
| metaos | projects/metaos/CAPABILITY-MAP.md |
| omo | projects/omo/CAPABILITY-MAP.md |
| runtime | projects/runtime/CAPABILITY-MAP.md |
| aetherforge | projects/aetherforge/CAPABILITY-MAP.md |
| l4-kernel | projects/l4-kernel/CAPABILITY-MAP.md |
| model-driven | projects/model-driven/CAPABILITY-MAP.md |
| omo-debt | projects/omo-debt/CAPABILITY-MAP.md |
| compute-mesh | **ARCHIVED** — 见 `projects/aetherforge/packages/mesh/` |
| family-hub | projects/family-hub/CAPABILITY-MAP.md |
| hermes-console | projects/hermes-console/CAPABILITY-MAP.md |
| llm-gateway | **ARCHIVED** — 见 [aetherforge/packages/gateway](../projects/aetherforge/packages/gateway/) |
| swarm-engine | **ARCHIVED** — 见 [aetherforge/packages/swarm](../projects/aetherforge/packages/swarm/) |
| aetherforge-swarm-ext | **ARCHIVED** — 见 [aetherforge/packages/swarm/src/swarm_engine/ext](../projects/aetherforge/packages/swarm/src/swarm_engine/ext/) |

---

*版本: 1.0.0 · 更新: 2026-06-12*
