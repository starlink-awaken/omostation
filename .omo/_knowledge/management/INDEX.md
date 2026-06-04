# 管理文档 — `_knowledge/management/`

> 审计报告、评审记录、影响分析、债务分析。回答"系统的健康状况如何？有哪些风险要管理？"
> 
> 本地文件数: ~7 | 编目引用数: ~17（跨 audits/、顶层、summaries/、drafts/、plans/）

---

## 管理机制

| 机制 | 说明 | 规范 |
|------|------|------|
| **审计报告** | 全面/专题审计，含发现分级和修复建议 | 标注范围、方法、critical/major/minor 分级 |
| **影响分析** | 变更/迁移的波及面评估 | 影响范围 → 风险矩阵 → 迁移路径 → 回退方案 |
| **债务分析** | 技术债务量化追踪 | 分类 → 量化 → 优先级 → 修复计划 |
| **清理与运维** | 基础设施清理/运维操作记录 | 操作前状态 → 操作步骤 → 验证结果 → 遗留事项 |
| **知识架构** | 知识基座架构定义与场景分析 | 架构设计 + 场景分析 + 跨平面引用 |

## 文档目录

| 文件 | 用途 | 位置 |
|------|------|------|
| [AUDIT.md](../../AUDIT.md) | 全面审计报告 | 顶层 |
| [ARCH-AUDIT-2026-05.md](ARCH-AUDIT-2026-05.md) | 架构审计 2026-05 | 顶层 |
| [ARCH-AUDIT-v2.md](ARCH-AUDIT-v2.md) | 架构审计 v2 | 顶层 |
| [ARCH-REVIEW.md](ARCH-REVIEW.md) | 架构评审 | 顶层 |
| [audits/phase2-comprehensive-audit-20260530.md](../../audits/phase2-comprehensive-audit-20260530.md) | Phase 2 全面审计 | audits/ |
| [debt-systems-analysis-and-governance.md](debt-systems-analysis-and-governance.md) | 系统思维债务深度分析 + 治理建议 (SystemsThinking/Iceberg/Archetype/Leverage) | 本目录 |
| [debt-cleanup-plan.md](../design/debt-cleanup-plan.md) | Phase 17 债务清理完整方案设计（SharedBrain/D2/D3/健康分/门禁/路线图） | design/ |
| [omo-convergence-audit-2026-05-31.md](omo-convergence-audit-2026-05-31.md) | `.omo` 收敛/腐败审计 | 本目录 |
| [phase6-pre-gate-governance-2026-05-31.md](phase6-pre-gate-governance-2026-05-31.md) | Phase 6 前置治理决策包 | 本目录 |
| [phase1-6-comprehensive-review.md](phase1-6-comprehensive-review.md) | Phase 1-6 全面 Review（5 维度评估） | 本目录 |
| [phase8-analysis-verification.md](phase8-analysis-verification.md) | Phase 8 分析与验证（任务/架构/债务/遗留） | 本目录 |
| [phase9-debt-cleanup-plan.md](phase9-debt-cleanup-plan.md) | Phase 9 债务清理需求分析（25 项/3 Wave/红队 R1-R3）— 被 Phase 10 取代 | 本目录 |
| [phase10-cross-audit.md](phase10-cross-audit.md) | Phase 10 交叉审计报告：15 项发现（4 严重/6 主要/5 次要） | 本目录 |
| [phase12-13-cross-review-2026-06-01.md](phase12-13-cross-review-2026-06-01.md) | Phase 12/13 多维度交叉审议与修订记录 | 本目录 |
| [phase12-14-cross-review-2026-06-01.md](phase12-14-cross-review-2026-06-01.md) | Phase 12-14 架构方案交叉审议与机制支撑评估 | 本目录 |
| [phase12-cross-audit.md](phase12-cross-audit.md) | Phase 12 能力生态底座交叉审计 | 本目录 |
| [phase12-redteam.md](phase12-redteam.md) | Phase 12 红队审议与风险控制记录 | 本目录 |
| [phase14-cross-audit.md](phase14-cross-audit.md) | Phase 14 deferred ecosystem expansion 交叉审计 | 本目录 |
| [phase15-cross-review-2026-05-31.md](phase15-cross-review-2026-05-31.md) | Phase 15 受控自治治理闭环交叉审议与机制支撑评估 | 本目录 |
| [plans/phase10-planning-analysis.md](../../plans/archive/phase10-planning-analysis.md) | Phase 10 债务治理需求分析：25 项+3 状态修复/3 Wave/红队 R1-R4（交叉审计修订版 v1.1） | plans/ |

## 影响分析与债务

| 文件 | 用途 | 位置 |
|------|------|------|
| [DEBT-ANALYSIS.md](DEBT-ANALYSIS.md) | 技术债务分析 | 顶层 |
| [KOS_MIGRATION_IMPACT.md](KOS_MIGRATION_IMPACT.md) | KOS 迁移影响分析 | 顶层 |
| [CLEANUP.md](../../CLEANUP.md) | 清理策略 | 顶层 |

## 知识架构

| 文件 | 用途 | 位置 |
|------|------|------|
| [../reference/KNOWLEDGE_ARCH.md](../reference/KNOWLEDGE_ARCH.md) | 知识架构定义 | 顶层 |
| [drafts/scenario-analysis.md](../../drafts/scenario-analysis.md) | 场景分析草稿 | drafts/ |

## 清理与运维操作

| 文件 | 用途 | 位置 |
|------|------|------|
| [scheduling-cleanup-2026-05-31.md](scheduling-cleanup-2026-05-31.md) | 调度基础设施清理记录 | 本目录 |

## 其他管理文档

| 文件 | 用途 | 位置 |
|------|------|------|
| [summaries/agent-task-contract.md](../../summaries/agent-task-contract.md) | Agent 任务契约 | summaries/ |
| [summaries/digitalbrainos-summary.md](../../summaries/digitalbrainos-summary.md) | DigitalBrainOS 总结 | summaries/ |
| [summaries/data-flow.md](../../summaries/data-flow.md) | 数据流文档 | summaries/ |
| [summaries/4-plus-1-plus-3-architecture-mapping.md](../../summaries/4-plus-1-plus-3-architecture-mapping.md) | 4+1+3 架构映射 | summaries/ |
| [summaries/full-architecture-audit-redteam-v3.md](../../summaries/full-architecture-audit-redteam-v3.md) | 完整架构审计 v3 | summaries/ |

---

## 管理文档规范

- 审计文档应标注审计范围、方法、发现（分级: critical/major/minor）、建议
- 影响分析应包含: 影响范围 → 风险矩阵 → 迁移路径 → 回退方案
- 债务分析应包含: 分类 → 量化 → 优先级 → 修复计划
- 管理文档引用事实面数据时使用指针（相对路径），不复制 SSOT 内容

## 跨平面引用

| 引用目标 | 位置 | 用途 |
|---------|------|------|
| [控制面:状态与门禁](../../_control/INDEX.md) | `_control/` | 审计发现对应的系统状态 |
| [事实面:标准 SSOT](../../_truth/INDEX.md) | `_truth/` | 审计依据的标准 |
| [知识面:设计文档](../design/INDEX.md) | `_knowledge/design/` | 审计对应的设计方案 |

---

*维护: 2026-05-31*
