# .omo/plans/ 目录索引

> 本页是计划文档注册表，不是运行时状态快照。
> 当前阶段、执行许可、active task 与 gate 结论一律以 `/.omo/goals/current.yaml`、`/.omo/state/system.yaml`、`/.omo/tasks/active/` 为准。

---

## 文档状态分类

| 标识 | 含义 | 操作 |
|:----:|------|------|
| 🔴 **EXECUTION** | 正在执行的任务规格书 | Agent 直接使用 |
| 🟣 **GATED** | 仍可作为执行候选的计划/规格，但不能直接越过 active task 机制 | Agent 只能执行 `.omo/tasks/active/*.yaml` |
| 🟡 **ACTIVE** | 仍作为当前规划输入维护的文档 | 随进展更新 |
| 🟢 **REFERENCE** | 历史完成计划、已收口执行包、只读基线与参考 | 只读，不修改 |
| ⚪ **ARCHIVED** | 已被新版取代 | 移到 archive/ |
| 🔵 **PRE-PLANNING** | 规划阶段文档，等待前置 Phase 完成 | 只读，不执行 |

---

## 🔴 EXECUTION — 当前任务源

| 文件/目录 | Phase | 状态 | Agent 执行规则 |
|-----------|:----:|------|----------------|
| `.omo/tasks/active/*.yaml` | — | 由运行时决定 | 当前可执行任务源；是否为空以目录现状与 `goals/current.yaml` 为准 |

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
| `phase6-entry-hardening-packet-implementation-plan.md` | 6 | gated | Phase 6 pre-gate hardening packet implementation plan |

---

## 🔵 PRE-PLANNING — 前置规划文档

| 文件 | Phase | Wave | 进入条件 |
|------|:-----:|:----:|----------|
| `phase17-wave1-sharedbrain-decomposition-plan.md` | 17 | 1 | SharedBrain 相关 scope 重新进入当前目标前，需显式 human approval + 当前 goals 对齐 |

> 说明: `completed / gated / active / reference / archived` 仅表示计划文档在注册表中的编目状态，
> 不等于当前系统运行时 Phase，也不等于任务可直接执行。

---

## 🟡 ACTIVE — 活文档（持续更新）

| 文件 | 版本 | 描述 |
|------|:---:|------|
| `evolution-roadmap-4phases.md` | v1.1 | 4 阶段路线图（红队修订） |
| `planning-blueprint-delivery-test-standard.md` | v1.0 | 规划/交付/测试统一标准 |
| `phase2-phase3-task-manifest.md` | v1.0 | P2 尾波执行项 + P3 future-gated 任务清单 |

---

## 🟢 REFERENCE — 参考文档（计划完成，只读）

| 文件 | 版本 | 描述 | 成果已融入 |
|------|:---:|------|-----------|
| `../_knowledge/design/MASTER-BLUEPRINT.md` | v1.1 | 历史全景主蓝图 + Post-Phase1 门禁输入 | design/INDEX 路由 |
| `post-phase1-governance-and-phase2-entry.md` | v1.0 | Phase 1 关闭 + Phase 2 入场规范（历史 gate snapshot） | 历史收口记录 |
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
| `phase5-program-plan.md` | v1.0 | Phase 5 总计划（历史 master program） | Phase 5 closeout |
| `phase5-entry-gate-checklist.md` | v1.0 | Phase 5 进入执行前的控制清单（历史 gate packet） | Phase 5 closeout |
| `phase5-wave0-execution-plan.md` | v1.0 | Phase 5 Wave 0 执行计划 | Phase 5 closeout |
| `phase5-wave0-task-specs.md` | v1.0 | Phase 5 Wave 0 任务规格书 | Phase 5 closeout |
| `phase5-wave1-execution-plan.md` | v1.0 | Phase 5 Wave 1 执行包 | Phase 5 closeout |
| `phase5-wave2-execution-plan.md` | v1.0 | Phase 5 Wave 2 执行包 | Phase 5 closeout |
| `phase5-wave3-execution-plan.md` | v1.0 | Phase 5 Wave 3 执行包 | Phase 5 closeout |
| `phase6-entry-hardening-packet-implementation-plan.md` | v1.0 | Phase 6 入口硬化包实现计划 | Phase 6 closeout |
| `phase6-program-plan.md` | v1.0 | Phase 6 主程序计划 | Phase 6 closeout |
| `phase6-wave1-execution-plan.md` | v1.0 | Phase 6 Wave 1 执行包 | Phase 6 closeout |
| `phase6-wave1-task-specs.md` | v1.0 | Phase 6 Wave 1 任务规格书 | Phase 6 closeout |
| `phase6-wave2-execution-plan.md` | v1.0 | Phase 6 Wave 2 执行包 | Phase 6 closeout |
| `phase6-wave3-execution-plan.md` | v1.0 | Phase 6 Wave 3 执行包 | Phase 6 closeout |
| `phase7-planning-gate.md` | v1.0 | Phase 7 planning gate 包 | Phase 7 closeout |
| `phase7-program-plan.md` | v1.0 | Phase 7 主程序计划 | Phase 7 closeout |
| `phase7-starter-packet-spec.md` | v1.0 | Phase 7 Wave 1 starter packet 规格 | Phase 7 closeout |
| `phase7-wave1-execution-plan.md` | v1.0 | Phase 7 Wave 1 执行计划 | Phase 7 closeout |
| `phase7-wave2-execution-plan.md` | v1.0 | Phase 7 Wave 2 执行计划 | Phase 7 closeout |
| `phase7-wave3-execution-plan.md` | v1.0 | Phase 7 Wave 3 执行计划 | Phase 7 closeout |
| `phase8-planning-gate.md` | v1.0 | Phase 8 planning gate 包 | Phase 8 closeout |
| `phase8-program-plan.md` | v1.0 | Phase 8 主程序计划 | Phase 8 closeout |
| `phase8-starter-packet-spec.md` | v1.0 | Phase 8 Wave 1 starter packet 规格 | Phase 8 closeout |
| `phase8-wave2-execution-plan.md` | v1.0 | Phase 8 Wave 2 执行计划 | Phase 8 closeout |
| `phase8-wave3-execution-plan.md` | v1.0 | Phase 8 Wave 3 执行计划 | Phase 8 closeout |
| `phase9-workspace-plane-refactor-plan.md` | v1.0 | Phase 9 工作区分面重构与首批迁移计划 | Phase 9 closeout |
| `phase9-program-plan.md` | v1.0 | Phase 9 主程序计划 | Phase 9 closeout |
| `phase9-wave2-execution-plan.md` | v1.0 | Phase 9 Wave 2 执行计划 | Phase 9 closeout |
| `phase9-wave3-execution-plan.md` | v1.0 | Phase 9 Wave 3 执行计划 | Phase 9 closeout |
| `phase9-wave4-execution-plan.md` | v1.0 | Phase 9 Wave 4 执行计划 | Phase 9 closeout |
| `phase10-program-plan.md` | v1.0 | Phase 10 master program plan | Phase 10 closeout |
| `phase10-wave1-execution-plan.md` | v1.0 | Phase 10 Wave 1 execution packet | Phase 10 closeout |
| `phase10-wave2-execution-plan.md` | v1.0 | Phase 10 Wave 2 execution packet | Phase 10 closeout |
| `phase10-wave3-execution-plan.md` | v1.0 | Phase 10 Wave 3 execution packet | Phase 10 closeout |
| `phase10-wave4-execution-plan.md` | v1.0 | Phase 10 Wave 4 execution packet | Phase 10 closeout |
| `phase10-planning-analysis.md` | v1.0 | Phase 10 债务治理需求分析：25 项/3 Wave/红队 R1-R4 | 历史分析输入 |
| `phase11-program-plan.md` | v1.0 | Phase 11 主程序计划 | Phase 11 closeout |
| `phase11-wave1-execution-plan.md` | v1.0 | Phase 11 Wave 1 执行计划 | Phase 11 closeout |
| `phase11-wave2-execution-plan.md` | v1.0 | Phase 11 Wave 2 执行计划 | Phase 11 closeout |
| `phase11-wave3-execution-plan.md` | v1.0 | Phase 11 Wave 3 执行计划 | Phase 11 closeout |
| `phase11-wave4-execution-plan.md` | v1.0 | Phase 11 Wave 4 执行计划 | Phase 11 closeout |
| `phase12-planning-gate.md` | v1.0 | Phase 12 entry gate 已通过 | Phase 12 closeout |
| `phase12-program-plan.md` | v1.0 | Phase 12 canonical program | Phase 12 closeout |
| `phase12-wave1-execution-plan.md` | v1.0 | Phase 12 Wave 1：能力元模型 + 核心扫描基线 | Phase 12 closeout |
| `phase12-wave2-execution-plan.md` | v1.0 | Phase 12 Wave 2：注册表工具链 + 场景 MVP + pilot ADR | Phase 12 closeout |
| `phase12-wave3-execution-plan.md` | v1.0 | Phase 12 Wave 3：单一融合 pilot + package dry-run | Phase 12 closeout |
| `phase12-wave4-execution-plan.md` | v1.0 | Phase 12 Wave 4：审计 + 红队 + P13/P14 交接 | Phase 12 closeout |
| `phase12-wave5-execution-plan.md` | v0.2 | 已合并到 Wave 4，不作为执行 packet | Phase 12 history |
| `phase13-metacognition-preplanning.md` | v1.0 | Phase 13 supervised metacognition 已完成 | Phase 13 closeout |
| `phase14-deferred-ecosystem-backlog.md` | v1.0 | Phase 14 backlog 已完成为 bounded preview/adapters | Phase 14 closeout |
| `phase14-program-plan.md` | v1.0 | Phase 14 program plan 已完成：triage / pilot contracts / patterns / ecosystem preview | Phase 14 closeout |
| `../_knowledge/design/system-design-baseline.md` | v1.0 | Post-Phase-14 canonical baseline（历史参考基线） | design/INDEX 路由 |
| `phase15-autonomous-governance-preplanning.md` | v0.2 | Phase 15 pre-planning（历史完成规划） | 历史规划输入 |
| `phase16-product-surface-convergence-preplanning.md` | v0.1 | Phase 16 pre-planning（历史完成规划） | 历史规划输入 |

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
| `../_knowledge/design/MASTER-BLUEPRINT.md` | 🟢 REFERENCE | 历史全景主蓝图（架构·路线图·里程碑） |
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
