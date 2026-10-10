---
type: ephemeral
status: archived
---

# Tasks Registry — 结构化任务注册表

> 替代 system.yaml 中的 orphaned_tasks blob。
> 每个任务有独立 YAML 文件。system.yaml 只保留指针引用。
> **SSOT**: 任务文件在 `tasks/` 下。本文档由验证流程生成，与实际目录保持同步。
> 
> **计数口径**: 与 `omo state sync-tasks` 保持一致，只统计 `tasks/{active,planned,done}/` 顶层 `*.yaml` 文件（不含子目录与草稿）。

## Active Tasks (3 个)
| ID | Title | Status |
|----|-------|--------|
| BET-Y2Q4-T10-CJK-ROUTING | 修复 Memory OS 六条意图路由对中文查询失效 (CJK \b 边界缺陷 | active |
| BET-Y2Q4-T10-TEMPORAL-PRECEDENCE | 待决 — _TEMPORAL_RE 实际持有的时间词是否应压过文档/卡片类名词（classify | active |
| kos-q-growth-rolling | KOS 季度扩量持续监测 (rolling goal 关联 task | active |

## Planned Tasks (6 个)
| ID | Title | Status |
|----|-------|--------|
| TASK-019B7FD6 | aetherforge 网关密钥轮换 | candidate |
| TASK-152D15B1 | worktree-hygiene-audit: squash 合并的 worktree 永远判不 | candidate |
| TASK-263EF9EC | worktree 删除工具补子仓合并闸: janitor + gac-worktree.sh 与 | candidate |
| TASK-9BFD0422 | R4 回归泄漏: 高负载降级路径绕过沙箱台账重定向(2 条 E2E 入真实台账, 已清 | candidate |
| TASK-B7086225 | 断言分层改造: 21 场景断言按业务谓词 vs 实现细节分类重写 | candidate |
| TASK-C20AFD70 | cockpit 实时测试: 战略源 9 条 library 引用越界(治理决策) + 快照比对( | candidate |

> **补充规划**: `.omo/tasks/planned/vision-roadmap/` 子目录保留长期愿景路线图（4 YAML + 5 MD），不纳入标准 planned 任务计数。

## Completed Tasks (331 个)

> `tasks/done/` — 331 个顶层 YAML 文件，子目录按 Phase/主题分组存放历史任务。

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

## Blocked Tasks (0 个)
| ID | Title | Status |
|----|-------|--------|


---
*Updated: 2026-10-08 (依据 `omo state sync-tasks` 与真实目录重算: done=331, planned=6, active=3, blocked=0, archived=6 顶层)*
*Sync command: `omo state sync-tasks`*
