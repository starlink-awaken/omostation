---
id: ADR-0297
title: 收敛产品真相与外部连接织层
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

# ADR-0297 收敛产品真相与外部连接织层

## Context

平台已经具备入口、治理、执行、知识、算力和证据能力，但产品价值仍需要围绕真实旅程收敛。
其中两个风险最直接：Cockpit 在后端不可用时可能把默认状态误呈现为运行事实；外部知识、数据、
方法、工具、渠道和模型如果继续按项目或脚本分别接入，会形成重复权限、重复路由、不可撤销的
复制和无法解释的智能调用。

## Decision

1. 产品执行统一使用 `scene_id -> journey_id -> intent_id -> workflow_run_id -> evidence_id` 作为可追踪身份链。
2. Cockpit 只展示后端真实状态；没有真实数据时显示 loading、partial 或 unavailable，不生成随机或默认业务数据。
3. 外部能力建立跨项目的 External Connection Fabric，由 ECOS 定义 descriptor，OMO 负责场景准入和证据，Agora 负责发现路由，Kairon 负责源与方法，Runtime 负责执行回执，AetherForge 负责模型与凭据，Cockpit 负责可见性。
4. 连接默认零复制、最小权限、期限化和可撤销；凭据只以引用存在；资源没有真实场景、结果指标或责任人时冻结。
5. 方法、模型、路由和自动化只能先生成 proposal，经过评测、影子运行、批准、灰度和回滚后才能改变生产行为。

## Consequences

正向结果是：产品指标、外部连接和 Workflow Mesh 使用同一条证据链；资源可以动态发现、降级和替换；
智能化扩展不会再额外创造一套任务或知识真相。

代价是：早期连接接入需要 descriptor、场景绑定、健康探针和证据测试；没有真实消费者的连接不会
因为技术可行而进入生产；Cockpit 和 Iris 需要补齐真实态与插件发现实现。

## Confirmation

- `tests/test_external_connection_fabric_registry.py` 验证注册表结构、密钥字段禁入、生命周期闭合和文档指针。
- Cockpit truthfulness test 验证后端不可用时不显示占位任务和指标。
- Iris registry test 验证声明式 connector entry points 与 descriptor 输出。
