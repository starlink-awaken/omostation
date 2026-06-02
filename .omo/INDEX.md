# `.omo/` 治理知识库导航

> 工作区治理与知识管理中心索引。
>
> 文档体系遵循 **SSOT 本体建模四平面架构**，详见 [DOC-ARCH.md](DOC-ARCH.md)。

---

## 四平面快速入口

| 平面 | 目录 | 回答的问题 | 核心文件 |
|------|------|-----------|---------|
| [🕹️ 控制面](_control/INDEX.md) | `_control/` | 我现在在哪？状态如何？ | `goals/current.yaml`, `state/system.yaml` |
| [📡 事实面 SSOT](_truth/INDEX.md) | `_truth/` | 什么是真的？唯一源在哪？ | `tasks/`, `standards/`, `PROJECTS.yaml` |
| [📚 知识面 WIKI](_knowledge/INDEX.md) | `_knowledge/` | 我们知道了什么？ | `plans/`, `summaries/`, 审计/复盘文档 |
| [📦 交付面](_delivery/INDEX.md) | `_delivery/` | 我们交付了什么？ | `workers/runs/`, `tests/`, `evidence/` |

---

## 融合原则

- **四平面是逻辑入口层，不是物理迁移层**：`_control/`、`_truth/`、`_knowledge/`、`_delivery/` 负责导航与分层说明，底层权威目录仍是 `goals/`、`state/`、`tasks/`、`standards/`、`workers/`、`tests/`、`summaries/`。
- **允许 plane-native domain，但只能有单一 owner plane**：默认继续使用导航壳；如果像 `task-center/` 这样的新域天然只属于 truth/delivery 某一平面，则允许直接落在该平面下，但其他平面只能保留索引、状态或引用，不能再复制一份 SSOT。
- **现有 `.omo` 机制继续生效**：任务认领、状态同步、worker dispatch、验收报告都仍写入原有 SSOT/证据目录，平面 INDEX 只负责统一阅读路径和跨平面跳转。
- **实时状态只链向 live source，不在 INDEX 中复制计数**：Phase、health、active queue、完成数等易变事实以 `state/system.yaml`、`goals/current.yaml`、`tasks/*/` 为准，索引页只提供阅读入口。
- **新增文档优先按平面归类，再映射到底层位置**：如果内容是事实，写入 SSOT；如果是复盘/指南/参考，则由知识面入口归档引用。

---

## 当前状态快照

- **实时 Phase / health / milestone**: [state/system.yaml](state/system.yaml)
- **实时 goals / current wave**: [goals/current.yaml](goals/current.yaml)
- **实时 active / blocked queue**: [tasks/active/](tasks/active/) · [tasks/blocked/](tasks/blocked/)
- **future backlog / planned queue**: [tasks/planned/](tasks/planned/)
- **当前完成基线**: [phase14-closeout.md](summaries/phase14-closeout.md)
- **当前执行焦点**: Phase 17 governance gate packets are active; future backlog lives under `tasks/planned/`
- **架构基线**: [_knowledge/design/system-design-baseline.md](_knowledge/design/system-design-baseline.md)
- **Phase 15 planning gate**: [phase15-autonomous-governance-preplanning.md](plans/phase15-autonomous-governance-preplanning.md)
- **外部 OMO 方法系统 canonical home**: [_knowledge/reference/OMO-METHODOLOGY-CANON.md](_knowledge/reference/OMO-METHODOLOGY-CANON.md)
- **Phase 16 pre-planning**: [phase16-product-surface-convergence-preplanning.md](plans/phase16-product-surface-convergence-preplanning.md)
- **Phase 9 架构重构计划**: [phase9-workspace-plane-refactor-plan.md](plans/phase9-workspace-plane-refactor-plan.md)
- **Phase 9 program**: [phase9-program-plan.md](plans/phase9-program-plan.md)
- **Phase 9 Wave 2 执行包**: [phase9-wave2-execution-plan.md](plans/phase9-wave2-execution-plan.md)
- **Phase 9 Wave 3 执行包**: [phase9-wave3-execution-plan.md](plans/phase9-wave3-execution-plan.md)
- **Phase 9 Wave 4 执行包**: [phase9-wave4-execution-plan.md](plans/phase9-wave4-execution-plan.md)
- **Phase 10 program**: [phase10-program-plan.md](plans/phase10-program-plan.md)
- **Phase 10 Wave 1 执行包**: [phase10-wave1-execution-plan.md](plans/phase10-wave1-execution-plan.md)
- **Phase 10 Wave 2 执行包**: [phase10-wave2-execution-plan.md](plans/phase10-wave2-execution-plan.md)
- **Phase 10 Wave 3 执行包**: [phase10-wave3-execution-plan.md](plans/phase10-wave3-execution-plan.md)
- **Phase 10 Wave 4 执行包**: [phase10-wave4-execution-plan.md](plans/phase10-wave4-execution-plan.md)
- **Phase 10 Wave 4 收口**: [phase10-wave4-closeout.md](summaries/phase10-wave4-closeout.md)
- **Phase 10 总复盘**: [phase10-closeout-retrospective.md](summaries/phase10-closeout-retrospective.md)
- **Phase 11 program**: [phase11-program-plan.md](plans/phase11-program-plan.md)
- **Phase 11 Wave 1 收口**: [phase11-wave1-closeout.md](summaries/phase11-wave1-closeout.md)
- **Phase 11 Wave 2 执行包**: [phase11-wave2-execution-plan.md](plans/phase11-wave2-execution-plan.md)
- **Phase 11 Wave 2 收口**: [phase11-wave2-closeout.md](summaries/phase11-wave2-closeout.md)
- **Phase 11 Wave 3 执行包**: [phase11-wave3-execution-plan.md](plans/phase11-wave3-execution-plan.md)
- **Phase 11 Wave 3 收口**: [phase11-wave3-closeout.md](summaries/phase11-wave3-closeout.md)
- **Phase 11 Wave 4 执行包**: [phase11-wave4-execution-plan.md](plans/phase11-wave4-execution-plan.md)
- **Phase 11 Wave 4 收口**: [phase11-wave4-closeout.md](summaries/phase11-wave4-closeout.md)
- **Phase 12 completed program**: [phase12-program-plan.md](plans/phase12-program-plan.md)
- **Phase 12 closeout**: [phase12-closeout.md](summaries/phase12-closeout.md)
- **Phase 13 closeout**: [phase13-closeout.md](summaries/phase13-closeout.md)
- **Phase 13 retrospective**: [phase13-retrospective.md](summaries/phase13-retrospective.md)
- **Phase 14 closeout**: [phase14-closeout.md](summaries/phase14-closeout.md)
- **Phase 14 retrospective**: [phase14-retrospective.md](summaries/phase14-retrospective.md)
- **System design baseline**: [_knowledge/design/system-design-baseline.md](_knowledge/design/system-design-baseline.md)
- **Phase 15 autonomous governance pre-planning**: [phase15-autonomous-governance-preplanning.md](plans/phase15-autonomous-governance-preplanning.md)
- **Phase 16 product-surface convergence pre-planning**: [phase16-product-surface-convergence-preplanning.md](plans/phase16-product-surface-convergence-preplanning.md)
- **Phase 9 首批迁移基线**: [phase9-first-migration-baseline.md](summaries/phase9-first-migration-baseline.md)
- **Phase 9 Wave 2 收口**: [phase9-wave2-closeout.md](summaries/phase9-wave2-closeout.md)
- **Phase 9 Wave 3 收口**: [phase9-wave3-closeout.md](summaries/phase9-wave3-closeout.md)
- **Phase 9 Wave 4 收口**: [phase9-wave4-closeout.md](summaries/phase9-wave4-closeout.md)
- **Phase 9 总复盘**: [phase9-closeout-retrospective.md](summaries/phase9-closeout-retrospective.md)
- **多阶段深度复盘**: [phase1-8-deep-retrospective.md](summaries/phase1-8-deep-retrospective.md)
- **文档覆盖**: 四平面 11 个 INDEX 文件已建立

---

## 阅读路径

| 目标 | 入口 |
|------|------|
| **Agent 会话启动必读** | **[`AGENT.md`](AGENT.md)** |
| 核心控制门禁 | [CONSISTENCY-CHECK.md](CONSISTENCY-CHECK.md) |
| 顶层架构蓝图 | [MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md) |
| 计划注册表 | [plans/README.md](plans/README.md) |
| Worker 使用说明 | [workers/README.md](workers/README.md) |
| 任务 Schema 与状态流转 | [tasks/README.md](tasks/README.md) |
| 查看 planned backlog queue | [tasks/planned/](tasks/planned/) |
| Wave 2 task/gate model | [standards/task-gate-model.md](standards/task-gate-model.md) |
| 快速了解整体状态 | [`_control/INDEX.md`](_control/INDEX.md) |
| 查找权威数据 (SSOT) | [`_truth/INDEX.md`](_truth/INDEX.md) |
| 查阅知识文档 | [`_knowledge/INDEX.md`](_knowledge/INDEX.md) |
| 验证交付证据 | [`_delivery/INDEX.md`](_delivery/INDEX.md) |
| 理解文档架构 | [`DOC-ARCH.md`](DOC-ARCH.md) |
| 查看 Phase 4 执行路线图 | [phase4-execution-roadmap.md](plans/phase4-execution-roadmap.md) |
| 查看 Phase 4 Wave 2 固化设计 | [phase4-wave2-hardening-design.md](plans/phase4-wave2-hardening-design.md) |
| 查看 Phase 4 Wave 2 实施计划 | [phase4-wave2-hardening-implementation-plan.md](plans/phase4-wave2-hardening-implementation-plan.md) |
| 查看 Phase 5 入口桥接设计 | [phase5-entry-architecture.md](_knowledge/design/phase5-entry-architecture.md) |
| 查看 Phase 5 总纲设计 | [phase5-program-architecture.md](_knowledge/design/phase5-program-architecture.md) |
| 查看 Phase 5 Program 计划 | [phase5-program-plan.md](plans/phase5-program-plan.md) |
| 查看 Phase 5 Entry Gate 清单 | [phase5-entry-gate-checklist.md](plans/phase5-entry-gate-checklist.md) |
| 查看 Phase 5 Wave 0 执行计划 | [phase5-wave0-execution-plan.md](plans/phase5-wave0-execution-plan.md) |
| 查看 Phase 5 Wave 0 任务规格书 | [phase5-wave0-task-specs.md](plans/phase5-wave0-task-specs.md) |
| 查看 Phase 5 Wave 0 kickoff 复盘 | [phase5-wave0-kickoff-retrospective.md](summaries/phase5-wave0-kickoff-retrospective.md) |
| 查看 Phase 5 Wave 0 收口复盘 | [phase5-wave0-closeout-retrospective.md](summaries/phase5-wave0-closeout-retrospective.md) |
| 查看 Phase 5 Wave 1 执行包 | [phase5-wave1-execution-plan.md](plans/phase5-wave1-execution-plan.md) |
| 查看 Phase 5 Wave 2 执行包 | [phase5-wave2-execution-plan.md](plans/phase5-wave2-execution-plan.md) |
| 查看 Phase 5 Wave 3 执行包 | [phase5-wave3-execution-plan.md](plans/phase5-wave3-execution-plan.md) |
| 查看 Phase 5 总收口复盘 | [phase5-closeout-retrospective.md](summaries/phase5-closeout-retrospective.md) |
| 查看 Phase 4 Wave 2 收口复盘 | [p4-wave2-closure-retrospective.md](summaries/p4-wave2-closure-retrospective.md) |
| 查看当前 active queue | [tasks/active/](tasks/active/) |
| 查看 worker 协作效果评估 | [worker-collaboration-effectiveness-review.md](summaries/worker-collaboration-effectiveness-review.md) |
| 查看 Phase 4 Wave 1 收口总结 | [p4-wave1-worker-ops-baseline.md](summaries/p4-wave1-worker-ops-baseline.md) |
| 查看下一轮机制升级蓝图 | [omo-fusion-optimization-blueprint.md](plans/omo-fusion-optimization-blueprint.md) |
| 查看机制 + Phase 1-3 总复盘 | [omo-mechanism-and-phase1-3-retrospective.md](summaries/omo-mechanism-and-phase1-3-retrospective.md) |
| 查看本轮收敛/腐败审计 | [omo-convergence-audit-2026-05-31.md](_knowledge/management/omo-convergence-audit-2026-05-31.md) |
| 查看 Phase 6 前置治理决策包 | [phase6-pre-gate-governance-2026-05-31.md](_knowledge/management/phase6-pre-gate-governance-2026-05-31.md) |
| 查看 Phase 6 Program 计划 | [phase6-program-plan.md](plans/phase6-program-plan.md) |
| 查看 Phase 6 Wave 1 执行计划 | [phase6-wave1-execution-plan.md](plans/phase6-wave1-execution-plan.md) |
| 查看 Phase 6 Wave 1 任务规格书 | [phase6-wave1-task-specs.md](plans/phase6-wave1-task-specs.md) |
| 查看 Phase 6 Wave 2 执行计划 | [phase6-wave2-execution-plan.md](plans/phase6-wave2-execution-plan.md) |
| 查看 Phase 6 Wave 3 执行计划 | [phase6-wave3-execution-plan.md](plans/phase6-wave3-execution-plan.md) |
| 查看 Phase 6 总收口复盘 | [phase6-closeout-retrospective.md](summaries/phase6-closeout-retrospective.md) |
| 查看 Phase 7 planning gate | [phase7-planning-gate.md](plans/phase7-planning-gate.md) |
| 查看 Phase 7 program plan | [phase7-program-plan.md](plans/phase7-program-plan.md) |
| 查看 Phase 7 starter packet spec | [phase7-starter-packet-spec.md](plans/phase7-starter-packet-spec.md) |
| 查看 Phase 7 ratification summary | [phase7-planning-ratification.md](summaries/phase7-planning-ratification.md) |
| 查看 Phase 7 Wave 1 执行计划 | [phase7-wave1-execution-plan.md](plans/phase7-wave1-execution-plan.md) |
| 查看 Phase 7 Wave 2 执行计划 | [phase7-wave2-execution-plan.md](plans/phase7-wave2-execution-plan.md) |
| 查看 Phase 7 Wave 3 执行计划 | [phase7-wave3-execution-plan.md](plans/phase7-wave3-execution-plan.md) |
| 查看 Phase 7 总收口复盘 | [phase7-closeout-retrospective.md](summaries/phase7-closeout-retrospective.md) |
| 查看 Phase 8 planning gate | [phase8-planning-gate.md](plans/phase8-planning-gate.md) |
| 查看 Phase 8 program plan | [phase8-program-plan.md](plans/phase8-program-plan.md) |
| 查看 Phase 8 starter packet spec | [phase8-starter-packet-spec.md](plans/phase8-starter-packet-spec.md) |
| 查看 Phase 8 ratification summary | [phase8-planning-ratification.md](summaries/phase8-planning-ratification.md) |
| 查看 Phase 8 Wave 1 closeout | [phase8-wave1-closeout.md](summaries/phase8-wave1-closeout.md) |
| 查看 Phase 8 Wave 2 execution plan | [phase8-wave2-execution-plan.md](plans/phase8-wave2-execution-plan.md) |
| 查看 Phase 8 Wave 2 closeout | [phase8-wave2-closeout.md](summaries/phase8-wave2-closeout.md) |
| 查看 Phase 8 Wave 3 execution plan | [phase8-wave3-execution-plan.md](plans/phase8-wave3-execution-plan.md) |
| 查看 Phase 8 Wave 3 closeout | [phase8-wave3-closeout.md](summaries/phase8-wave3-closeout.md) |
| 查看 Phase 8 retrospective | [phase8-closeout-retrospective.md](summaries/phase8-closeout-retrospective.md) |
| 查看 Phase 8 review | [phase8-review.md](summaries/phase8-review.md) |
| 查看 Phase 1-8 深度复盘 | [phase1-8-deep-retrospective.md](summaries/phase1-8-deep-retrospective.md) |
| 查看 Phase 9 架构重构计划 | [phase9-workspace-plane-refactor-plan.md](plans/phase9-workspace-plane-refactor-plan.md) |
| 查看 Phase 9 program | [phase9-program-plan.md](plans/phase9-program-plan.md) |
| 查看 Phase 9 Wave 2 执行包 | [phase9-wave2-execution-plan.md](plans/phase9-wave2-execution-plan.md) |
| 查看 Phase 9 Wave 3 执行包 | [phase9-wave3-execution-plan.md](plans/phase9-wave3-execution-plan.md) |
| 查看 Phase 9 Wave 4 执行包 | [phase9-wave4-execution-plan.md](plans/phase9-wave4-execution-plan.md) |
| 查看 Phase 10 program | [phase10-program-plan.md](plans/phase10-program-plan.md) |
| 查看 Phase 10 Wave 1 执行包 | [phase10-wave1-execution-plan.md](plans/phase10-wave1-execution-plan.md) |
| 查看 Phase 10 Wave 2 执行包 | [phase10-wave2-execution-plan.md](plans/phase10-wave2-execution-plan.md) |
| 查看 Phase 10 Wave 3 执行包 | [phase10-wave3-execution-plan.md](plans/phase10-wave3-execution-plan.md) |
| 查看 Phase 10 Wave 4 执行包 | [phase10-wave4-execution-plan.md](plans/phase10-wave4-execution-plan.md) |
| 查看 Phase 10 Wave 4 收口 | [phase10-wave4-closeout.md](summaries/phase10-wave4-closeout.md) |
| 查看 Phase 10 总复盘 | [phase10-closeout-retrospective.md](summaries/phase10-closeout-retrospective.md) |
| 查看 Phase 11 program | [phase11-program-plan.md](plans/phase11-program-plan.md) |
| 查看 Phase 11 Wave 1 收口 | [phase11-wave1-closeout.md](summaries/phase11-wave1-closeout.md) |
| 查看 Phase 11 Wave 3 执行包 | [phase11-wave3-execution-plan.md](plans/phase11-wave3-execution-plan.md) |
| 查看 Phase 11 Wave 4 收口 | [phase11-wave4-closeout.md](summaries/phase11-wave4-closeout.md) |
| 查看 Phase 12 completed program | [phase12-program-plan.md](plans/phase12-program-plan.md) |
| 查看 Phase 12 closeout | [phase12-closeout.md](summaries/phase12-closeout.md) |
| 查看 Phase 13 closeout | [phase13-closeout.md](summaries/phase13-closeout.md) |
| 查看 Phase 13 retrospective | [phase13-retrospective.md](summaries/phase13-retrospective.md) |
| 查看 Phase 14 closeout | [phase14-closeout.md](summaries/phase14-closeout.md) |
| 查看 Phase 14 retrospective | [phase14-retrospective.md](summaries/phase14-retrospective.md) |
| 查看 Phase 15 autonomous governance pre-planning | [phase15-autonomous-governance-preplanning.md](plans/phase15-autonomous-governance-preplanning.md) |
| 查看 Phase 9 首批迁移基线 | [phase9-first-migration-baseline.md](summaries/phase9-first-migration-baseline.md) |
| 查看 Phase 9 Wave 2 收口 | [phase9-wave2-closeout.md](summaries/phase9-wave2-closeout.md) |
| 查看 Phase 9 Wave 3 收口 | [phase9-wave3-closeout.md](summaries/phase9-wave3-closeout.md) |
| 查看 Phase 9 Wave 4 收口 | [phase9-wave4-closeout.md](summaries/phase9-wave4-closeout.md) |
| 查看 Phase 9 总复盘 | [phase9-closeout-retrospective.md](summaries/phase9-closeout-retrospective.md) |
| 新人上手指南 | [`ONBOARDING.md`](ONBOARDING.md) |

---

## 目录结构

```
.omo/                          ← 治理知识库根目录
├── INDEX.md                   ← ★ 四平面主入口（当前文件）
├── DOC-ARCH.md                ← ★ 文档架构蓝图
├── ONBOARDING.md              ← 新人上手指南（知识面:usage）
│
├── _control/                  ← ● 控制面：战略目标 + 系统状态 + 门禁
│   └── INDEX.md               →  state/, goals/, CONSISTENCY-CHECK
│
├── _truth/                    ← ● 事实面（SSOT）：任务/标准/实体
│   └── INDEX.md               →  tasks/, standards/, PROJECTS.yaml
│
├── _knowledge/                ← ● 知识面（WIKI）：5 子分类
│   ├── INDEX.md               →  总入口
│   ├── design/INDEX.md        →  plans/, MASTER-BLUEPRINT
│   ├── process/INDEX.md       →  RETRO-*, retro-*, wave-*
│   ├── management/INDEX.md    →  AUDIT.md, ARCH-AUDIT-*, DEBT-ANALYSIS
│   ├── usage/INDEX.md         →  ONBOARDING.md, CLI-MCP-SPEC.md
│   └── reference/INDEX.md     →  diagrams/, LESSONS.md, ARC-ONTOLOGY*
│
├── _delivery/                 ← ● 交付面：运行记录 + 证据 + 测试
│   └── INDEX.md               →  workers/runs/, tests/, evidence/
│
├── goals/                     → 战略目标（控制面 SSOT）
├── state/                     → 系统状态（控制面 SSOT）
├── tasks/                     → 任务 SSOT（事实面核心）
├── standards/                 → 标准 SSOT（事实面核心）
├── plans/                     → 计划文档（知识面:design）
├── workers/                   → Worker 调度 + 运行记录（事实面+交付面）
├── summaries/                 → 总结文档（知识面:管理/过程）
├── audits/                    → 审计报告（知识面:管理）
├── tests/                     → 测试（交付面）
├── diagrams/                  → 架构图（知识面:参考）
├── ../runtime/run-continuation/ → 会话续接（工作区运行时根）
├── evidence/                  → 交付证据（交付面）
├── drafts/                    → 草稿（知识面:管理）
├── task-prompts/              → Agent 提示词（知识面:参考）
└── ...                        → 其余各类文档
```

---

## Agent 使用约定

| 场景 | 入口 |
|------|------|
| Agent 启动时读取 | `INDEX.md` → `_control/INDEX.md` → 检查 `state/system.yaml` + `goals/current.yaml` |
| 查找可以认领的任务 | `_truth/INDEX.md` → `tasks/active/`（SSOT，strict-active-only） |
| 查阅某个标准 | `_truth/INDEX.md` → `standards/` |
| 查阅某个设计文档 | `_knowledge/design/INDEX.md` → `plans/` |
| 创建新的交付记录 | `_delivery/INDEX.md` → 对应位置写入 |

**SSOT 铁律**: 事实面数据不得在知识面文档中复制；引用时使用相对路径指针。

**历史文档定位**: [`STATE.md`](STATE.md) = 架构历史与演进里程碑（legacy summary），当前运行状态以 `state/system.yaml` 与 `goals/current.yaml` 为准。

---

*维护: 2026-05-31 · 四平面文档架构 v1.1（已融合现有 .omo 机制）*

---

> **文档体系新建文件清单**
>
> | 文件 | 用途 |
> |------|------|
> | `DOC-ARCH.md` | 四平面文档架构蓝图 |
> | `_control/INDEX.md` | 控制面导航索引 |
> | `_truth/INDEX.md` | 事实面 SSOT 导航索引 |
> | `_knowledge/INDEX.md` | 知识面总导航索引 |
> | `_knowledge/design/INDEX.md` | 设计文档索引 |
> | `_knowledge/process/INDEX.md` | 过程文档索引 |
> | `_knowledge/management/INDEX.md` | 管理文档索引 |
> | `_knowledge/usage/INDEX.md` | 使用文档索引 |
> | `_knowledge/reference/INDEX.md` | 参考文档索引 |
> | `_delivery/INDEX.md` | 交付面导航索引 |
