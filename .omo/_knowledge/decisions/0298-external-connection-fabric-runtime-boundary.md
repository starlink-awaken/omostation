---
id: ADR-0298
title: 外部连接织层运行时边界与 Workflow Mesh 回执
status: ACCEPTED
type: decision
owner: architecture-governance
created: 2026-08-02
last_updated: 2026-08-02
lifecycle: spec
related:
  - ../../standards/external-connection-fabric.md
  - ../../_truth/registry/external-connection-fabric.yaml
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
---

# ADR-0298 外部连接织层运行时边界与 Workflow Mesh 回执

## Context

ADR-0297 建立了 External Connection Fabric 的职责和 descriptor 合同，但仅有注册表与入口声明
仍不足以支撑真实业务旅程。没有执行边界时，连接器发现、权限准入、能力选择和外部调用容易重新
散落在各个子项目，且结果无法进入 Workflow Mesh 的证据链。

## Decision

1. Agora 在 `agora.external_connections` 提供无状态中心的目录、entry point 发现、生命周期检查、
   场景准入、能力路由和调用 receipt；不直接导入 Kairon/Iris 或具体供应商。
2. 外部提供方统一通过 `external.resources` entry point 暴露 `external_descriptor()`；单个提供方
   失败必须隔离并返回错误记录，不能阻断其他提供方发现。
3. 激活必须同时满足场景、旅程、结果指标、数据范围、操作者、匹配的 `permission_ref`、健康、
   来源、期限/审查时间和回滚方案。缺任一项即拒绝或保持冻结。
4. 路由结果必须包含资源身份、候选决策因子、策略摘要和 trace；无候选时返回显式
   `unavailable`，不能使用默认资源或 fake success。
5. 调用只能返回不含外部原文和凭据的 `ConnectionReceipt`。receipt 通过
   `evidence_payload()` 接入 OMO `EvidenceRecorded`，Workflow Mesh 仍是运行证据真相。
6. `proposal_only` 资源只允许生成提案，不得执行生产副作用；后续演进仍遵循
   `proposal -> shadow -> approval -> canary -> rollback`。

## Consequences

外部连接可以通过插件声明动态扩展，而无需修改 Agora 路由代码；不同来源可以按场景切换并留下
可解释回执。代价是每个新连接必须提供权限引用、健康和可撤销元数据，且真实调用方必须负责将
receipt 追加到同一条 Workflow Mesh 事件链。

## Confirmation

- Agora `tests/test_external_connections.py` 覆盖 descriptor、准入、路由、不可用、proposal-only、
  receipt 和动态 entry point 发现。
- Iris 注册表测试覆盖 `external.resources` 与 `iris.connectors` 的声明一致性。
- 根仓 `tests/test_external_connection_runtime.py` 验证 receipt payload 可被 OMO Workflow Mesh
  作为 `EvidenceRecorded` 接受。
