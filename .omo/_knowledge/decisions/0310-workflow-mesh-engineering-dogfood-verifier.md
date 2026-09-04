---
id: ADR-0310
title: Workflow Mesh 工程 dogfood 端到端验收与场景绑定传递
status: ACCEPTED
lifecycle: spec
owner: engineering-team
date: 2026-08-02
last_updated: 2026-08-02
related:
  - docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - docs/scene-cards/engineering-delivery-dogfood.yaml
  - .omo/_knowledge/decisions/0309-cockpit-home-operating-focus.md
---

# ADR-0310: Workflow Mesh 工程 dogfood 端到端验收与场景绑定传递

## 背景

Workflow Mesh、OMO Task Lifecycle 和 worker dispatch 已分别具备创建、准入、派发、执行、证据与
关闭能力，但仅有分层测试时，无法证明任务状态与运行态会在同一次执行中收敛。与此同时，Mesh
支持 `scene_binding`，准入桥却没有把调用方的业务场景上下文传递到 `WorkflowRequested`，存在在真实
派发前丢失业务旅程身份的风险。

## 决策

1. `admit_workflow` 接受可选 `scene_binding`，并只在 `WorkflowRequested` 上写入它；后续事件继续由
   Mesh 投影校验绑定不变。
2. `dispatch_admitted_workflow` 通过 admission options 透传该绑定，返回包同时暴露安全的绑定摘要，
   供调用方构造 worker packet 和产品投影。
3. OMO 保留 `Workflow Mesh` 事件日志为运行事实来源，任务 YAML 仍由 task lifecycle broker 管理；
   两者通过 `task_id`、`workflow_run_id`、执行日志和证据引用关联，不合并成第二套状态机。
4. 用临时 OMO 工作区建立可重复的工程 dogfood 测试，覆盖：
   `create_planned_task -> promote_task_to_active -> dispatch_admitted_workflow -> worker ACK ->
   execution record -> complete_task -> EvidenceRecorded -> WorkflowVerified -> WorkflowClosed`。
   测试不得调用外部 provider，不得依赖真实业务私有资料，也不得把 proposal-only 场景提升为激活。

## 不变量

- 缺少完整 `scene_id`、`journey_id`、`outcome_metric` 时，不能伪造产品场景绑定。
- Mesh 运行必须先获得 admission grant，worker 生命周期必须匹配同一 `admission_id` 和 `step_run_id`。
- 任务 done 必须有物理 evidence path；Mesh verified 必须有 `EvidenceRecorded`。
- `WorkflowClosed` 之前不得把 `succeeded` 或 `verified` 当作最终结案。

## 验收

- `projects/omo/tests/test_workflow_mesh_task_dogfood.py` 在隔离临时工作区跑通完整链路。
- 断言任务最终为 `done`，执行审计 exit code 为 0，Mesh 最终为 `closed`，并保留同一
  `scene_binding`、worker 上下文和 evidence projection。
- 既有 `test_workflow_dispatch.py` 回归通过，说明无场景绑定的兼容调用保持不变。

## 后续

这只是 M1 工程真实性门槛，不代表外部知识、数据、渠道或业务自动化已激活。真实业务场景仍需先
满足 Scene Card、权限、责任人、结果指标、脱敏样本和 receipt 证据，再进入 External Connection
Fabric 的 proposal-only/sandbox/active 晋级链。
