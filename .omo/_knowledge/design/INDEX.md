# 设计文档 — `_knowledge/design/`

> 架构设计、蓝图、路线图、规格书。回答"系统的设计是什么？要去哪？"

---

## 设计文档总览

### 计划注册表 — `plans/`

> 所有计划文档以 `plans/README.md` 为注册表入口，按 6 种状态分类（EXECUTION / GATED / ACTIVE / REFERENCE / ARCHIVED / LEGACY）

| 计划文档 | 状态 | 描述 |
|---------|------|------|
| [debt-cleanup-plan.md](debt-cleanup-plan.md) | ACTIVE | Phase 17 债务清理方案（SharedBrain/D2/D3/健康分/门禁） |
| [sharedbrain-decomposition-architecture.md](sharedbrain-decomposition-architecture.md) | PRE_PLANNING | SharedBrain 824K 行 → kairon 架构拆分全案（能力矩阵/目标架构/4-Wave 路线图） |
| [plans/README.md](../../plans/README.md) | ACTIVE | 计划状态注册表与执行规则 |
| [plans/evolution-roadmap-4phases.md](../../plans/evolution-roadmap-4phases.md) | ACTIVE | 四阶段演进路线图 |
| [plans/kos-repair-plan.md](../../plans/kos-repair-plan.md) | ACTIVE | KOS 修复计划 |
| [plans/safe-mesh-rbac-deployment-roadmap.md](../../plans/safe-mesh-rbac-deployment-roadmap.md) | ACTIVE | Safe Mesh RBAC 部署路线图 |
| [plans/llm-convergence-requirements.md](../../plans/llm-convergence-requirements.md) | ACTIVE | LLM 收敛需求 |
| [plans/llm-convergence-planning-packet.md](../../plans/llm-convergence-planning-packet.md) | ACTIVE | LLM 收敛规划包 |
| [phase4-execution-roadmap.md](../../plans/archive/phase4-execution-roadmap.md) | Phase 4 Execution Roadmap | ARCHIVED |
| [phase4-wave2-hardening-design.md](../../plans/archive/phase4-wave2-hardening-design.md) | Phase 4 Wave 2 Hardening Design | ARCHIVED |
| [phase4-wave2-hardening-implementation-plan.md](../../plans/archive/phase4-wave2-hardening-implementation-plan.md) | Phase 4 Wave 2 Hardening Implementation Plan | ARCHIVED |
| [omo-fusion-optimization-blueprint.md](../../plans/omo-fusion-optimization-blueprint.md) | ACTIVE | 四平面机制进一步融合升级蓝图 |
| [plans/phase2-phase3-task-manifest.md](../../plans/archive/phase2-phase3-task-manifest.md) | Phase 2 Phase 3 Task Manifest | ARCHIVED |
| [standards/post-phase1-governance-and-phase2-entry.md](../../standards/post-phase1-governance-and-phase2-entry.md) | LEGACY | Phase 1 后治理与 Phase 2 入口（历史gate快照） |
| | | |
| [plans/phase2-task-specs-v2.md](../../plans/archive/phase2-task-specs-v2.md) | Phase 2 Task Specs V2 | ARCHIVED |
| [plans/phase3-task-specs-v2.md](../../plans/archive/phase3-task-specs-v2.md) | Phase 3 Task Specs V2 | ARCHIVED |
| [plans/phase4-task-specs-v2.md](../../plans/archive/phase4-task-specs-v2.md) | Phase 4 Task Specs V2 | ARCHIVED |
| | | |
| [plans/architecture-final-vision.md](../../plans/architecture-final-vision.md) | REFERENCE | 最终架构愿景 |
| [plans/comprehensive-architecture-audit.md](../../plans/comprehensive-architecture-audit.md) | REFERENCE | 全面架构审计 |
| [plans/agent-architecture-audit-redteam.md](../../plans/agent-architecture-audit-redteam.md) | REFERENCE | Agent 架构红队审计 |
| [plans/deep-architecture-agent-analysis.md](../../plans/deep-architecture-agent-analysis.md) | REFERENCE | 深度 Agent 分析 |
| [plans/redteam-revision-patch.md](../../plans/redteam-revision-patch.md) | REFERENCE | 红队修订补丁 |
| [plans/beyond-phase4-vision.md](../../plans/beyond-phase4-vision.md) | REFERENCE | Phase 4 后愿景 |
| [plans/sharedbrain-kairon-integration.md](../../plans/sharedbrain-kairon-integration.md) | REFERENCE | SharedBrain-Kairon 集成 |
| [plans/tech-intelligence-2026q2.md](../../plans/tech-intelligence-2026q2.md) | REFERENCE | 2026 Q2 技术情报 |
| [plans/phase1-sprint-plan.md](../../plans/archive/phase1-sprint-plan.md) | Phase 1 Sprint Plan | ARCHIVED |
| [plans/phase1-task-specs.md](../../plans/archive/phase1-task-specs.md) | Phase 1 Task Specs | ARCHIVED |
| [plans/phase1-verification-report.md](../../plans/archive/phase1-verification-report.md) | Phase 1 Verification Report | ARCHIVED |

> 归档计划见 [plans/archive/](../../plans/archive/)（35+ 历史计划文档）

### 需求规格书

| 文件 | 用途 | 状态 |
|------|------|------|
| [task-center-requirements.md](task-center-requirements.md) | Task Center 需求文档 v0.2.1（收敛修订版） | draft — 待审批 |
| [phase5-requirements.md](phase5-requirements.md) | Phase 5 需求文档：OMO 级流程治理（聚焦 Durable Execution / Governance Pipeline / Auto-Discovery / Templates / Skill Federation） | draft — 初稿（基于 28 方案行业对标） |
| [phase5-entry-architecture.md](phase5-entry-architecture.md) | Phase 5 入口桥接设计：先完成 Phase 4 closeout，再进入 Entry Gate / Wave 0 | active |
| [phase5-program-architecture.md](phase5-program-architecture.md) | Phase 5 总纲设计：主 program、四平面边界、wave 结构与 go/no-go 规则 | active |
| [plans/phase5-program-plan.md](../../plans/archive/phase5-program-plan.md) | Phase 5 Program Plan | ARCHIVED |
| [plans/phase5-entry-gate-checklist.md](../../plans/archive/phase5-entry-gate-checklist.md) | Phase 5 Entry Gate Checklist | ARCHIVED |
| [plans/phase6-program-plan.md](../../plans/archive/phase6-program-plan.md) | Phase 6 Program Plan | ARCHIVED |
| [plans/phase6-wave1-execution-plan.md](../../plans/archive/phase6-wave1-execution-plan.md) | Phase 6 Wave 1 Execution Plan | ARCHIVED |
| [plans/phase6-wave1-task-specs.md](../../plans/archive/phase6-wave1-task-specs.md) | Phase 6 Wave 1 Task Specs | ARCHIVED |
| [plans/phase6-wave2-execution-plan.md](../../plans/archive/phase6-wave2-execution-plan.md) | Phase 6 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase6-wave3-execution-plan.md](../../plans/archive/phase6-wave3-execution-plan.md) | Phase 6 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase7-planning-gate.md](../../plans/archive/phase7-planning-gate.md) | Phase 7 Planning Gate | ARCHIVED |
| [plans/phase7-program-plan.md](../../plans/archive/phase7-program-plan.md) | Phase 7 Program Plan | ARCHIVED |
| [plans/phase7-planning-analysis-requirements.md](../../plans/phase7-planning-analysis-requirements.md) | Phase 7 全面需求分析：10 章（架构/战略/红队/交叉分析/D1-D7） | active |
| [plans/phase7-starter-packet-spec.md](../../plans/archive/phase7-starter-packet-spec.md) | Phase 7 Starter Packet Spec | ARCHIVED |
| [plans/phase7-wave1-execution-plan.md](../../plans/archive/phase7-wave1-execution-plan.md) | Phase 7 Wave 1 Execution Plan | ARCHIVED |
| [plans/phase7-wave2-execution-plan.md](../../plans/archive/phase7-wave2-execution-plan.md) | Phase 7 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase7-wave3-execution-plan.md](../../plans/archive/phase7-wave3-execution-plan.md) | Phase 7 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase8-planning-gate.md](../../plans/archive/phase8-planning-gate.md) | Phase 8 Planning Gate | ARCHIVED |
| [plans/phase8-program-plan.md](../../plans/archive/phase8-program-plan.md) | Phase 8 Program Plan | ARCHIVED |
| [plans/phase8-starter-packet-spec.md](../../plans/archive/phase8-starter-packet-spec.md) | Phase 8 Starter Packet Spec | ARCHIVED |
| [plans/phase8-wave2-execution-plan.md](../../plans/archive/phase8-wave2-execution-plan.md) | Phase 8 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase8-wave3-execution-plan.md](../../plans/archive/phase8-wave3-execution-plan.md) | Phase 8 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase9-workspace-plane-refactor-plan.md](../../plans/archive/phase9-workspace-plane-refactor-plan.md) | Phase 9 Workspace Plane Refactor Plan | ARCHIVED |
| [plans/phase9-program-plan.md](../../plans/archive/phase9-program-plan.md) | Phase 9 Program Plan | ARCHIVED |
| [plans/phase9-wave2-execution-plan.md](../../plans/archive/phase9-wave2-execution-plan.md) | Phase 9 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase9-wave3-execution-plan.md](../../plans/archive/phase9-wave3-execution-plan.md) | Phase 9 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase9-wave4-execution-plan.md](../../plans/archive/phase9-wave4-execution-plan.md) | Phase 9 Wave 4 Execution Plan | ARCHIVED |
| [plans/phase10-program-plan.md](../../plans/archive/phase10-program-plan.md) | Phase 10 Program Plan | ARCHIVED |
| [plans/phase10-wave1-execution-plan.md](../../plans/archive/phase10-wave1-execution-plan.md) | Phase 10 Wave 1 Execution Plan | ARCHIVED |
| [plans/phase10-wave2-execution-plan.md](../../plans/archive/phase10-wave2-execution-plan.md) | Phase 10 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase10-wave3-execution-plan.md](../../plans/archive/phase10-wave3-execution-plan.md) | Phase 10 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase10-wave4-execution-plan.md](../../plans/archive/phase10-wave4-execution-plan.md) | Phase 10 Wave 4 Execution Plan | ARCHIVED |
| [plans/phase11-program-plan.md](../../plans/archive/phase11-program-plan.md) | Phase 11 Program Plan | ARCHIVED |
| [plans/phase11-wave1-execution-plan.md](../../plans/archive/phase11-wave1-execution-plan.md) | Phase 11 Wave 1 Execution Plan | ARCHIVED |
| [plans/phase11-wave2-execution-plan.md](../../plans/archive/phase11-wave2-execution-plan.md) | Phase 11 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase11-wave3-execution-plan.md](../../plans/archive/phase11-wave3-execution-plan.md) | Phase 11 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase11-wave4-execution-plan.md](../../plans/archive/phase11-wave4-execution-plan.md) | Phase 11 Wave 4 Execution Plan | ARCHIVED |
| [summaries/SB-DECISION.md](../../summaries/SB-DECISION.md) | SharedBrain long-term decision：selective extraction + layered contraction | active |
| [summaries/phase11-wave2-adr-ontoderive-inference-metatype.md](../../summaries/phase11/phase11-wave2-adr-ontoderive-inference-metatype.md) | Wave 2 ADR：OntoDerive Inference adopts additive `meta_type` | active |
| [summaries/phase11-wave2-adr-ontoderive-scheme-metatype.md](../../summaries/phase11/phase11-wave2-adr-ontoderive-scheme-metatype.md) | Wave 2 ADR：OntoDerive Scheme adopts additive `meta_type` | active |
| [summaries/phase11-wave2-adr-minerva-relation-metarelation.md](../../summaries/phase11/phase11-wave2-adr-minerva-relation-metarelation.md) | Wave 2 ADR：Minerva Relation adopts additive `meta_relation` | active |
| [summaries/phase11-wave4-adr-kos-canonical-metatype.md](../../summaries/phase11/phase11-wave4-adr-kos-canonical-metatype.md) | Wave 4 ADR：KOS canonical MetaType SSOT aligns ingest and CLI | active |
| [summaries/phase11-wave4-adr-eidos-protocol-contract-surface.md](../../summaries/phase11/phase11-wave4-adr-eidos-protocol-contract-surface.md) | Wave 4 ADR：`eidos.protocols` extends from runtime Protocols to serialized payload contracts | active |
| [plans/phase12-planning-gate.md](../../plans/archive/phase12-planning-gate.md) | Phase 12 Planning Gate | ARCHIVED |
| [plans/phase12-program-plan.md](../../plans/archive/phase12-program-plan.md) | Phase 12 Program Plan | ARCHIVED |
| [phase12-14-architecture-design.md](phase12-14-architecture-design.md) | Phase 12-14 architecture design：P12 foundation, P13 supervised metacognition, P14 deferred expansion, OMO mechanism support | pre_planning |
| [plans/phase12-wave1-execution-plan.md](../../plans/archive/phase12-wave1-execution-plan.md) | Phase 12 Wave 1 Execution Plan | ARCHIVED |
| [plans/phase12-wave2-execution-plan.md](../../plans/archive/phase12-wave2-execution-plan.md) | Phase 12 Wave 2 Execution Plan | ARCHIVED |
| [plans/phase12-wave3-execution-plan.md](../../plans/archive/phase12-wave3-execution-plan.md) | Phase 12 Wave 3 Execution Plan | ARCHIVED |
| [plans/phase12-wave4-execution-plan.md](../../plans/archive/phase12-wave4-execution-plan.md) | Phase 12 Wave 4 Execution Plan | ARCHIVED |
| [plans/phase12-wave5-execution-plan.md](../../plans/archive/phase12-wave5-execution-plan.md) | Phase 12 Wave 5 Execution Plan | ARCHIVED |
| [plans/phase13-metacognition-preplanning.md](../../plans/archive/phase13-metacognition-preplanning.md) | Phase 13 Metacognition Preplanning | ARCHIVED |
| [plans/phase14-deferred-ecosystem-backlog.md](../../plans/archive/phase14-deferred-ecosystem-backlog.md) | Phase 14 Deferred Ecosystem Backlog | ARCHIVED |
| [plans/phase14-program-plan.md](../../plans/archive/phase14-program-plan.md) | Phase 14 Program Plan | ARCHIVED |
| [system-design-baseline.md](system-design-baseline.md) | Post-Phase-14 canonical baseline：`4P3V1L` + `00/P0/I0/L1-L4/X1-X3` convergence and roadmap boundary | active baseline |
| [plans/phase15-autonomous-governance-preplanning.md](../../plans/phase15-autonomous-governance-preplanning.md) | Phase 15 pre-planning：承接基线，固化治理证据账本、策略测试、提案编译与恢复演练 | pre_planning |
| [phase15-autonomous-governance-design.md](phase15-autonomous-governance-design.md) | Phase 15 architecture design：governance evidence ledger, policy tests, proposal compiler, recovery rehearsal, Phase 16 handoff boundary | pre_planning |
| [plans/phase16-product-surface-convergence-preplanning.md](../../plans/phase16-product-surface-convergence-preplanning.md) | Phase 16 pre-planning：`P0` 产品入口层、统一场景壳与用户旅程收敛 | pre_planning |
| [plans/phase10-planning-analysis.md](../../plans/archive/phase10-planning-analysis.md) | Phase 10 Planning Analysis | ARCHIVED |
| [reviews/INDEX.md](reviews/INDEX.md) | 审阅报告目录（3 份并行审阅，评审对象为 v0.1 底稿） | — |
| [hermes-convergence-strategy.md](hermes-convergence-strategy.md) | Hermes 收敛策略 — Phase 5 输入（方向 A 主推荐 + 方向 B 参考） | active |
| [hermes-research-notes.md](hermes-research-notes.md) | Hermes 研究过程记录（源文件清单 + 关键发现） | reference |

### 蓝图与路线图

| 文件 | 用途 | 状态 |
|------|------|------|
| [MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md) | 全景蓝图 v1.2（10 条架构法则） | active |
| [INSIGHTS-AND-ROADMAP.md](INSIGHTS-AND-ROADMAP.md) | 见解与路线图 | active |

### 已归档设计文档

| 文件 | 用途 | 状态 |
|------|------|------|
| [plans/dbo-archive/](../../plans/dbo-archive/) | Digital Brain OS 历史计划 | archived |

---

## 设计文档规范

- 新设计提案遵循 `plans/templates/proposal-template.md` 格式
- Sprint 计划遵循 `plans/templates/sprint-plan-template.md`
- Wave 计划遵循 `plans/templates/wave-plan-template.md`
- 涉及事实面（SSOT）的内容使用指针引用，不复制数据

## 跨平面引用

| 引用目标 | 位置 | 用途 |
|---------|------|------|
| [控制面:目标与状态](../../_control/INDEX.md) | `_control/` | 设计目标的当前完成状态 |
| [事实面:任务 SSOT](../../_truth/INDEX.md) | `_truth/` | 设计对应的可执行任务 |

---

*维护: 2026-06-01 · 计划文档状态以 plans/README.md 为准*
