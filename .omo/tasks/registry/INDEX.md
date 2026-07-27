# Tasks Registry — 结构化任务注册表

> 替代 system.yaml 中的 orphaned_tasks blob。
> 每个任务有独立 YAML 文件。system.yaml 只保留指针引用。
> **SSOT**: 任务文件在 `tasks/` 下。本文档由验证流程生成，与实际目录保持同步。
> 
> **计数口径**: 与 `omo state sync-tasks` 保持一致，只统计 `tasks/{active,planned,done}/` 顶层 `*.yaml` 文件（不含子目录与草稿）。

## Active Tasks

当前无活跃任务。所有 in-progress 任务通过 `.omo/tasks/planned/` 排队等待认领。

## Planned Tasks (13 个)
| ID | Title | Status |
|----|-------|--------|
| OPC-P6-SELF-EVOLUTION-doc-gate-e | Reconcile docs/OPC-PHASE4 with OPC-P4 plan yaml | candidate |
| cockpit-debt-debt-1 | 治理技术债务：债务 | candidate |
| needs-human-batch2-physical-recovery-checklist | 机器恢复日验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁） | candidate |
| needs-human-batch2-role-expansion-proposal | Batch2 B3: 第 4/5 角色（research/delivery）实装提案（评估页已齐 | candidate |
| needs-human-batch3-proposal | STRAT-P81 Batch 3 提案（物理 KPI 冲刺主轴 · 待人类拍板） | candidate |
| needs-human-gbrain-427-red-failures | gbrain 427红灯 — mock.module隔离根因已定位 (1根因→427 casca | candidate |
| needs-human-ingress-registry-drift | ingress-registry 28 task carrier missing (cockpi | candidate |
| needs-human-metaos-phase12-d1-d4 | metaos 治理批 Phase 1/2 前提: D1-D4 四项决策 (CLI/PID/age | candidate |
| needs-human-mof-m4-d1-d4-decisions | MOF/M4 治理优化 D1-D4 决策签核 (Phase 1/2 启动前置 | candidate |
| needs-human-p80-phase45-bos-stdio | P80 T1.2 residual: bos_stdio_ratio < 65% (live ~ | candidate |
| needs-human-p80-physical-hosts | P80 T2: expand physical hosts ≥4 + G-DEL.3 true | candidate |
| needs-human-p81-batch4-proposal | STRAT-P81 Batch 4 提案（多 agent 协作深化主轴 · C 波 · 待人类拍 | candidate |
| needs-human-p81-m1-acceptance | P81 S0.1: M1 提前验收申请（ADR-0210 Confirmation · 人类拍板 | candidate |

> **补充规划**: `.omo/tasks/planned/vision-roadmap/` 子目录保留长期愿景路线图（4 YAML + 5 MD），不纳入标准 planned 任务计数。

## Completed Tasks (0 个)

> `tasks/done/` — 0 个顶层 YAML 文件，子目录按 Phase/主题分组存放历史任务。

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
*Updated: 2026-07-27 (依据 `omo state sync-tasks` 与真实目录重算: done=0, planned=13, active=0, archived=6 顶层)*
*Sync command: `omo state sync-tasks`*
