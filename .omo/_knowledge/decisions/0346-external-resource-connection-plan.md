---
id: ADR-0346
title: External Resource Connection Plan
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: Workflow Mesh external connection fabric
date: 2026-08-03
---

# ADR-0346: External Resource Connection Plan

## Context

`external-resource-directory/v1` 已经能够告诉产品和运营“有哪些能力、当前是否可用、下一步是什么”，但还不能把下一步转成可执行的接入准备清单。若每个连接器自行解释 `capabilities`，知识源、工具、模型和渠道会重新形成各自的接入语义，最终迫使 Agora 路由代码承担 provider 特例。

动态扩展需要把“发现”与“可触达”分开：系统可以自动发现和探活，但必须明确还缺哪些场景、权限、评测、回滚和人工证据，才能进入受治理的连接路径。

## Decision

在 catalog 到 Cockpit 的只读投影链上增加 `external-resource-connection-plan/v1`。根仓
`bin/ssot/external-resource-catalog.py::build_external_resource_connection_plan` 从
`external-resource-directory/v1` 确定性生成每个资源的：

- `next_step`：探活、评估、沙盒、场景/权限复核、激活复核或路由评估；
- `status`：当前只允许 `blocked` 或 `ready_for_review`，不表示已准入；
- `blockers`：缺失的健康、场景、策略、权限、结果指标或人工处置证据；
- `required_inputs`：下一阶段允许收集的最小输入；
- `owner_ref`、`permission_ref` 和目录 digest，用于把计划回接到责任人与观察快照。

该计划是证据收集和人工/治理复核队列，不是安装器、插件市场、激活器或 WorkflowRun 创建器。它固定：

- `activation=forbidden`；
- `provider_invocation=false`；
- `workflow_run_creation=false`；
- `admission_mutation=false`。

OMO 仍是 admission、运行状态和证据的唯一真相；Agora 仍负责发现和路由；Runtime/AetherForge
仍负责实际执行；Cockpit 只消费计划和后续观察投影。连接器无需新增路由特例，只需遵守 descriptor、health probe、permission、rollback 和真实场景合同。

## Consequences

正向结果：

1. 外部知识、数据、方法、工具、模型和渠道共享一套“从发现到可触达”的产品语言。
2. 没有真实场景时，系统能够明确告诉操作者缺什么，而不是把静态发现误报成可用能力。
3. 计划由目录 digest 派生，可重放、可比较，不会创建第二份资源状态真相。
4. 后续 Cockpit UI 或调度器可以直接消费计划，不需要理解每种 provider 的内部实现。

约束：

- 本 ADR 不引入外部写操作、不增加第二套工作流引擎、不自动批准连接器。
- `ready_for_review` 只表示计划字段完整且可以进入人工/治理复核，不能表示 active 或 admitted。
- 真实消费者、结果指标、权限和回滚证据仍由 Scene Card、OMO admission、Workflow Mesh receipt 和 outcome feedback 提供。

## Verification

- `tests/test_external_resource_catalog.py` 覆盖连接计划的稳定排序、证据阻塞项、摘要和 digest。
- CLI 边界测试确保 `--directory` 与 `--connection-plan`、`--observe` 不可混用。
