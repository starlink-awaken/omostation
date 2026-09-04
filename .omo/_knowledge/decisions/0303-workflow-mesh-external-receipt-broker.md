---
id: ADR-0303
title: Workflow Mesh 外部 receipt 回写 broker
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/external-connection-fabric.md
  - ../../_knowledge/decisions/0298-external-connection-fabric-runtime-boundary.md
---

# ADR-0303: Workflow Mesh 外部 receipt 回写 broker

## 背景

External Connection Fabric 已能生成不含原文和凭据的 `ConnectionReceipt`，但过去的集成测试由
调用方手工构造 `EvidenceRecorded`，没有统一校验、幂等身份和可查询投影。这样容易在真实
连接器接入时丢失决策因素，或把失败结果错误地写成成功。

## 决策

1. OMO 提供 `record_external_receipt()` 作为唯一的 receipt-to-evidence broker；CLI
   `omo worker external-receipt` 只是同一 broker 的受控适配器。
2. broker 不导入 Agora、不调用 provider、不读取凭据；执行方只提交最小 receipt，OMO 只持久化
   receipt 摘要、哈希、来源、策略、决策因素和结果状态。
3. 只有 `succeeded` 和 `degraded` receipt 可以追加 `EvidenceRecorded`；`failed`、`unavailable`
   和 `proposed` 必须由对应 Workflow Mesh 事件表达，禁止用 EvidenceRecorded 伪造成功。
4. 事件身份由 `workflow_run_id + receipt_id` 稳定派生，重试必须返回同一 append-only 事件；同一
   receipt 在内容或上下文冲突时 fail-closed。
5. OMO 投影白名单保留 `evidence_schema`、`receipt_id`、`resource_id`、`trace_id`、结果、时间、
   provenance、policy 和 decision factors；禁止 provider 原文、模型输出和 secret 字段进入事件或投影。

## 不变量

- receipt broker 不替代 admission、执行、补偿或失败状态机。
- `proposal_only` 永远不产生生产副作用，也不能通过 broker 获得成功证据。
- receipt 记录成功不等于业务完成；只有 Workflow Mesh 的验证和 Outcome 证据才能推进业务闭环。
- 外部调用的真实回执必须与同一 `workflow_run_id/trace_id` 关联，并可由事件日志重建。

## 验收

- Agora receipt 经 broker 后可在 OMO snapshot 查询 provenance、策略、结果和 decision factors。
- 相同 receipt 重试不增加事件数量，事件 ID 和 payload 保持稳定。
- 失败、不可用、提案和含原文/凭据的输入均被拒绝或隔离。
- CLI smoke 和根仓跨模块测试覆盖执行方 receipt -> OMO EvidenceRecorded -> WorkflowVerified。
