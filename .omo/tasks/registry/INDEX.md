# Tasks Registry — 结构化任务注册表

> 替代 system.yaml 中的 orphaned_tasks blob。
> 每个任务有独立 YAML 文件。system.yaml 只保留指针引用。
> **SSOT**: 任务文件在 `tasks/` 下。本文档由验证流程生成，与实际目录保持同步。
> 
> **计数口径**: 与 `omo state sync-tasks` 保持一致，只统计 `tasks/{active,planned,done}/` 顶层 `*.yaml` 文件（不含子目录与草稿）。

## Active Tasks

当前无活跃任务。所有 in-progress 任务通过 `.omo/tasks/planned/` 排队等待认领。

## Planned Tasks (15 个)
| ID | Title | Status |
|----|-------|--------|
| OPC-P6-SELF-EVOLUTION-doc-gate-e | Reconcile docs/OPC-PHASE4 with OPC-P4 plan yaml | candidate |
| OPC-P6-SELF-EVOLUTION-nop-20260628T221211Z | No-op: drift detector reported 0 drift; loop con | candidate |
| QUEST-5 | 测试每日打扫 | candidate |
| QUEST-6 | 测试每日打扫 | candidate |
| QUEST-7 | 测试每日打扫 | candidate |
| QUEST-8 | 测试每日打扫 | candidate |
| TASK-13AD0B21 | AETHERFORGE P1: L0 33 命名空间消费接入 (AUDIT 11%→提升 | candidate |
| TASK-236A991C | gac-gate doc refs/alert 债: cross-refs + dead-pat | candidate |
| TASK-2FB9244F | 项目 doc 契约: 17 项目三件套 + DIAGRAM/EVOLUTION | candidate |
| TASK-4D8EDEAC | c2g/l4-kernel 子仓 test 环境绑定 (launchd macOS + ingr | candidate |
| TASK-67C63D6C | AETHERFORGE P1: QuotaEngine 数据全用 (v2 Phase 1 收尾 | candidate |
| TASK-6B868907 | P1 产品门户: c2g draft→bet路径 + 全场景门户 | candidate |
| TASK-94BB9C70 | P1 并发Agent抢占: 共享文件advisory-lock | candidate |
| TASK-A367B061 | GaC 声明/执行鸿沟: 129 rules 缺 executor | candidate |
| TASK-F7114ABA | P1 GodModule: omo_ingress/agora/gbrain (行数见源码实测, | candidate |

> **补充规划**: `.omo/tasks/planned/vision-roadmap/` 子目录保留长期愿景路线图（4 YAML + 5 MD），不纳入标准 planned 任务计数。

## Completed Tasks (95 个)

> `tasks/done/` — 95 个顶层 YAML 文件，子目录按 Phase/主题分组存放历史任务。

近期关键完成里程碑（done/ 顶层）:
- P42-W0-W1-COMBO / P42-W2-COMBO — P42 治理面 SSOT 同步
- P43-W0-W3-COMBO — P43 4 wave 全面实施
- P44-W0-W4-COMBO / P44-REMEDIATE-WF-CONV-CLOSE / P44-SUBMODULE-PIN — P44 HTTP-MCP 收敛与收尾
- P45-DOC-LIFECYCLE / P45-W0-W3-COMBO — P45 BOS URI 收敛
- P46-MOF-IMPL — P46 MOF 实现
- P47-P52 系列 — CI 覆盖、GBR TODO、drafts 清理、MDrift 关闭等
- REMEDIATE-ARC-CONV-P1-CRON — 架构收敛 P1 完成
- SHAREDBRAIN-FORMAL-DECISION — SharedBrain 归档决策
- TASK-DEBT-CLOSURE-EVIDENCE-20260620 — 债务关闭 evidence
- TASK-KAIRON-MYPY-STRICT — kairon mypy strict 启用
- TASK-9B363829 — BOS 声明/执行鸿沟修复 (evidence-smoke resolve_rate=100)
- TASK-26348641 — 自反馈闭环 (feedback-loop-guard 3 维度 + mypy MYPYPATH=src baseline-gate)

完整列表请见 `tasks/done/` 目录及子目录。

## Archived Tasks (6 个顶层)

> `tasks/archived/` — 6 个顶层 YAML 文件，含历史 imported 任务与 legacy-normalized 子目录。

顶层 archived 任务:
- P35-ROADMAP
- OPC-P6-SELF-EVOLUTION-nop-20260614T114209Z
- OPC-P15-KAI-02
- P2-HARDCODED-PATHS-TICKET
- TASK-C2G-V2-EVOLUTION
- IMPORTED-58d3f8

> **注**: 子目录 `legacy-normalized/` 中包含 REMEDIATE-ARC-CONV-P2-CACHE 至 P6-CALIBRATE 等历史收敛任务，已在 BET-ARCH-CONVERGENCE 完成上下文下归档。

## Blocked Tasks

当前无阻塞任务。

---
*Updated: 2026-07-02 (依据 `omo state sync-tasks` 与真实目录重算: done=95, planned=15, active=0, archived=6 顶层)*
*Sync command: `omo state sync-tasks`*
