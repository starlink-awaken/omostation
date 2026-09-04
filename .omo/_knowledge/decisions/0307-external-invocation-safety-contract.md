---
id: ADR-0307
title: Workflow Mesh 外部调用安全契约
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../.omo/standards/external-connection-fabric.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../projects/agora/src/agora/external_connections.py
  - ./0303-workflow-mesh-external-receipt-broker.md
---

# ADR-0307: Workflow Mesh 外部调用安全契约

## 背景

External Connection Fabric 支持通过 entry point 动态发现知识、数据、方法、工具、模型和渠道。
动态扩展的风险不只在于 provider 是否可用，还在于 descriptor 可能把凭据或原始载荷藏进
`metadata`、`health`、`provenance`，以及 provider 异常可能把实现细节直接带入 Mesh receipt。
这会扩大跨 Agora、OMO、Cockpit 和 Runtime 的数据泄漏面，也让下游无法稳定判断超时、权限失败和
后端故障。

## 决策

1. `ExternalResourceDescriptor.from_mapping()` 对 descriptor 的所有递归字段执行敏感字段和原始
   内容拒绝。除已有的 token、密码和私钥外，`api_key`、`api_secret`、`credential`、`dsn`、
   `connection_string`、`authorization`、`cookie` 以及原始输入/输出字段均不得进入 descriptor。
2. `ExternalConnectionCatalog.invoke()` 将 provider 异常映射为稳定的 `EXTERNAL_*` 错误码：
   `EXTERNAL_TIMEOUT`、`EXTERNAL_BACKEND_UNAVAILABLE`、`EXTERNAL_PERMISSION_DENIED`、
   `EXTERNAL_INVALID_RESPONSE` 和 `EXTERNAL_PROVIDER_FAILURE`。
3. 异常类型、异常消息和堆栈只允许留在调用方受控日志；receipt、OMO `EvidenceRecorded`、目录
   投影和 Cockpit 不得携带异常原文。连接层的 `no_route` 和 `invoker_unavailable` 保留为确定性
   前置失败码。
4. 本 ADR 只收紧外部连接的输入和回执合同，不新增副作用执行器、不改变 Runtime effect journal
   或补偿所有权，也不自动激活任何真实 provider。

## 不变量

- descriptor 任何嵌套层级出现禁止字段时，注册和动态发现都 fail-closed。
- provider 失败回执的 `error_code` 只能来自稳定错误码集合，不能是 Python 异常类名或异常文本。
- `proposal_only` 资源仍不得调用 handler。
- 外部调用失败不生成成功证据；失败、不可用和提案继续由既有 Workflow Mesh/OMO 边界表达。
- 真实业务场景、Scene Card、权限引用和 provider-specific 补偿仍是后续激活的独立前置条件。

## 验收

- Agora 外部连接专项测试 26/26 通过，覆盖常见凭据、原始载荷、稳定错误码和 proposal-only 边界。
- 根仓外部资源目录及 Agora receipt 到 Runtime/Workflow Mesh 的跨边界回归通过 8/8。
- Agora Ruff 检查通过，外部连接标准、Workflow Mesh 实施文档和 ADR 索引同步更新。
- 本阶段不声称真实外部 provider、业务 Scene Card、生产数据或补偿流程已经激活；这些仍需真实
  业务/运维证据才能进入 J4 真实激活门。
