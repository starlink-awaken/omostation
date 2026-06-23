---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 12 主计划：系统能力生态构建

> 日期: 2026-06-01 | 状态: completed
> 前置: Phase 11 完成 (SSOT修复 → 核心债务 → 用户层 → 深度加固)
> 愿景: 系统能力生态底座 — capability registry + scenario MVP + one fusion pilot + audit gates
> Canonical: yes
> Entry gate: `phase12-planning-gate.md`
> Deferred scope: `phase14-deferred-ecosystem-backlog.md`

---

## 一、阶段定位

Phase 11 完成了"系统能力 & 用户层使能"——把架构基础转化为可交付模块。  
**Phase 12 升级到"系统能力生态构建"**，但只做底座闭环，不做全生态吞并。Phase 12 的核心是把能力描述、注册、发现、绑定和最小场景跑通：

| Phase | 主题 | 范围 | 核心动作 |
|-------|------|------|---------|
| P10 | 规则统一 | OMO 治理文件 | 规则注册表 + 归一化 |
| P11 | 能力使能 | 4 项目 + 用户层 | SSOT 修复 + 债务攻防 + 前端落地 |
| **P12** | **能力生态底座** | 核心项目 + 代表性外部能力 | **注册/发现/绑定/最小编排/一个融合 pilot** |

### 1.1 阶段主题

> **Theme**: Capability ecosystem construction（系统能力生态构建）
> **副主题**: 从项目内集成到可审计能力生态，建立注册、发现、绑定、最小编排和受控融合机制

---

## 二、核心架构设计 — 能力生态层 (CEL)

在现有 **4+1+3+I** 架构上增加一个跨层横切面——**能力生态层 (Capability Ecosystem Layer, CEL)**：

```
原有架构:                             Phase 12 演进:
                                    ┌─────────────────────────┐
                                    │  CEL 能力生态层 (横切)    │
                                    │  注册 · 发现 · 绑定 ·     │
                                    │  连接 · 扩展 · 编排       │
                                    ├─────────────────────────┤
P0  用户入口层                       P0  用户入口层
I0  Agora 集成织物                   I0  Agora 集成织物 (+ 能力路由)
L1  契约层                           L1  契约层 (+ 能力契约)
L2  能力层                           L2  能力层 (+ SharedWork 融合)
L3  协作层                           L3  协作层 (+ 场景编排)
L4  元层                             L4  元层 (+ 生态治理)
SB  合规控制面                       SB  合规控制面
agentmesh Agent 运行时               agentmesh (+ Gateway)
gbrain 知识脑                        gbrain (+ 记忆后端)
```

**CEL 不改变 10 条不可变法则**。它是在 I0 之上的轻量横切面，只负责：
- 能力元模型定义 (Capability/Skill/Tool/Plugin/Connector)
- 能力注册表 (Registry)
- 能力发现 (Discovery)  
- 能力绑定 (Binding)
- 场景编排 (Orchestration)

Phase 12 禁止把 CEL 扩张为新的业务层。批量外部项目吸收、架构模式全面落地、文章知识图谱扩张、插件市场等工作进入 `phase14-deferred-ecosystem-backlog.md`。

---

## 三、五维机制设计

### 3.1 注册 (Register) — 能力声明与发现

**机制**: 轻量能力声明文件 + 全局注册表

```
每个能力单元 (包/插件/工具/CLI) 携带:
  capabilities.yaml 或 capabilities.json
  └─ id: unique_name
  └─ type: skill | tool | plugin | connector | cli | package
  └─ protocol: mcp | cli | api | local
  └─ entrypoint: command | module | url
  └─ metadata: description, version, deps, tags, scenario_tags
  └─ lifecycle: active | deprecated | experimental | external

全局注册表:
  .omo/registry/
  └─ capabilities/            ← 能力注册
  └─ packages/                ← 包管理注册
  └─ connectors/              ← 连接器注册
  └─ scenarios/               ← 场景注册
  
能力扫描:
  omo capability scan          ← 全量扫描所有目录
  omo capability register      ← 手动注册
  omo capability discover      ← 按条件发现
```

**启发来源**: agency-agents (文件系统即注册中心), Anthropic Plugins (`.mcp.json`), LiteLLM (YAML 声明)

### 3.2 连接 (Connect) — 组件发现与通信

**机制**: MCP 协议作为标准连接通道 + 能力路由

```
Agent/Scenario → I0/Agora → CEL Router → 目标 Capability
                                        → MCP Server
                                        → CLI subprocess
                                        → API call
                                        → Local import

CEL Router 功能:
  - 能力查找 (按标签/类型/场景)
  - 连接协商 (协议选择)
  - 健康检查 (Live/Ready)
  - 熔断降级
```

**启发来源**: DeepCode (MCP 中央编排), Claude Managed Agents (Brain/Hands/Session), Daytona (MCP Sandbox 桥梁)

### 3.3 扩展 (Extend) — 新能力融入

**机制**: 插件市场 + 能力吸收管道

```
外部能力 → CEL Extend Pipeline:
  1. 能力扫描 (Scan)         — 自动发现新能力声明
  2. 能力验证 (Validate)      — 检查格式/协议/安全性
  3. 能力注册 (Register)      — 写入全局注册表
  4. 能力测试 (Test)          — 烟雾测试
  5. 能力发布 (Publish)       — 标记可用

插件市场:
  omo market list             ← 浏览可用能力
  omo market install <name>   ← 一键安装/注册
  omo market publish <path>   ← 发布新能力
```

**启发来源**: Anthropic Knowledge-Work-Plugins, Ruflo 插件市场, context-hub (社区 PR)

### 3.4 集成 (Integrate) — 外部项目吸收

**机制**: 遵循第 9 条法则"融合是吸收而非复制"

```
SharedWork 集成管道:
  Level 1 — 注册引用 (Register Ref)
    └─ 不复制代码，只注册为外部能力引用
    └─ capabilities.yaml: {source: SharedWork/Agent/OpenManus, type: external}
  
  Level 2 — 封装适配 (Wrap Adapter)
    └─ 编写轻量 MCP 适配器包装
    └─ 通过 I0 暴露为 MCP 工具
  
  Level 3 — 深度吸收 (Deep Absorb)
    └─ 核心逻辑按 "吸收而非复制" 原则重写整合
    └─ Phase 12 只允许 selected pilot 走此路径，其余进入 Phase 14 backlog

候选映射 (来自 architecture-final-vision):
  Phase 12 pilot candidate: LiteLLM → agentmesh Gateway
  Phase 12 pilot candidate: memU → gbrain 记忆后端
  Phase 14 backlog: GitNexus → KOS index
  Phase 14 backlog: Graphify → KOS index
  Phase 14 backlog: UltraRAG → minerva
  Phase 14 backlog: Firecrawl → kronos
  Phase 14 backlog: MinerU → kronos
  Phase 14 backlog: AgentLaboratory → minerva
  Phase 14 backlog: nuwa-skill → KOS self
```

### 3.5 绑定 (Bind) — 运行时关联

**机制**: 场景驱动的运行时能力绑定

```
场景定义 (scenario.yaml):
  └─ id: research-pipeline
  └─ capabilities: [kronos, ontoderive, minerva, gbrain-search]
  └─ bindings:
       input: kronos → ontoderive (事实推导)
       output: minerva → gbrain (知识存储)
  └─ lifecycle: active

运行时绑定:
  CEL Loader 读取场景定义 → 查找注册表 → 
  建立 MCP 连接链 → 健康检查 → 场景就绪

绑定类型:
  - 静态绑定 (编译时声明)
  - 动态绑定 (运行时按需解析)
  - 事务绑定 (多能力原子绑定)
```

**启发来源**: TrustGraph (Context Core), Ruflo (Swarm 编排), Claude Managed Agents (Session 持久化)

---

## 四、战略目标

| 编号 | 目标 | 关联维度 | 关键度量 |
|------|------|---------|---------|
| S1 | **能力生态元模型** — 定义 Capability/Skill/Tool/Plugin/Connector 元模型与注册协议 | Register | 元模型完成、注册表可用 |
| S2 | **能力扫描基线** — 扫描并注册核心 workspace 能力单元 | Register/Connect | 注册 ≥50 个能力单元，SharedWork 只做抽样/分类 |
| S3 | **单一融合 pilot** — 从 LiteLLM 或 memU 中选择一个 P0 pilot | Integrate | 1 个 pilot 完成，另一个进入 Phase 14 backlog |
| S4 | **场景编排 MVP** — 构建最小场景驱动能力编排 | Bind/Extend | ≥1 个可运行场景 |
| S5 | **包生态 dry-run** — 最小 `omo pkg` dry-run 和依赖声明草案 | Connect/Register | dry-run 可报告差异，不直接改依赖 |
| S6 | **知识化策略** — 定义文章/外部知识 ingestion policy，不追求数量 | Integrate | policy + 5 条样例记录 |
| S7 | **架构验证与收敛** — 交叉审计 + 红队验证 + Phase 13/14 交接 | 治理 | 交叉审计通过，Phase 14 backlog 明确 |

---

## 五、健康目标

| 指标 | Phase 11 结束 (估算) | W1 | W2 | W3 | W4 |
|------|:-------------------:|:--:|:--:|:--:|:--:|
| 健康分 | 97 | 90 | 91 | 92 | 93 |
| 注册能力数 | — | 50 | 75 | 100 | 100+ |
| SharedWork 融合 | — | 分类抽样 | pilot 选择 | 1 个 pilot | backlog |
| 可运行场景 | — | — | 1 | 1-2 | 1-2 |
| CLI 统一度 | 5 套 CLI | 5 | 4 | 4 | 4 |
| 技术文章入库 | — | policy | 5 样例 | 5 样例 | backlog |

> 健康分目标不再因范围扩张主动降级；Phase 12 只接收可控底座范围。

---

## 六、Wave 全景

```
Wave 1 — 能力生态元模型 + 核心扫描基线       (入口: P11 完成, 健康分 ≥97)
Wave 2 — 注册表工具链 + 场景 MVP + pilot ADR (入口: W1 元模型完成)
Wave 3 — 单一融合 pilot + 包生态 dry-run      (入口: W2 场景 MVP 可用)
Wave 4 — 架构验证 + 红队 + P13/P14 交接       (入口: W3 pilot 完成)
```

**Sequencing rule**: Wave 串行，one-packet-at-a-time

---

## 七、Go/No-Go 规则

### 7.1 进入条件 (从 Phase 11)

- [x] Phase 11 所有 Wave 关闭完毕
- [x] Phase 11 健康分达到 Phase 12 entry acceptance
- [x] `pip install kairon` local source-install baseline 可用
- [x] FastMCP 迁移完成
- [x] Hermes 断链 ≤10
- [x] human-approved request promoted live SSOT through Phase 12 completion

### 7.2 Wave 间过渡

| 过渡 | 条件 |
|------|------|
| W1→W2 | 能力元模型定稿 + 核心扫描完成 (≥50 注册) |
| W2→W3 | 注册/发现 CLI 可用 + 1 个场景 MVP + pilot ADR |
| W3→W4 | 单一 P0 pilot 完成 + package dry-run 通过 |
| W4→P13/P14 | 交叉审计通过 + 红队报告 + Phase 13 gate 更新 + Phase 14 backlog 登记 |

### 7.3 整体 Go/No-Go

**GO 条件**:
1. 健康分 ≥93
2. 注册能力 ≥100
3. 1 个 P0 融合 pilot 完成并可回滚
4. ≥1 个场景可运行并有 trace
5. 文章/外部知识 ingestion policy 完成，样例可检索
6. `omo pkg` dry-run 可报告依赖差异
7. Phase 14 deferred backlog 已登记
8. 交叉审计 8 检查点全通过

**No-Go 条件**:
1. 能力元模型在 W1 结束时未定稿
2. 注册表工具链在 W2 结束时不可用
3. 注册表工具链在 Phase 结束时不可用
4. 健康分未达标 (≤90)

---

## 八、交叉审计设计

### 8.1 审计检查点 (8 个)

| # | 检查点 | 审计对象 | 标准 | 时机 |
|:-:|--------|---------|------|------|
| A1 | system.yaml | state/system.yaml | Phase/Wave/健康分一致 | Wave 1 基线 + 每 Wave |
| A2 | 注册表一致性 | registry/ | 核心能力单元有注册记录，外部能力有 backlog 或 exclusion reason | Wave 2+ |
| A3 | 能力声明完整性 | 各 capabilities.yaml | 必填字段齐全 | Wave 2+ |
| A4 | 场景可用性 | scenarios/ | 至少 1 个场景可通过 I0 执行 | Wave 3+ |
| A5 | 融合深度 | selected pilot | 选定 pilot 有实际适配器或代码，未选项进入 Phase 14 backlog | Wave 4 |
| A6 | 架构法则遵守 | 10 条不可变法则 | 未违反 (尤其是 I0 隔离/MCP 协议) | 每 Wave |
| A7 | 包生态一致性 | omo pkg 状态 | 依赖声明与安装一致 | Wave 3+ |
| A8 | 健康分轨迹 | system.yaml | 从 P1→P12 连续可追溯 | Phase 结束 |

### 8.2 继承的审计教训

| 教训 | 来源 | Phase 12 应对 |
|------|------|-------------|
| system.yaml 不同步 (C1) | P10 | 只允许 human-approved promotion task 更新 live SSOT |
| goals 无当前 Phase (C2) | P10 | 只允许 human-approved promotion task 更新目标源 |
| plans/README 误导 (C3) | P10 | Phase 12 program/waves 必须注册为 pre-planning |
| 控制面 degrade (C4) | P10 | 能力健康心跳自动上报 |
| 债务不追踪 (M1) | P10 | 注册表自带债务标记 |
| D2/D3 反复延期 | P10→P11 | Phase 12 必须 P11 完成后才启动 |

---

## 九、红队分析 (R1-R6)

| # | 风险 | 等级 | 缓解 |
|:-:|------|:----:|------|
| R1 | **范围膨胀失控** — 90 个项目全部融合不可能在 1 个 Phase 完成 | 🔴 Critical | Scope 严格限制: 只做 1 个 P0 pilot，其余进入 Phase 14 backlog |
| R2 | **CEL 层增加复杂度** — 新层可能违反 I0 隔离法则 | 🔴 Critical | CEL 是横切层非新层, 不承载业务逻辑; 在 I0 之上但仅做路由/注册/发现 |
| R3 | **元模型过度设计** — 能力元模型过于复杂导致无人使用 | 🟠 Major | MVP 元模型仅 5 个字段, 先运行再优化 |
| R4 | **SharedWork 项目质量参差** — 多数项目仅为克隆读代码, 未做深度开发 | 🟠 Major | Level 1 注册引用为主, 仅有价值项目走 Level 2/3 |
| R5 | **技术文章去重与质量** — 微信文章质量不一, 需过滤 | 🟡 Minor | 自动摘要 + 质量评分过滤 |
| R6 | **跨包管理器冲突** — uv/brew/npm/pip 版本冲突 | 🟡 Minor | `omo pkg sync` 依赖解析 + 冲突报告 |

---

## 十、参考文件索引

| 文件 | 用途 |
|------|------|
| `.omo/plans/architecture-final-vision.md` | 终极架构蓝图 + 10 法则 + SharedWork 融入路线 |
| `.omo/INSIGHTS-AND-ROADMAP.md` | v0.2→v0.5 路线图 + 6 深度洞察 |
| `.omo/INVENTORY.md` | 项目全量清单 |
| `.omo/summaries/data-flow.md` | 三段式数据流 + format_version |
| `.omo/_knowledge/management/phase10-cross-audit.md` | 交叉审计方法论 (C1-C4) |
| `.omo/plans/phase11-program-plan.md` | Phase 11 主计划 (前置条件) |
| `SharedWork/INDEX.md` | SharedWork 23 分类 ~90 项目索引 |
