---
id: ADR-0350
title: Task Center scene-bound Workflow request
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: cockpit task center and workflow mesh promotion
date: 2026-08-03
---

# ADR-0350: 任务中心的场景化 Workflow 请求

## Context

Phase 56 已将 ready Scene Card 承接为 OMO planned task，但任务中心仍只展示通用任务操作。业务人员需要再次手工
拼接 `workflow_name`、场景绑定和证据计划，容易把技术任务与业务场景脱钩，也容易误把请求动作当成执行结果。

## Decision

任务列表和详情只读投影安全的 `scene_binding` 三元组。对于 pending 的场景任务，Task Center 提供 Workflow 请求表单，
调用现有 `request-workflow` API，并固定透传 `workflow_version=v1`、actor 引用和显式证据计划。请求成功后展示
`workflow_run_id/request_state`，并保留“未启动 worker”的边界说明。

## Boundary

- 只允许拥有完整场景绑定的任务显示场景化 Workflow 请求入口。
- 该动作只追加 `WorkflowRequested`，不执行 admission、审批、provider 调用、worker 派发或业务写入。
- Task Center 不维护 Workflow 状态副本；后续状态以 OMO/Workflow Mesh 运营投影为准。
- 原始 Scene Card 目标、输入契约、结果载荷和凭据不随任务列表投影暴露。

## Verification

- Cockpit 任务场景绑定投影测试通过；全套任务 API 中保留的 5 个失败均属于独立 workspace OMO 兼容漂移，见会话验证记录。
- Cockpit UI build 通过。
- Scene Card 与外部连接回归测试 9/9 通过。
- Task Center ESLint 通过。
