---
id: ADR-0352
title: Workflow Mesh result receipt and evaluation readiness projection
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: omo workflow mesh evaluation and cockpit operations
date: 2026-08-03
---

# ADR-0352: Workflow Mesh 结果回执与评测样本准备度投影

## Context

Phase 58 已将任务中心的 Workflow 请求状态和准入入口接通，但准入之后仍缺少一个产品化的结果闭环：外部调用回执需要
由真实执行方产生，业务消费需要显式反馈，评测样本还要区分“有运行记录”和“标签完整”。如果把这些事实散落在 UI
表单或另一套数据表中，系统会产生第二状态机，也无法判断哪些样本真的能支撑模型评测。

## Decision

1. Cockpit 提供 `POST /api/workflow-mesh/external-receipt` 作为受治理录入面，严格将 envelope 与 OMO receipt broker
   分开；只允许 `workflow_run_id`、可选 step/producer 和安全 receipt，未知 envelope 字段直接拒绝。
2. OMO 继续以 append-only Workflow Mesh 事件为事实源，使用既有
   `external-resource-selection-eval/v1` join 结果派生 `workflow-mesh-evaluation-readiness/v1`，不创建第二个评测存储。
3. readiness 明确区分 `ready`、`execution_ready`、`blocked`，阻塞原因至少覆盖运行关联、场景绑定、执行结果、receipt 对齐
   和结果消费反馈；只暴露安全标识、标签、计数和来源，不读写外部原文。
4. Cockpit UI 将 receipt 录入、结果反馈和 readiness 摘要放在同一 Workflow Mesh 运营页，但不调用 provider、不启动 worker、
   不改变 WorkflowRun 状态。

## Boundary

- receipt 录入只记录已经发生的外部操作，不能被解释为外部调用授权或调用成功的替代品；
- `ready` 只表示样本满足当前离线评测准入条件，不表示模型训练、预测或策略自动发布；
- 预测模型、模型注册、在线推理和自动策略晋升仍需独立的真实场景、标注协议、评测门禁和人工审批；
- 外部原文、输入输出载荷、凭据、secret 和任意未审计内容不得跨越 OMO/Cockpit receipt 边界。

## Verification

- OMO workflow evaluation and operations tests: `6 passed`;
- Cockpit Workflow Mesh API tests: `10 passed`;
- Cockpit UI Workflow Mesh operations tests: `4 passed`;
- Cockpit UI TypeScript and ESLint checks pass;
- OMO and Cockpit targeted Ruff checks pass.
