# Tasks Registry — 结构化任务注册表

> 替代 system.yaml 中的 orphaned_tasks blob。
> 每个任务有独立 YAML 文件。system.yaml 只保留指针引用。

## Active Tasks (active/)

当前无活跃任务。所有 previously stale 任务已归档至 `tasks/done/`。

## Planned Tasks (planned/)

当前无计划任务。P22-W2 (Pontus quality) 和 P25-W1 (E2E集成测试) 已在之前会话中完成。

## Completed Tasks (done/)

> 156 tasks completed. See `tasks/done/` for full listing.

Key completions:
- Phase 3-16 — 全量完成
- P17-W1/2/3/4 — Architecture foundation + protocols v1 + gap analysis + agentmesh audit
- P18-W1/2/3/4 — NeuralCenter + CircuitEngine + NeuronPool + D_Window cleanup
- P19-W1/2/3 — Agent runtime + Agent Hub + TS archive
- P20-W1/2/3/4 — Economy/KI/Extension/Harness extraction to kairon
- P21-W1/2/3/4 — Immunity/Genesis/observability/gc-engine
- P22-W1 — Pontus DSL + scheduler
- P23-W1/2 — Hermes Console scaffold + dashboard
- P24-W1/2 — BaseMembrane zero + Nucleus替换
- P25-W2 — 文档终稿+债务关闭
- D2-CI-E2E-TEST-ENV — CI E2E baseline
- D3-EU-PRICING-TEST — eu-pricing 独立测试
- SHAREDBRAIN-FORMAL-DECISION — SharedBrain 归档决策
- P17-DEBT-GOVERNANCE-GATE-RULES — Phase 17 债务门禁
- ORPHANED-TASKS-STRUCTURED-REGISTRY — Orphaned tasks 结构化

## Blocked Tasks (blocked/)

| ID | Title | Blocker |
|----|-------|---------|
| M2.6-APPLE-CONNECTOR-BLOCKED-SPEC | Apple connector | Safe Mesh gate |
| M2.6-WECHAT-SMB-MEDIA-DEFERRED-SPECS | WeChat/SMB/Media | RBAC gate |

---
*Updated: 2026-06-03*
