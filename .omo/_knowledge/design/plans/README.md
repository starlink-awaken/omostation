# .omo/plans/ 目录索引

> 日期: 2026-06-03 | 版本: v1.9 | 状态: Phase 16 completed / Phase 17 planning gate

---

## 文档状态分类

| 标识 | 含义 | 操作 |
|:----:|------|------|
| 🔴 **EXECUTION** | 正在执行的任务规格书 | Agent 直接使用 |
| 🟣 **GATED** | 执行候选，但只允许前置 gate 任务 | Agent 只能执行 `.omo/tasks/active/*.yaml` |
| 🟡 **ACTIVE** | 持续更新的活文档 | 随进展更新 |
| 🟢 **REFERENCE** | 计划完成，保留参考 | 只读，不修改 |
| ⚪ **ARCHIVED** | 已被新版取代 | 移到 archive/ |
| 🔵 **PRE-PLANNING** | 规划阶段文档，等待前置 Phase 完成 | 只读，不执行 |

---

## 🔴 EXECUTION — 当前任务源

| 文件/目录 | Phase | 状态 | Agent 执行规则 |
|-----------|:----:|------|----------------|
| `.omo/tasks/active/*.yaml` | — | ✅ EMPTY | Phase 16 completed; no active packet currently queued |

### 生成 active task 前必须对齐的标准

- `.omo/standards/planning-blueprint-delivery-test-standard.md`
- `.omo/standards/phase2-full-execution-go-no-go.md`
- `.omo/standards/ARCHITECTURE_CONVERGENCE.md`

要求：

1. phase spec 进入 execution 前，必须能映射成 `.omo/tasks/active/*.yaml`。
2. active task 必须带上 entry gate / evidence / test plan。
3. 任何执行推进都必须服从当前 `goals/current.yaml` 与 go/no-go 约束。

---

## 🟣 GATED — 阶段规格书（执行候选）

| 文件 | Phase | 任务数 | 当前口径 |
|------|:----:|:-----:|----------|
| `phase2-task-specs-v2.md` | 2 | 47 | M2.FULL-GO 7/7 已通过；可初始化 M2.3 首批任务到 active/ |
| `phase3-task-specs-v2.md` | 3 | 35 | Phase 2 full execution 验收前不可执行 |
| `phase4-task-specs-v2.md` | 4 | 15 | Phase 3 + 验证期通过前不可执行 |
| `llm-convergence-requirements.md` | 2→3 | draft | LLM 路由统一收敛需求源，不直接下发到 active/ |
| `llm-convergence-planning-packet.md` | 2→3 | gated | dual_track 规划包：P2 尾波前置 + P3 主收敛包 |
| `phase2-phase3-task-manifest.md` | 2→3 | active planning | 当前可调度 P2 尾波 + future-gated P3 任务清单 |
| `phase5-program-plan.md` | 5 | completed | Phase 5 program 总计划：Wave 0-3、goal sequencing、go/no-go |
| `phase5-entry-gate-checklist.md` | 5 | completed | Phase 5 Entry Gate 控制清单（历史 gate packet） |
| `phase5-wave0-execution-plan.md` | 5 | completed | G5.0 / Wave 0 执行计划 |
| `phase5-wave0-task-specs.md` | 5 | completed | G5.0 / Wave 0 任务规格书，可映射到 active/ |
| `phase5-wave1-execution-plan.md` | 5 | completed | G5.1 durable runtime + governance core packet |
| `phase5-wave2-execution-plan.md` | 5 | completed | G5.2 auto-discovery + templates packet |
| `phase5-wave3-execution-plan.md` | 5 | completed | G5.3 skill federation packet |
| `phase6-entry-hardening-packet-implementation-plan.md` | 6 | gated | Phase 6 pre-gate hardening packet implementation plan |
| `phase6-program-plan.md` | 6 | completed | Phase 6 master program plan：G6.1-G6.3 sequencing + one-packet-at-a-time rule |
| `phase6-wave1-execution-plan.md` | 6 | completed | G6.1 durable + governance runtime core execution packet |
| `phase6-wave1-task-specs.md` | 6 | completed | G6.1 task packet spec；只允许 `P6-G1-DURABLE-GOVERNANCE-CORE` 进入 active |
| `phase6-wave2-execution-plan.md` | 6 | completed | G6.2 discovery + templates execution packet |
| `phase6-wave3-execution-plan.md` | 6 | completed | G6.3 skill federation execution packet |
| `phase7-planning-gate.md` | 7 | completed | Phase 7 planning gate packet |
| `phase7-program-plan.md` | 7 | completed | Phase 7 master program plan |
| `phase7-starter-packet-spec.md` | 7 | completed | Phase 7 Wave 1 starter packet spec |
| `phase7-wave1-execution-plan.md` | 7 | completed | Phase 7 Wave 1 execution packet |
| `phase7-wave2-execution-plan.md` | 7 | completed | Phase 7 Wave 2 execution packet |
| `phase7-wave3-execution-plan.md` | 7 | completed | Phase 7 Wave 3 execution packet |
| `phase8-planning-gate.md` | 8 | completed | Phase 8 planning gate packet |
| `phase8-program-plan.md` | 8 | completed | Phase 8 master program plan |
| `phase8-starter-packet-spec.md` | 8 | completed | Phase 8 Wave 1 starter packet spec |
| `phase8-wave2-execution-plan.md` | 8 | completed | Phase 8 Wave 2 execution packet |
| `phase8-wave3-execution-plan.md` | 8 | completed | Phase 8 Wave 3 execution packet |
| `phase9-workspace-plane-refactor-plan.md` | 9 | completed | Phase 9 workspace plane refactor + first migration slice |
| `phase9-program-plan.md` | 9 | completed | Phase 9 master program plan |
| `phase9-wave2-execution-plan.md` | 9 | completed | Phase 9 Wave 2 execution packet |
| `phase9-wave3-execution-plan.md` | 9 | completed | Phase 9 Wave 3 execution packet |
| `phase9-wave4-execution-plan.md` | 9 | completed | Phase 9 Wave 4 execution packet |
| `phase10-program-plan.md` | 10 | completed | Phase 10 master program plan |
| `phase10-wave1-execution-plan.md` | 10 | completed | Phase 10 Wave 1 execution packet |
| `phase10-wave2-execution-plan.md` | 10 | completed | Phase 10 Wave 2 execution packet |
| `phase10-wave3-execution-plan.md` | 10 | completed | Phase 10 Wave 3 execution packet |
| `phase10-wave4-execution-plan.md` | 10 | completed | Phase 10 Wave 4 execution packet |
| `phase10-planning-analysis.md` | 10 | reference | Phase 10 债务治理需求分析：25 项/3 Wave/红队 R1-R4（W1 S1-S3 同步到 README） |
| `phase11-program-plan.md` | 11 | completed | Phase 11 master program plan: 4 waves (SSOT/Core Debt/User MVP/Evolution) |
| `phase11-wave1-execution-plan.md` | 11 | completed | Phase 11 Wave 1 execution packet: SSOT repair + baseline inventory |
| `phase11-wave2-execution-plan.md` | 11 | completed | Phase 11 Wave 2 execution packet: core debt assault |
| `phase11-wave3-execution-plan.md` | 11 | completed | Phase 11 Wave 3 execution packet: user layer MVP |
| `phase11-wave4-execution-plan.md` | 11 | completed | Phase 11 Wave 4 execution packet: evolution bridge |
| `phase12-planning-gate.md` | 12 | completed | Phase 12 entry gate passed for capability ecosystem foundation |
| `phase12-program-plan.md` | 12 | completed | Phase 12 canonical program: registry + scenario MVP + one fusion pilot + audit |
| `phase12-wave1-execution-plan.md` | 12 | completed | Wave 1: capability metamodel + core scan baseline |
| `phase12-wave2-execution-plan.md` | 12 | completed | Wave 2: registry toolchain + scenario MVP + pilot ADR |
| `phase12-wave3-execution-plan.md` | 12 | completed | Wave 3: single fusion pilot + package dry-run |
| `phase12-wave4-execution-plan.md` | 12 | completed | Wave 4: audit + redteam + Phase 13/14 handoff |
| `phase12-wave5-execution-plan.md` | 12 | merged | Historical shell; merged into Wave 4 |
| `phase13-metacognition-preplanning.md` | 13 | completed | Phase 13 read-only metacognition + supervised autonomy boundary |
| `phase14-deferred-ecosystem-backlog.md` | 14 | completed | Deferred ecosystem expansion completed as bounded preview/adapters |
| `phase14-program-plan.md` | 14 | completed | Phase 14 formal program: triage, pilots, patterns, ecosystem preview |

### Phase 1-14 历史计划归档

> 62 个已完成/历史计划文档已移至 [`archive/`](archive/)。
> 包括：phase1-14 的全部 program plans、execution plans、task specs、planning gates、closure documents。
| `phase15-autonomous-governance-preplanning.md` | 15 | completed | Phase 15 supervised autonomous governance loop |
| `phase16-product-surface-convergence-preplanning.md` | 16 | completed | Phase 16 product-surface convergence: knowledge-capture-search scenario shell |
| `phase17-wave1-sharedbrain-decomposition-plan.md` | 17 | pre_planning | Phase 17 Wave 1: SharedBrain decomposition execution plan |
| `layer-capability-user-planning.md` | cross-phase | active | 系统能力层 + 用户使用层 v2 规划（Phase 11 基础输入文档） |

---

## 🔵 PRE-PLANNING — 前置规划文档

| 文件 | Phase | Wave | 进入条件 |
|------|:-----:|:----:|----------|
| `phase15-autonomous-governance-preplanning.md` | 15 | completed | Phase 14 closeout GO + explicit human approval |
| `phase16-product-surface-convergence-preplanning.md` | 16 | completed | Phase 15 closeout GO + explicit human approval |

---

## 🟡 ACTIVE — 活文档（持续更新）

| 文件 | 版本 | 描述 |
|------|:---:|------|
| `../_knowledge/design/MASTER-BLUEPRINT.md` | v1.1 | 全景主蓝图 + Post-Phase1 门禁 |
| `evolution-roadmap-4phases.md` | v1.1 | 4 阶段路线图（红队修订） |
| `post-phase1-governance-and-phase2-entry.md` | v1.0 | Phase 1 关闭 + Phase 2 入场规范 |
| `planning-blueprint-delivery-test-standard.md` | v1.0 | 规划/交付/测试统一标准 |
| `llm-convergence-requirements.md` | v1.0 | LiteLLM / LLM 路由统一收敛需求（future planning input） |
| `llm-convergence-planning-packet.md` | v1.0 | 将 requirements 拆成 dual_track workstreams 的规划包 |
| `phase2-phase3-task-manifest.md` | v1.0 | P2 尾波执行项 + P3 future-gated 任务清单 |
| `phase5-program-plan.md` | v1.0 | Phase 5 总计划（已完成的 master program + Wave 0-3 sequencing） |
| `phase5-entry-gate-checklist.md` | v1.0 | Phase 5 进入执行前的控制清单（历史 gate packet） |
| `phase5-wave0-execution-plan.md` | v1.0 | Phase 5 Wave 0 执行计划 |
| `phase5-wave0-task-specs.md` | v1.0 | Phase 5 Wave 0 任务规格书 |
| `phase5-wave1-execution-plan.md` | v1.0 | Phase 5 Wave 1 执行包 |
| `phase5-wave2-execution-plan.md` | v1.0 | Phase 5 Wave 2 执行包 |
| `phase5-wave3-execution-plan.md` | v1.0 | Phase 5 Wave 3 执行包 |
| `phase6-entry-hardening-packet-implementation-plan.md` | v1.0 | Phase 6 入口硬化包实现计划（先 hardening，再 runtime） |
| `phase6-program-plan.md` | v1.0 | Phase 6 主程序计划（ratified after P6-G0 GO） |
| `phase6-wave1-execution-plan.md` | v1.0 | Phase 6 Wave 1 执行包 |
| `phase6-wave1-task-specs.md` | v1.0 | Phase 6 Wave 1 任务规格书 |
| `phase6-wave2-execution-plan.md` | v1.0 | Phase 6 Wave 2 执行包 |
| `phase6-wave3-execution-plan.md` | v1.0 | Phase 6 Wave 3 执行包 |
| `phase7-planning-gate.md` | v1.0 | Phase 7 planning gate 包 |
| `phase7-program-plan.md` | v1.0 | Phase 7 主程序计划 |
| `phase7-starter-packet-spec.md` | v1.0 | Phase 7 Wave 1 starter packet 规格 |
| `phase7-wave1-execution-plan.md` | v1.0 | Phase 7 Wave 1 执行计划 |
| `phase7-wave2-execution-plan.md` | v1.0 | Phase 7 Wave 2 执行计划 |
| `phase7-wave3-execution-plan.md` | v1.0 | Phase 7 Wave 3 执行计划 |
| `phase8-planning-gate.md` | v1.0 | Phase 8 planning gate 包 |
| `phase8-program-plan.md` | v1.0 | Phase 8 主程序计划 |
| `phase8-starter-packet-spec.md` | v1.0 | Phase 8 Wave 1 starter packet 规格 |
| `phase8-wave2-execution-plan.md` | v1.0 | Phase 8 Wave 2 执行计划 |
| `phase8-wave3-execution-plan.md` | v1.0 | Phase 8 Wave 3 执行计划 |
| `phase9-workspace-plane-refactor-plan.md` | v1.0 | Phase 9 工作区分面重构与首批迁移计划 |
| `phase9-program-plan.md` | v1.0 | Phase 9 主程序计划（Wave 2-4 sequencing） |
| `phase9-wave2-execution-plan.md` | v1.0 | Phase 9 Wave 2 执行计划（已收口，作为 Wave 2 reference） |
| `phase9-wave3-execution-plan.md` | v1.0 | Phase 9 Wave 3 执行计划（identity / authorization / admission） |
| `phase10-planning-analysis.md` | v1.0 | Phase 10 债务治理需求分析：25 项/3 Wave/红队 R1-R4（债务治理方案） |
| `phase11-program-plan.md` | v1.0 | Phase 11 主程序计划（已完成） |
| `phase11-wave1-execution-plan.md` | v1.0 | Phase 11 Wave 1 执行计划（已完成 baseline packet） |
| `phase11-wave2-execution-plan.md` | v1.0 | Phase 11 Wave 2 执行计划（已完成 core-debt packet） |
| `phase11-wave3-execution-plan.md` | v1.0 | Phase 11 Wave 3 执行计划（已完成 user-layer MVP） |
| `phase11-wave4-execution-plan.md` | v1.0 | Phase 11 Wave 4 执行计划（已完成） |
| `phase12-planning-gate.md` | v1.0 | Phase 12 entry gate 已通过 |
| `phase12-program-plan.md` | v1.0 | Phase 12 canonical program 已完成，范围收敛为 registry/scenario/pilot/audit |
| `phase12-wave1-execution-plan.md` | v1.0 | Phase 12 Wave 1：能力元模型 + 核心扫描基线，已完成 |
| `phase12-wave2-execution-plan.md` | v1.0 | Phase 12 Wave 2：注册表工具链 + 场景 MVP + pilot ADR，已完成 |
| `phase12-wave3-execution-plan.md` | v1.0 | Phase 12 Wave 3：单一融合 pilot + package dry-run，已完成 |
| `phase12-wave4-execution-plan.md` | v1.0 | Phase 12 Wave 4：审计 + 红队 + P13/P14 交接，已完成 |
| `phase12-wave5-execution-plan.md` | v0.2 | 已合并到 Wave 4，不作为执行 packet |
| `phase13-metacognition-preplanning.md` | v1.0 | Phase 13 supervised metacognition 已完成，取代 archive/phase13-metacognition.md 作为历史规划入口 |
| `phase14-deferred-ecosystem-backlog.md` | v1.0 | Phase 14 backlog 已完成为 bounded preview/adapters |
| `phase14-program-plan.md` | v1.0 | Phase 14 program plan 已完成：triage / pilot contracts / patterns / ecosystem preview |
| `../_knowledge/design/system-design-baseline.md` | v1.0 | Post-Phase-14 canonical baseline：统一 `4P3V1L` 框架、路线图边界与 Phase 15/16 锚点 |
| `phase15-autonomous-governance-preplanning.md` | v0.2 | Phase 15 pre-planning，承接 `4P3V1L` 基线，固化治理证据账本、策略测试、提案编译与恢复演练 |
| `phase16-product-surface-convergence-preplanning.md` | v0.1 | Phase 16 pre-planning，在 Phase 15 护栏之后收敛 `P0` 产品入口层、用户旅程与统一场景壳 |

---

## 🟢 REFERENCE — 参考文档（计划完成，只读）

| 文件 | 版本 | 描述 | 成果已融入 |
|------|:---:|------|-----------|
| `phase1-task-specs.md` | v1.0 | Phase 1 任务规格 | Phase 1 归档 |
| `phase1-verification-report.md` | v1.0 | Phase 1 代码验收 | Phase 1 history |
| `architecture-final-vision.md` | v1.0 | 终极架构蓝图 | MASTER-BLUEPRINT |
| `sharedbrain-kairon-integration.md` | v2.0 | SharedBrain 融合方案 | Phase 1 已完成 |
| `comprehensive-architecture-audit.md` | v1.0 | SSOT 7 域拆解 + 缺口分析 | Phase 2-3 任务 |
| `tech-intelligence-2026q2.md` | v1.0 | 行业技术情报 (50+ repos) | Phase 2-3 T1-T5 |
| `deep-architecture-agent-analysis.md` | v1.1 | Agent 协作 + 第一性原理 | Phase 2 ACP_* |
| `agent-architecture-audit-redteam.md` | v1.0 | Agent 体系审计 + 红队 | Phase 2 SAFE_* |
| `redteam-revision-patch.md` | v1.0 | 全 Phase 红队修订补丁 | 已应用到 v1.1 |
| `beyond-phase4-vision.md` | v1.1 | Phase ∞ 远景（红队修订） | — |
| `beyond-phase4-review.md` | v1.0 | Phase ∞ 红队·战略·安全审查 | — |

---

## ⚪ ARCHIVED — 已被新版取代

| 文件 | 取代者 |
|------|--------|
| `phase2-task-specs.md` (v1.0, 29任务) | `phase2-task-specs-v2.md` (v2.0, 47任务) |
| `phase3-task-specs.md` (v1.0, 25任务) | `phase3-task-specs-v2.md` (v2.0, 35任务) |
| `phase4-task-specs.md` (v1.0, 10任务) | `phase4-task-specs-v2.md` (v2.0, 15任务) |

---

## .omo/ 根目录文档

| 文件 | 状态 | 描述 |
|------|:---:|------|
| `../_knowledge/design/MASTER-BLUEPRINT.md` | 🟡 ACTIVE | 全景主蓝图（架构·路线图·里程碑） |
| `_archive/CONSISTENCY-CHECK.md` | 🟡 ACTIVE | 一致性检查报告 |
| `goals/current.yaml` | 🔴 EXECUTION | 当前 Phase 目标源 |
| `state/system.yaml` | 🟡 ACTIVE | 聚合状态快照 |
| `tasks/active/*.yaml` | 🔴 EXECUTION | Agent 可认领任务源 |

---

## 命名规范

```
[status]-[phase]-[name]-[version].md

示例:
  phase2-task-specs-v2.md    ← EXECUTION, Phase 2, 任务规格, v2
  evolution-roadmap-4phases.md ← ACTIVE, 路线图
  beyond-phase4-vision.md      ← REFERENCE, 远景

规则:
  - 任务规格书: phase{N}-task-specs{-v{N}}.md
  - 蓝图/路线图: {name}.md
  - 审计/分析: {name}-{audit|analysis|review|redteam}.md
  - 可执行任务: .omo/tasks/active/{milestone}-{slug}.yaml
  - 旧版: 移到 archive/ 或标记 ARCHIVED
```
