---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 系统能力层 + 用户使用层 — 全景梳理与建设规划

> 日期: 2026-05-31 | 状态: v2 (补充遗漏文档审计结果)
> 输入: MASTER-BLUEPRINT、PROJECTS.yaml、Phase 5-10 系列文档、architecture-final-vision、scenario-analysis、PRODUCT-ARCH-JOURNEY、ARCH-AUDIT-2026-05、DEBT-ANALYSIS、Phase1-6 Review、Phase10 Cross Audit、Phase9 Debt Cleanup、data-flow、INSIGHTS-AND-ROADMAP、INVENTORY、provider-plane、control/current、freshness/current、GOVERNANCE_PLAN、ARCH-AUDIT-v2、AUDIT、P1_PROJECT_HEALTH、KNOWLEDGE_ARCH、KOS_MIGRATION_IMPACT
> 说明: 本文是历史分析输入，不是当前项目拓扑或运行时事实源。当前项目身份/状态/路径以 `/.omo/PROJECTS.yaml` 为准；架构边界以 `/docs/PANORAMA.md` 与各项目 `ARCHITECTURE.md` / `CALLCHAIN.md` / `BOUNDARY.md` 为准；运行时阶段以 `/.omo/goals/current.yaml` / `/.omo/state/system.yaml` 为准。

---

## 补充：遗漏文档关键发现

> 本节基于第二次 `omo/` 全面扫描发现的 ~25 份遗漏文档，以下仅列举直接影响规划的前提性结论。

### A. 架构前提性洞察

| # | 发现 | 来源 | 影响 |
|---|------|------|------|
| A1 | **"三层架构"是概念层不是代码层** — Eidos/KOS/OntoDerive 之间无硬依赖。所有集成通过 `try/except ImportError`（可选适配器）和 CLI subprocess 实现 | ../_knowledge/management/ARCH-AUDIT-2026-05.md | 架构解耦已做到极致，代价是跨层数据交换必须序列化 JSON，无类型安全 |
| A2 | **唯一真·硬依赖**: Agora→OntoDerive 的 12+ hard imports. 其余 0 硬依赖 | ../_knowledge/management/ARCH-AUDIT-v2.md | 解耦优先级最高 |
| A3 | **KOS 0 消费者**: 无项目 `import kos`，KOS 是纯 CLI 工具 | ../_knowledge/management/DEBT-ANALYSIS.md | API 未经验证，设计缺陷不自知 |
| A4 | **模型统一度 ~80%**: Eidos/OntoDerive/Minerva 已归一化 MetaType。未统一: OntoDerive Inference/Scheme, Minerva Relation, KOS 存储格式 | ../_knowledge/management/ARCH-AUDIT-v2.md | 元模型驱动设计的杠杆效应已验证 |
| A5 | **全链路就绪 ≠ 产品就绪**: 每个工具都有关键粗放之处（KOS 索引器、Eidos MCP 手写 JSON-RPC、Pipeline 硬编码） | ../_knowledge/design/INSIGHTS-AND-ROADMAP.md | v0.x 工具链需要生产就绪改造 |
| A6 | **适配器模式的隐藏成本**: `try/except ImportError` 把集成失败从编译时推到了运行时 | ../_knowledge/design/INSIGHTS-AND-ROADMAP.md | 应逐步替换为 Protocol/ABC 契约 |

### B. 健康与控制面状态

| # | 发现 | 数据来源 | 当前值 |
|---|------|---------|:------:|
| B1 | **system.yaml**: Phase 10 W2 active, 97/100 tasks, health 90 | state/system.yaml | ✅ 已更新 |
| B2 | **控制面 degrade**: freshness_score 70, `state_update_stale`，建议 refresh state summary | _delivery/task-center/control/current.yaml | ⚠️ 需修复 |
| B3 | **Provider 平面**: 单 provider (DeepSeek), OpenRouter 余额 $26.72, LiteLLM 1 健康 1 不健康 (gpt-4o 挂了) | state/provider-plane.yaml | 🟢 可用 |
| B4 | **项目健康评分 (12项目)**: Agora/OntoDerive A, Sophia/Eidos A-, Minerva B+, KOS B, eCOS B-, SharedBrain C-, Forge D | ../_knowledge/management/ARCH-AUDIT-2026-05.md | 两极分化 |

### C. 数据流全景

```
Kronos (摄取) ──► OntoDerive (事实推导) ──► Minerva (深度研究) ──► 输出
    │                    │                       │
    ▼                    ▼                       ▼
RawContent JSON     facts/ Markdown         SQLite KnowledgeStore
                        │                       │
                        └── Eidos Schema (KnowledgeCard / Fact / OntologyNode)
```

所有 MCP 工具输出必须带 `format_version`（已完成: kronos-v1, ontoderive-v1, minerva-v1, sophia-v1, agora-v1, pallas-v1）

### D. 债务遗漏补充（来自 Phase 10 交叉审计）

| ID | 发现 | 严重度 | 说明 |
|:--:|------|:-----:|------|
| C1 | system.yaml 与实际系统状态不同步 | 🔴 Critical | Phase 10 交叉审计发现 `current_phase: 8` 但事实已到 Phase 9 (注: 当前已修复为 phase:10) |
| C2 | goals/current.yaml 无 Phase 9/10 目标条目 | 🔴 Critical | 目标-任务链路断裂 |
| C3 | plans/README.md Phase 8 仍标 active, 无 Phase 10 条目 | 🔴 Critical | 注册表误导 |
| C4 | 控制面 degrade (freshness 70) | 🔴 Critical | 新鲜度异常，系统信号不健康 |
| M1 | 产品债务计数 10→实际只有 6 项 | 🟠 Major | 计数不准确 |
| M2 | D7 orphaned task 在 3 Wave 中均未分配 | 🟠 Major | 规划中的孤儿 |
| M3 | 健康基线"93-95"是假设而非实际 | 🟠 Major | 需 re-baseline |

### E. 其他关键文档摘录

| 文档 | 核心内容 |
|------|---------|
| Phase 1-6 Review | 全 6 阶段回顾: 健康 75→80→88→90→90→90; 使用方式 CLI→MCP→Hermes→CI→Worker Ops→治理→自运维 |
| Phase 9 Debt Cleanup | 25 项债务/4 类别/3 Wave; 红队分析: R1(空口号) R2(无增长) R3(技术债无尽头) |
| KNOWLEDGE_ARCH | 知识资产散落四地 (knowledge/ kos/ ontoderive/ minerva/), 无统一访问层 |
| model-benchmark | Eidos 6 个核心 Schema 类型字段定义 (KnowledgeCard/Fact/OntologyNode/Relation) |
| AUDIT.md | SharedBrain 健康(有测试), Agora 58 tests, Minerva 250 tests 但有 109MB 临时文件 |
| P1_PROJECT_HEALTH | Sophia 保留并继续, Pallas 保留薄层, BOS-Skill-CLI 70.78% 覆盖 |

---

## 第一部分：系统能力层（projects/）

### 1. 全景

```
系统能力层 = 4 项目 + 5 根仓库
├── kairon/         5.1MB Python monorepo (18+ 包)
│   ├── L1 契约 (5): core-models, eidos, family-models, work-models, media-models
│   ├── L2 能力 (10): kronos, minerva, sophia, ontoderive, ssot, codeanalyze,
│   │                 eu-pricing, token-juicer, memory-tree, bf-search
│   ├── L3 协作 (8): forge, kos, iris, cross-domain, kems-runtime,
│   │                 trust-layer, skill-router, sharedbrain-bridge
│   ├── L4 元层 (8): agent-runtime, metaos, ecos, cron-service, wksp,
│   │                 family-os, kos-health, device-orchestrator
│   └── I0 路由: agora (agora 包, MCP 统一收敛)
│
├── SharedBrain/    71K lines / 14 organs / 0 测试
│   ├── 合规控制面、EU 经济、数字免疫、身份桥接、自愈、语音处理
│   └── 风险: 210 万行零测试，最大技术债务
│
├── agentmesh/      TypeScript monorepo (7 packages)
│   ├── MCP 网关、LLM 路由、工具注册、任务编排
│   └── Fastify :3000, 14 endpoints
│
├── gbrain/         TypeScript, 19 engine modules
│   ├── PGLite + Postgres 双引擎, 144+ tests
│   └── 74 MCP tools + memU 后端
│
├── _archived/      22 项已归档项目
└── ops/            运维中心 (32 MCP tools)
```

### 2. 已有规划基础（.omo 中已有文档）

| 项目 | 已有规划文档 |
|------|-------------|
| **kairon** | Phase 5-10 设计文档体系, L1-L4 分层设计, 能力增长矩阵 (MASTER-BLUEPRINT §IV) |
| **SharedBrain** | `sharedbrain-kairon-integration.md`, `comprehensive-architecture-audit.md` |
| **agentmesh** | Phase 5-8 设计文档, `safe-mesh-rbac-deployment-roadmap.md` (D2 user journey, RBAC) |
| **gbrain** | Phase 5-6 知识脑设计, `architecture-final-vision.md` |
| **跨项目** | `PROJECTS.yaml`, `../_knowledge/design/MASTER-BLUEPRINT.md`, `TRUTH/INDEX.md` |
| **能力增长** | Phase 1(17→19包) → 2(19→24) → 3(24→28) → 4(28→30) → 5-10(持续) |
| **MCP 增长** | 当前 33+ → P1 50+ → P2 80+ → P3 100+ → P4 130+ → P∞ 150+ |

### 3. 关键指标

| 指标 | 数值 |
|------|------|
| 项目数 | 4 active + 1 archived |
| kairon 包 | 17 (详细分类见 `../_truth/INVENTORY.md`: 4 运行时+4 知识工程+3 研究+3 OS+2 通用+1 核心) |
| SharedBrain | ~83,778 .py 文件 / 14 organs / 零测试 (210 万行最大风险) |
| agentmesh | 7 packages / ~5,148 .ts 文件 |
| gbrain | ~1,257 .ts 文件 / 19 engine modules / 144+ tests / 74 MCP tools |
| MCP 工具总量 | ~100+ |
| 测试覆盖 | agora 238✅ / ontoderive 204✅ / minerva 258⚠️ / eidos 57✅ / kos 58❌ / sophia 87✅ / eCOS 98⚠️ |
| 项目健康 | agora/ontoderive **A** / sophia/eidos A- / minerva B+ / kos **B** / eCOS B- / SharedBrain **C-** / Forge **D** |
| 模型统一度 | **~80%** (Eidos/OntoDerive/Minerva 已归一化 MetaType; 未统一: OntoDerive Inference, Minerva Relation, KOS 存储) |
| Provider | **DeepSeek** (单一 provider), OpenRouter 余额 $26.72, LiteLLM: gpt-4o 不健康 |
| 控制面健康 | **degrade** (freshness 70, `state_update_stale`) |

### 4. 已知债务（综合 phase10-planning-analysis + 交叉审计 + 遗漏文档）

| 债务 | 等级 | 来源 | 跨越阶段 | 影响 |
|------|:----:|:----:|:--------:|------|
| **C1** system.yaml 状态不同步 | 🔴 Critical | 交叉审计 | P8→P10 | 系统 SSOT 与事实不符 |
| **C2** goals/current.yaml 无 Phase 9/10 目标 | 🔴 Critical | 交叉审计 | P8→P10 | 目标-任务链路断裂 |
| **C3** plans/README.md 状态活数据 | 🔴 Critical | 交叉审计 | P8→P10 | 注册表误导 |
| **C4** 控制面 degrade (freshness 70) | 🔴 Critical | 交叉审计 | P9→P10 | 系统信号不健康 |
| **D2** CI 测试环境 | 🔴 Critical | Phase 1-6 | 5 phases | E2E 无法在 CI 中运行 |
| **D3** eu-pricing 零测试 | 🔴 Critical | Phase 1-6 | 5 phases | 计费模块无验证 |
| **P1** SharedBrain 零测试 | 🔴 High | DEBT-ANALYSIS | 发现于 P2 | 210 万行最大风险 |
| **D4** Cross-repo 治理 | 🟠 Major | Phase 1-6 | 标准有了未执行 | 43 仓库未对齐 |
| **D6** Hermes 断链 | 🟠 Major | Phase 1-6 | 4 phases | 179 条断链 |
| **M1** 产品债务计数不准确 | 🟠 Major | 交叉审计 | — | 债务表自洽性差 |
| **M2** D7 orphaned 无归属 | 🟠 Major | 交叉审计 | — | 规划中的孤儿 |
| **M3** 健康基线假设而非实际 | 🟠 Major | 交叉审计 | — | 需 re-baseline |
| **T1** KOS 5,263 ruff 问题 | 🟠 High | DEBT-ANALYSIS | — | 代码质量红线 |
| **T4** 硬编码路径 | 🟡 Medium | DEBT-ANALYSIS | — | `/Users/` 硬编码 |
| **P2** Forge 1,762 LOC 零测试 | 🟠 Medium | DEBT-ANALYSIS | — | 用途不明 |
| **P3** KOS 零消费者 | 🟠 Medium | ARCH-AUDIT | — | API 未经验证 (0 import) |
| **P5** 交互式 eidos define 缺失 | 🟡 Medium | DEBT-ANALYSIS | — | 需手写 JSON |

> **债务全景**: 总计 ~26 项债务 (来自 Phase 9 Debt Cleanup 的 4 类别 25 项 + 交叉审计 4 Critical)。DEBT-ANALYSIS 四维评分: 产品 **B** / 架构 **B+** / 功能 **B** / 技术 **C** → 综合 **B-**

### 5. 建设规划建议

建议分 Wave 推进，对齐 Phase 10 债务治理节奏：

```
Wave 1 — SSOT 修复 + 现状摸底 (1-2 天)
├── C1-C4 系统状态全面修复
│   ├── system.yaml 同步为 Phase 10 W2 实际状态 ✅ (已完成)
│   ├── goals/current.yaml 增加 Phase 9/10 目标条目
│   ├── plans/README.md Phase 8→completed + 加 Phase 10 条目
│   └── 控制面 freshness 修复 (refresh state summary)
├── 核实 kairon 17 包的实际状态 (哪些已实现、哪些存 stub)
├── 核实 SharedBrain 14 器官能力清单 (结合 AUDIT.md 健康评估)
├── 梳理 agentmesh 7 包接口文档
├── 核实 gbrain 19 引擎模块的完整入口
├── Agora→OntoDerive 解耦评估 (12+ hard imports, 改可选 adapter)
├── 输出: `system-capability-inventory.md`
└── 输出: `SB-ORGAN-INVENTORY.md`

Wave 2 — 核心债务先行 (2-3 周)
├── D3  eu-pricing 独立测试 ← 跨越 5 阶段必须做
├── D2  CI 测试环境 ← 容器化 Agora + SharedBrain
├── D4  Cross-repo 治理对齐 (10 repos min)
├── P1  SharedBrain 零测试决策 (保留/迁移/归档)
├── P5  交互式 eidos define (CLI 体验改进)
├── T4  硬编码路径清理 (5 文件: pipeline/ingest/gateway/mcp_server/tests)
├── 模型统一度补全: OntoDerive Inference/Scheme 接 MetaType
├── === Phase 10 Wave 2 对齐点 ===
└── 数据流 format_version 检查 (所有 MCP 工具)

Wave 3 — 深化与加固 (2-3 周)
├── P2  Forge 确认去留 (1,762 LOC, 零测试, 52 uncommitted)
├── P3  KOS 消费者验证 (至少 1 个真实 import 消费方)
├── T1  KOS ruff 5,263 → ≤500 (设子目标: 先清至 1,500)
├── Agora→OntoDerive 正式解耦实施
├── Minerva Relation 接 MetaRelationType
├── KOS 存储格式标定 MetaType
├── === Phase 10 Wave 3 对齐点 ===
└── Hermes 断链清理 (179 条, 持续 P8 W2 方向)

Wave 4 — 长期演进规划
├── v0.2→v0.5 路线图对接 (生产就绪→接口契约→可观测→多存储)
├── kairon L4 元层能力展开 (family-os/kos-health/device-orchestrator)
├── gbrain 引擎模块扩展路线图
├── SharedBrain 决策后行动 (保留则加冒烟测试/迁移或归档路径)
├── 跨项目 API 契约 SSOT (替换 try/except → Protocol/ABC)
├── 综合健康目标: 当前 90 → W1 90 → W2 92 → W3 94 → W4 95
└── 输出: `capability-roadmap-phase11.md`
```

---

## 第二部分：用户使用层（spaces/data/runtime）

### 1. 全景

```
用户使用层 = 3 根域 + 5 系统
│
├── spaces/           用户/租户空间 manifest
│   ├── registry.yaml       空间注册表
│   ├── system-space.yaml   系统空间 manifest
│   ├── system-space-*-*.yaml (7 份策略文档)
│   │   ├── identity-admission       身份锚定
│   │   ├── capability-taxonomy      能力分类
│   │   ├── admission-matrix         准入矩阵
│   │   ├── rollout-policy           灰度策略
│   │   ├── cross-root-rule-registry 跨根规则
│   │   └── ... 更多
│   └── _schema/          空间 manifest schema
│
├── data/             共享数据基板
│   ├── system-data-access-policy.yaml  访问策略
│   ├── db/organs/execution/execution.db 器官执行状态
│   ├── db/organs/memory/memory.db       器官内存状态
│   └── backups/        2 个时间点备份
│
├── runtime/          临时运行时残留
│   ├── system-runtime-boundary.yaml   边界契约
│   ├── run-continuation/ses_*.json    会话心跳
│   └── (日志/临时态/pid-socket/缓存)
│
├── 用户身份
│   ├── 11 角色定义 (projects/SharedBrain/config/roles/)
│   ├── 双层 EU 经济 (eu_pricing -> EUBridge -> Agora accounting)
│   └── spaces 四层身份映射 (actor→membership→role→capability_binding)
│
├── 用户体验
│   ├── 5 已验证用户旅程 (test-integration/test_user_journeys.py)
│   ├── 60 场景分析 (drafts/scenario-analysis.md, 7 个已做断点分析)
│   ├── 研究引擎三级降级 (minerva→ollama→缓存)
│   ├── 4 故障注入测试 (test-fault-injection.py)
│   └── P7-W1-USER-JOURNEY-ENABLEMENT (已完成)
│
└── 数据生命周期
    ├── 数据散落 4 处: ~/.workspace/、~/.agora/、~/.kos/、data/db/
    ├── 无统一数据目录
    ├── 无数据 TTL/GC 策略
    └── backups 无自动调度
```

### 2. 已有规划基础（.omo 中已有文档）

| 领域 | 已有文档 |
|------|---------|
| **空间管理** | `spaces/registry.yaml`, 5 份策略文档, `_schema/` schema 定义 |
| **身份/权限** | `system-space-identity-admission.yaml`, `capability-taxonomy`, `admission-matrix` |
| **跨根规则** | `system-space-cross-root-rule-registry.yaml` (Phase 10 W1) |
| **数据访问** | `data/system-data-access-policy.yaml` |
| **运行时边界** | `runtime/system-runtime-boundary.yaml` |
| **用户旅程** | `drafts/scenario-analysis.md`, `tests/integration/test-user-journeys.py` |
| **故障容错** | `tests/integration/test-fault-injection.py` |
| **用户旅程使能** | `P7-W1-USER-JOURNEY-ENABLEMENT` (已完成, Phase 7 W1) |
| **EU 经济** | `eu-pricing` L2 包, `sharedbrain-bridge/eu.py`, `agora/accounting.py` |
| **角色定义** | `projects/SharedBrain/config/roles/` (11 个角色) |
| **控制面健康** | `_delivery/task-center/control/current.yaml` (degrade, freshness 70) |
| **用户用量** | `_truth/task-center/usage-accounting.yaml` (90 completed/2 blocked/9 dispatches) |

### 3. 关键指标

| 指标 | 数值 |
|------|------|
| 策略文件数 | ~10 份 (identity/admission/rollout/cross-root/data-access) |
| 用户旅程 | 5 已验证 / 60 已分析 |
| 场景可行度 | 20/60 ✅ / 28/60 ⚠️ / 12/60 ❌ |
| 数据存储位置 | 4+ 处 (无统一管理) |
| 用户身份 | string caller_id (无真正身份验证) |
| 审计追踪 | 无 |
| 会话恢复 | 心跳级 (无状态恢复) |
| 故障注入 | 4 场景已定义 |
| 数据备份 | 2 个时间点 (手动) |

### 4. 建设规划建议

```
Wave 1 — 用户使用层摸底 (1-2 天)
├── 核实 11 角色定义与 EU 模型的当前运行状态
├── 梳理数据散落点的完整清单
├── 验证 5 条用户旅程的当前可行度
├── 检查 P7-W1-USER-JOURNEY-ENABLEMENT 遗留的 gap
├── 输出: `user-layer-inventory.md`
└── 输出: `data-scatter-map.md`

Wave 2 — 基础体验补全 (2-3 周)
├── A1 深度研究 — workspace dashboard 一键 Web UI
├── B2 知识搜索 — SQLite FTS5 全文搜索
├── D1 系统健康 — HTTP health check (不只测 CLI 存在)
├── C7 结果通知 — macOS 系统通知
├── 数据统一管理 — 数据目录集中索引
├── === Phase 10 Wave 2 对齐点 ===
└── A2 后续追问 — minerva 真实重新研究

Wave 3 — 身份与治理增强 (2-3 周)
├── 真正用户身份验证 (从 caller_id 升级)
├── 用户操作审计追踪
├── 会话状态持久化 (不仅是心跳)
├── 12 个 ❌ 不可行场景的可行性评估与决策
└── === Phase 10 Wave 3 对齐点 ===

Wave 4 — 长期演进 (持续)
├── 多用户/协作场景
├── 数据 TTL/GC 自动策略
├── 自动备份调度
├── Web UI 统一入口 (不依赖 CLI)
├── Top 20 场景补全到 ✅ 可行
└── 输出: `user-experience-roadmap-phase11.md`
```

---

## 第三部分：跨层协同规划

### 3.1 关键依赖关系

```
系统能力层 (projects)          用户使用层 (runtime/data/spaces)
────────────────────          ────────────────────────────────
D2 CI 环境                    ← 用户旅程 E2/E3 的自动化基础设施
D3 eu-pricing 测试            ← 用户 D10 用量统计的基础
P1 SharedBrain 决策           ← 用户 D1/D5/D7/D8 的系统管理
P5 eidos define CLI 改进      ← 用户 B2/B4/B10 的知识管理
T4 硬编码路径清理              ← 用户 D6 配置变更
                               ← 用户 A1/A2 研究体验依赖 L2 能力
                               ← 用户 D4 日志查看依赖运行时
```

### 3.2 对齐 Phase 10 节奏

| 层 | W1 (摸底) | W2 (补基础) | W3 (加固) | W4 (演进) |
|---|:--------:|:----------:|:---------:|:---------:|
| Phase 10 | 状态修复+Quick Win | 核心债务清理 | 遗留风险处理 | 结项 |
| 系统能力层 | ✅ 摸底 | ⚡ D2/D3/P1/P5 | ⚡ P2/P3/T4/T1 | 📋 路线图 |
| 用户使用层 | ✅ 摸底 | ⚡ A1/B2/D1/C7 | ⚡ 身份/审计/会话 | 📋 路线图 |

### 3.3 立即能启动的事项

1. **核实阶段**: kairon 包实际状态 / SB 器官清单 / 用户角色 - **本计划完成后即可启动**
2. **快速修复**: workspace dashboard / HTTP health check / 数据目录索引
3. **必须决策**: SharedBrain 去留 (决定后续大量 work 的方向)

---

## 第四部分：下一步行动

### 本阶段目标
- [x] 系统能力层全景梳理 (已完成, 见第一部分)
- [x] 用户使用层全景梳理 (已完成, 见第二部分)
- [ ] 分 Wave 的任务分解 (待输出到 tasks/)
- [ ] 输出 layer-inventory 文档 (待执行)

### 建议立即开始的 task

| 优先级 | Task | 层 | 预计工时 |
|:------:|------|:--:|:--------:|
| P0 | 核实 kairon 18 包实际状态 (哪些是活的/哪些是 stub) | 能力层 | 2h |
| P0 | 核实 SharedBrain 14 器官能力清单 + 当前运行状态 | 能力层 | 2h |
| P0 | 梳理用户数据散落点完整清单 | 用户层 | 1h |
| P0 | 验证 5 条用户旅程当前实际可行度 | 用户层 | 2h |
| P1 | workspace dashboard 一键启动 Web UI | 用户层 | 4h |
| P1 | workspace status HTTP health check | 用户层 | 2h |
| P1 | D3 eu-pricing 独立测试 | 能力层 | 8h |
| P1 | P1 SharedBrain 零测试决策 | 能力层 | 2h |
| P2 | data-scatter-map.md 输出 | 用户层 | 1h |
| P2 | 12 个 ❌ 场景可行性再评估 | 用户层 | 2h |

---

*参考指针:*
- `.omo/MASTER-BLUEPRINT.md` — 全景蓝图
- `.omo/PROJECTS.yaml` — 项目注册表
- `.omo/plans/archive/phase10-planning-analysis.md` — Phase 10 债务分析
- `.omo/plans/archive/phase10-program-plan.md` — Phase 10 总体计划
- `.omo/drafts/scenario-analysis.md` — 60 场景分析
- `.omo/PRODUCT-ARCH-JOURNEY.md` — 产品架构与旅程
- `spaces/` — 空间 registry 与策略
- `data/`, `runtime/` — 数据/运行时根目录
- `projects/SharedBrain/config/roles/` — 11 角色定义
- `.omo/ARCH-AUDIT-2026-05.md` — 12 项目架构审计
- `.omo/ARCH-AUDIT-v2.md` — 19 项目模型统一度/依赖审计
- `.omo/DEBT-ANALYSIS.md` — 四维债务分析 (产品/架构/功能/技术)
- `.omo/HEALTH_DASHBOARD.md` — 9 维系统健康度历史看板
- `.omo/INSIGHTS-AND-ROADMAP.md` — 6 深度洞察 + v0.2→v0.5 路线图
- `.omo/INVENTORY.md` — 项目资产清单 (项目级 LOC/文件数)
- `.omo/AUDIT.md` — 16 项目综合审计
- `.omo/GOVERNANCE_PLAN.md` — 治理计划总纲 (历史战略快照)
- `.omo/_knowledge/design/phase5-program-architecture.md` — Phase 5 总纲 (四平面/着陆模型)
- `.omo/_knowledge/management/phase1-6-comprehensive-review.md` — P1-6 全面回顾
- `.omo/_knowledge/management/phase9-debt-cleanup-plan.md` — Phase 9 债务清理规划 (25 项)
- `.omo/_knowledge/management/phase10-cross-audit.md` — Phase 10 交叉审计 (4C/6M/5m)
- `.omo/summaries/data-flow.md` — 数据流向规范 (Kronos→OntoDerive→Minerva)
- `.omo/summaries/p3-capability-track-retrospective.md` — Phase 3 能力轨迹回顾
- `.omo/summaries/worker-utilization-baseline.md` — Worker 利用率基线
- `.omo/state/provider-plane.yaml` — Provider 平面状态
- `.omo/_delivery/task-center/control/current.yaml` — 控制面当前状态 (degrade)
- `.omo/_delivery/task-center/freshness/current.yaml` — 新鲜度报告 (70)
- `.omo/_truth/task-center/usage-accounting.yaml` — 用量核算
- `.omo/KNOWLEDGE_ARCH.md` — 知识基座三层架构 (Eidos/KOS/OntoDerive)
- `.omo/KOS_MIGRATION_IMPACT.md` — KOS 迁移影响分析 (运行时 6 处必须改)
- `.omo/MODEL-BENCHMARK.md` — Eidos 核心 Schema 字段定义
- `.omo/P1_PROJECT_HEALTH.md` — Sophia/Pallas/BOS-Skill-CLI 健康分析
