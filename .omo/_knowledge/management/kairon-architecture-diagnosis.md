---
category: guides
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# kairon 包架构诊断与重构方案

> 2026-06-06 | 系统性分析
> 24 包 · 310K 行源码 · 6 库 + 17 工具

---

## 一、现状诊断

### 1.1 依赖拓扑

```
                           用户层
          ┌─────────────────┼─────────────────┐
          │                 │                 │
        wksp(15K)    kairon-governance(2.5K)  metaos(6K)
          │                 │                 │
          └─────────┬───────┴────────┬────────┘
                    │                │
          ┌─────────▼────────────────▼────────┐
          │         编排层/基础设施            │
          │                                   │
          │  agora(38K)  agent-runtime(20K)   │
          │  forge(8K)   cron-service(2K)     │
          │  llm-gateway(3K)   codeanalyze(7K)│
          └─────────┬────────────────┬────────┘
                    │                │
          ┌─────────▼────────────────▼────────┐
          │        知识工程流水线              │
          │                                   │
          │  kronos → ontoderive → minerva   │
          │  iris → sophia → eidos           │
          │  kos → ecos → sharedbrain-bridge │
          └─────────┬─────────────────────────┘
                    │
          ┌─────────▼─────────────────────────┐
          │     数据模型层                     │
          │                                   │
          │  core-models(1.6K)                │
          │  eidos(35K)     ← 过重            │
          │  ssot(14K)      ← 过重            │
          │  shared-lib(38K) ← 倾倒场          │
          │  engine-core(25K) ← 过重           │
          └───────────────────────────────────┘
```

### 1.2 核心问题 (7 个)

| # | 问题 | 涉及包 | 影响 |
|---|------|--------|------|
| **P1** | **治理工具重复** | `kairon-governance` vs `projects/omo` | 同一职责两个实现 |
| **P2** | **shared-lib 是倾倒场** | 38K 行, 无明确边界 | 谁都在用, 谁都不敢拆 |
| **P3** | **eidos 与 core-models 职责重叠** | eidos(35K) vs core-models(1.6K) | Schema 和数据模型应该是一层 |
| **P4** | **engine-core 过大** | 25K 行 (事件总线/任务存储/重试/能力目录) | 单一职责违反 |
| **P5** | **agora 超大** | 38K 行, 90+ 文件 | 路由/认证/仪表板/A2A/代理混在一起 |
| **P6** | **ssot 是库但 14K 行** | 无 CLI, 14K 行纯库 | 太大了, 可能有可拆部分 |
| **P7** | **知识流水线边界模糊** | kos(14K) - minerva(25K) - eidos(35K) | 三者职责边界不清晰 |

---

## 二、干净架构方案

### 2.1 分层原则

```
L0 — 数据模型 (不变层)
L1 — 基础设施 (可插拔)
L2 — 知识工程 (流水线)
L3 — 编排/治理 (运行时)
L4 — 用户入口 (CLI/UI)
```

### 2.2 新包结构 (23 → 18 包)

#### L0: 数据模型层 (3 包)

| 新包 | 来源 | 职责 | 规模 |
|------|------|------|------|
| **kairon-types** | core-models + eidos schema | 实体/关系/溯源/图谱/Schema 类型 | ~5K |
| **kairon-domain** | ssot 的事实面 | 领域实体定义、不变量 | ~5K |
| **kairon-utils** | shared-lib 的工具函数 | 纯工具: 日期/路径/IO/脱敏 | ~3K |

#### L1: 基础设施层 (4 包)

| 新包 | 来源 | 职责 | 规模 |
|------|------|------|------|
| **kairon-engine** | engine-core 精简 | 事件总线/任务调度/重试策略 | ~8K |
| **kairon-llm** | llm-gateway | LLM 提供者抽象 | ~3K |
| **kairon-gateway** | agora 精简 (路由+代理) | MCP 服务发现/路由/代理 | ~15K |
| **kairon-executor** | agent-runtime 核心 | Agent 执行引擎 | ~12K |

#### L2: 知识工程层 (6 包)

| 新包 | 来源 | 职责 | 规模 |
|------|------|------|------|
| **kairon-ingestion** | kronos + iris | 知识摄取 + 连接器 | ~8K |
| **kairon-derivation** | ontoderive | 事实推导 | ~6K |
| **kairon-knowledge** | kos + eidos storage | 知识存储/索引/搜索 | ~12K |
| **kairon-research** | minerva | 深度研究 | ~20K |
| **kairon-paradigm** | sophia | 范式编译 | ~1.5K |
| **kairon-analysis** | codeanalyze | 代码/文档分析 | ~7K |

#### L3: 编排/治理层 (3 包)

| 新包 | 来源 | 职责 | 规模 |
|------|------|------|------|
| **kairon-runtime** | agent-runtime CLI + cron-service | 任务调度/执行/定时 | ~10K |
| **kairon-governance** | kairon-governance (现有) | 巡检/ADR/路由 (保留, 与 omo 对齐) | ~2.5K |
| **kairon-forge** | forge | 资产/工具注册发现 | ~8K |

#### L4: 用户层 (2 包)

| 新包 | 来源 | 职责 | 规模 |
|------|------|------|------|
| **kairon-cli** | wksp CLI | 统一用户命令行入口 | ~12K |
| **kairon-dashboard** | agora dashboard + wksp dashboard | Web 仪表板 | ~5K |

#### 废弃/合并 (5 包)

| 原包 | 去向 | 理由 |
|------|------|------|
| **shared-lib** | 拆入 kairon-utils + 各包 | 倾倒场, 无拥有者 |
| **eidos** | 拆入 kairon-types + kairon-knowledge | 35K 行, 职责混杂 (类型+存储) |
| **engine-core** | 拆入 kairon-engine + kairon-executor | 25K 行, 两个不同职责 |
| **ssot** | 拆入 kairon-domain + kairon-knowledge | 14K 行, 事实面+知识面混同 |
| **ecos** | 拆入 kairon-knowledge + kos | 认知层实质是知识存储的增强 |
| **metaos** | 拆入 kairon-governance | 编排/治理应合并 |

### 2.3 依赖方向

```
L4: kairon-cli ← kairon-dashboard
     ↓                    ↓
L3: kairon-runtime ← kairon-governance ← kairon-forge
     ↓                    ↓
L2: kairon-ingestion → kairon-derivation → kairon-research
     ↓                    ↓
L1: kairon-engine ← kairon-gateway ← kairon-llm
     ↓                    ↓
L0: kairon-types ← kairon-domain ← kairon-utils
```

**规则**: 依赖只能向下，不能向上。L2 不能依赖 L3，L3 不能依赖 L4。

---

## 三、对比分析

| 维度 | 当前 (24 包) | 新架构 (18 包) | 变化 |
|------|-------------|---------------|------|
| 总包数 | 24 | 18 | -6 |
| 大包 (>15K) | 8 (shared-lib/agora/eidos/ssot/engine-core/minerva/agent-runtime/wksp) | 2 (kairon-research/kairon-gateway) | -6 |
| 职责重复 | 多处 (eidos/core-models, kairon-governance/omo) | 无 | ✅ |
| 依赖方向 | 混乱 (agora 依赖 minerva/kos/eidos) | 严格向下 | ✅ |
| 用户入口 | 多个 CLI (workspace, kairon-governance, 各包独立) | kairon-cli 统一 | ✅ |
| 治理工具 | kairon-governance + projects/omo | kairon-governance (对齐 omo) | ✅ |
| shared-lib | 38K 倾倒场 | 拆散 | ✅ |

---

## 四、实施建议

### 不建议立即做全量重构

24 包 → 18 包的重构是**架构级的断裂式变更**。当前代码 310K 行，全量重构需要冻结开发 2-4 周，风险极高。

### 建议的渐进路径

| 阶段 | 操作 | 风险 | 收益 |
|------|------|------|------|
| **P0 立即** | shared-lib 标记 deprecation, 新代码不用 | 低 | 阻止倾倒场扩大 |
| **P1 短期** | kairon-governance 与 omo 对齐协议 | 低 | 消除治理重复 |
| **P2 中期** | agora 拆 I0 功能到 gateway | 中 | 减少 38K 负担 |
| **P3 长期** | eidos 类型部分合并到 core-models | 高 | 消除模型重复 |
| **P4 远期** | 全量按 4 层结构拆分 | 极高 | 干净架构 |
