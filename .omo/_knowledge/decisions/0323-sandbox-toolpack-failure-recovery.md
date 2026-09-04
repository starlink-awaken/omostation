---
id: ADR-0323
title: Workflow Mesh Sandbox ToolPack 失败、不可用与恢复契约
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0322-sandbox-toolpack-mesh-execution.md
  - 0299-workflow-mesh-worker-lease-and-reclaim.md
---

# ADR-0323: Workflow Mesh Sandbox ToolPack 失败、不可用与恢复契约

## 背景

ADR-0322 只验证了受控 sandbox ToolPack 的成功、回执和幂等回放。真实 provider 尚未激活，
但执行控制面必须先证明“失败不会伪造成功、后端不可用可以重放、租约失效后可以安全接管”。
否则后续接入外部知识、数据、工具和渠道时，provider 异常会被错误地解释为业务完成。

## 决策

1. `ToolInvocationRecorded` 必须携带 provider-neutral `outcome`，取值只能是 `succeeded`、
   `failed` 或 `unavailable`；sandbox runner 仍固定 `activation=sandbox` 和
   `external_side_effects=disabled`。
2. `succeeded` 只能继续 `WorkflowSucceeded -> EvidenceRecorded`；`failed` 追加
   `StepFailed`，`unavailable` 追加 `BackendUnavailable`。两条非成功路径只允许稳定错误码
   `SANDBOX_TOOL_FAILED` 或 `SANDBOX_BACKEND_UNAVAILABLE`，不创建成功 receipt/evidence。
3. 同一 invocation identity 的失败或不可用调用必须幂等回放，内容改变视为冲突；不能以改变
   outcome 的方式重写既有 invocation。业务重试必须由协调方显式恢复并创建新的 StepRun attempt。
4. worker lease 失效后，执行器拒绝旧 worker 上下文；恢复必须复用既有
   `WorkerLeaseExpired -> WorkerReclaimed`，由 successor dispatch/ack 建立新租约，再用新的
   attempt 执行。reclaim 本身不是成功证据。
5. 运营投影统计 sandbox outcome，但不把 sandbox 成功当业务成功；真实 provider 仍须通过具体
   Scene Card、admission、receipt 和 Outcome Feedback 证明业务价值。

## 不在本 ADR 内

- 不激活外部 provider、私人资料、网络调用或真实业务副作用。
- 不自动选择 successor、不自动补偿、不自动重试，不新增 scheduler 或 workflow engine。
- 不允许 provider-specific 错误原文、凭据或输出进入 Mesh 事件。

## 验证

- sandbox 失败和不可用均不产生 `WorkflowSucceeded` 或 `EvidenceRecorded`，重复调用不增加事件。
- lease expiry 后 successor 使用新的 attempt 成功执行并留证；旧 worker 上下文继续被拒绝。
- OMO Workflow Mesh、worker lifecycle、external receipt 和 operations projection 回归测试通过。

