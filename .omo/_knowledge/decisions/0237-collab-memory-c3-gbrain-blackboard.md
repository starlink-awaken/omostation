---
id: ADR-0237
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-07-25
related:
  - 0235-role-catalog-c1-research-delivery.md
  - 0236-collab-protocol-c2-deepening.md
  - STRAT-P81-strategic-roadmap.md
supersedes: []
amends: []
type: ssot
---

# ADR-0237: C3 协作记忆 — gbrain 公共黑板（跨任务上下文复用）

## Context

STRAT-P81 Batch3 C3 要求 gbrain 共享上下文成为**公共黑板**：角色协作产物写入，
后续任务可检索复用，隔离边界 + 检索质量并重。`AgentSharedContextStore`（G-DEL.4 /
BET-b7da）已有 scope-keyed store + readers 可见性，是公共黑板的天然基底。
C1（research/delivery）+ C2（多轮协商）产生的协作产物需要落盘到黑板供跨任务复用。

## Decision

扩展 `projects/gbrain/src/core/agent-shared-context.ts::AgentSharedContextStore`：

1. **`CollabProductEntry`** interface：协作产物结构（taskRef / fromRole / toRole /
   messageType / correlationId / payload / writer）。
2. **`writeCollabProduct(entry)`**：写入公共黑板。scope=taskRef；tags=[fromRole,
   messageType, toRole?]；readers 空 → 对 scope 内所有 agent 可见（公共黑板语义）。
3. **`retrieveCollab(reader, opts)`**：检索协作产物。taskRef 省略 → 跨 scope（跨任务）
   检索；fromRole/messageType 按 tags 过滤。**C3 核心：后续任务复用前序协作产物**。

**隔离边界**：复用 store 现有 readers 机制（private readers list 隐藏非列出 agent）；
公共黑板 entries readers 空（全 scope 共享）。role-based 可见性由 tags + readers 组合表达。

## Confirmation

- `projects/gbrain/test/agent-shared-context.test.ts` **9 tests pass**（原 5 回归 + C3 新增 4）
- writeCollabProduct 写入 + role tags 正确
- retrieveCollab 跨任务检索（taskA research_result + taskB delivery_registered）
- retrieveCollab by fromRole 过滤
- writeCollabProduct 校验 required fields（taskRef/fromRole/messageType）

## Status

**ACCEPTED** for Batch3 C3 blackboard extension (2026-07-25)。隔离测试深化 +
检索命中率基线入 audits + role-based 写权限收紧（research 只读/无写）后续轮。
