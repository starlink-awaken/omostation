---
title: External Connection Fabric Standard
status: active
type: standard
owner: architecture-governance
last-reviewed: 2026-08-02
related:
  - ../_truth/registry/external-connection-fabric.yaml
  - ../../ARCHITECTURE.md
  - ../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
---

# External Connection Fabric 标准

## 1. 目的

外部知识、数据、资料、资源、方法、理论、渠道和工具不再以散乱的临时接入方式进入系统。
所有连接先成为可描述、可发现、可评估、可准入、可撤销的资源，再由现有的 OMO、Agora、
Workflow Mesh、Kairon、AetherForge 和 Cockpit 协同消费。

本标准不新增顶层项目，也不拥有任务、权限、凭据、持久知识或运行状态真相。

## 2. Descriptor 合同

每个连接必须提供 `external-resource/v1` descriptor，至少包含身份、类型、提供方、协议、
能力、数据分级、来源、生命周期、健康、所有者和版本。凭据只允许使用 `credential_ref`，
禁止落盘 token、密码、私钥或未经治理的私人原文。

资源类型统一为：`knowledge_source`、`data_source`、`resource_provider`、`method_pack`、
`tool_capability`、`channel`、`model_provider`。

## 3. 生命周期与准入

连接必须经过 `discovered -> sandbox -> admitted -> active`，运行中可进入 `degraded` 或
`quarantined`，最终进入 `retired`。激活前必须具备场景、旅程、结果指标、数据范围、操作人、
健康探针、来源证据、审查时间和回滚方案。

没有真实消费者、结果指标、责任人或权限边界时，资源保持冻结，不得因为“已经能连通”而激活。

## 4. 触达模式

优先使用 `live_query` 和 `live_invoke`，仅在有边界时使用 `ttl_snapshot` 或
`governed_snapshot`。事件订阅和消息投递必须带最小化载荷、去重、免打扰、升级和投递回执。
方法和模型默认 `proposal_only`，必须经过评测、影子运行和人工批准才能产生生产副作用。

## 5. 路由与证据

Agora 根据相关性、可信度、新鲜度、权限、可用性、成本和延迟选择能力。任何选择都必须留下
候选决策因素、策略摘要和 `trace_id`。连接不可用、权限过期、来源过时或预算超限时，必须
返回显式 `unavailable/degraded`，不得使用默认值伪装成功。

每次发现、准入、调用、投递和退役都回写 `workflow-mesh/v1` 证据，至少包含资源身份、时间、
结果状态和来源引用。外部结果只有在同一条证据链中完成 provenance 校验后，才能进入派生知识。

## 6. 受控进化

连接优化、方法改写、路由调整和模型切换只能生成提案。提案按
`proposal -> shadow -> approval -> canary -> rollback` 推进，并且必须能比较结果质量、成本、
延迟、权限失败率和人工接管率。

验证命令：

```bash
uv run --with pyyaml --with pytest python -m pytest -q tests/test_external_connection_fabric_registry.py
```
