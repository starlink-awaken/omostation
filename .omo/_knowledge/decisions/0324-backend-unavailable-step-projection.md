---
id: ADR-0324
title: BackendUnavailable 的 WorkflowRun 与 StepRun 投影一致性
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0323-sandbox-toolpack-failure-recovery.md
---

# ADR-0324: BackendUnavailable 的 WorkflowRun 与 StepRun 投影一致性

## 决策

当 `BackendUnavailable` 事件携带 `step_run_id` 时，Workflow Mesh 将对应 StepRun 投影为
`unavailable`，与 WorkflowRun 的状态保持一致。事件不携带 StepRun 上下文的历史兼容事件仍可
用于表示整个 WorkflowRun 不可用，不强行生成虚假的 StepRun。

该映射只修正读模型，不改变状态机、租约、恢复或重试权限。恢复必须继续通过既有
`WorkflowRecovered` 或 `WorkerLeaseExpired -> WorkerReclaimed` 流程，新的执行尝试必须使用
新的 StepRun attempt 和有效 worker lease。

## 验证

- sandbox `unavailable` 结果的 WorkflowRun 和 StepRun 都为 `unavailable`。
- 既有状态机、worker lifecycle、receipt 和 operations projection 回归测试继续通过。

