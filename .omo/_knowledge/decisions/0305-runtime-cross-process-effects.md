---
id: ADR-0305
title: Runtime 跨进程 effect journal 与显式补偿边界
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/external-connection-fabric.md
  - ./0304-runtime-effect-outcome-receipts.md
---

# ADR-0305: Runtime 跨进程 effect journal 与显式补偿边界

## 背景

Workflow Mesh 的 `effect_key` 只有在跨进程也能完成读、判重和追加的原子边界时，才足以防止
重复副作用。网络超时还存在一个额外风险：远端可能已经提交了操作，但 Runtime 没有收到
响应；自动补偿会把不确定状态扩大成第二个副作用。此前 effect journal 只提供进程内锁和
成功 replay，不能证明部署到多个 Runtime 进程后仍然只执行一次，也没有统一的补偿生命周期。

## 决策

1. `WorkflowEffectStore` 使用进程内 `RLock` 加同路径 lock file 的 `fcntl.flock`，覆盖
   `read -> check -> effect -> append` 的完整临界区。数据 JSONL 仍是本地恢复日志，lock file
   只负责并发协调，不成为业务事实源。
2. 前向 effect 的状态分为 `succeeded`、`degraded`、`failed` 和 `unavailable`。超时输出
   `EFFECT_TIMEOUT`，连接失败输出 `EFFECT_BACKEND_UNAVAILABLE`，权限和未知失败使用稳定
   `EFFECT_*` 错误码；不保存异常原文到安全摘要。
3. 只有 `succeeded/degraded` 才能编译为 `external-connection-receipt/v1`。失败和不可用只能
   通过 Mesh 的失败/不可用事件表达，不能进入 `EvidenceRecorded`。
4. 补偿是显式命令，不是超时自动动作。`compensate()` 只接受此前成功的 forward effect，
   使用独立 `record_type=compensation` journal，并对成功补偿幂等 replay；失败或不可用允许
   后续显式重试。
5. `AgentRuntime.compensate_effect()` 负责把补偿意图和结果映射为
   `CompensationStarted -> WorkflowRecovered`，或 `CompensationStarted -> StepFailed ->
   WorkflowFailed`。它不直接调用 OMO broker，也不把本地结果写入 Mesh。
6. provider-specific Channel/Tool 只有在真实 Scene Card、权限、责任人、结果指标和回执
   齐备后才接入；本 ADR 只提供可靠执行边界，不激活任何真实业务 provider。

## 不变量

- 两个 Runtime 进程使用同一 `effect_key` 时最多一个真实 forward effect 被执行。
- forward/replay/compensation 的安全 payload 不包含 prompt、tool arguments、provider output
  或 secret。
- 超时不自动补偿；没有明确补偿策略时保持 `unavailable` 并等待人工或连接器决策。
- 补偿成功不等于业务完成，也不会自动产生 `EvidenceRecorded`；业务验证仍需独立证据。
- OMO 仍是 Workflow Mesh 状态和证据真相，Runtime 仍只负责执行、恢复和安全回执摘要。

## 验收

- Runtime effect 定向测试通过：成功 replay、跨进程单次执行、超时分类、显式补偿幂等。
- Runtime Mesh 测试覆盖安全 receipt 和补偿事件序列。
- 根仓跨项目测试覆盖 `AgentRuntime -> OMO CompensationStarted/WorkflowRecovered` 和既有
  `safe receipt -> EvidenceRecorded -> WorkflowVerified` 链。
- 文档、ADR、workflow verify/closeout 和主仓治理门禁通过。
