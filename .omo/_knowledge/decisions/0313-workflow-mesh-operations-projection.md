---
id: ADR-0313
title: Workflow Mesh operations projection and explicit consumption boundary
status: ACCEPTED
date: 2026-08-02
last_updated: 2026-08-02
owner: engineering-team
lifecycle: spec
related:
  - ../../../docs/operations/workflow-mesh-operations.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../projects/omo/src/omo/workflow_eval.py
  - ../../../projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py
---

# ADR-0313: Workflow Mesh 运营投影与显式消费边界

## Context

Phase 19 已让 Cockpit Delivery Journey 在没有真实 WorkflowRun 时保持诚实，但 J1 连续运营
还缺少跨运行的复盘入口。现有事件和证据足以计算执行、验证、恢复和交付里程碑；它们不足以
证明业务人员已经消费结果、完成回写或产生价值。若把关闭、验证或证据存在当作业务消费，
会重新制造声明与实效之间的鸿沟。

## Decision

1. OMO 在 `workflow_eval.py` 中提供 `workflow-mesh-operations/v1` 事件派生快照，作为运营
   指标和复盘队列的唯一计算位置。
2. Cockpit 只读暴露 `/api/workflow-mesh/operations`，不创建自己的状态机、任务库或指标库；
   OMO 日志不可读时返回明确 `unavailable`，不返回默认成功。
3. 运营快照同时保留里程碑事实与历史故障事实：恢复后的运行仍计入故障和恢复计数。
4. 运营投影将场景绑定作为显式归因；没有绑定的运行进入 `_unbound`，不得从分支、文件、PR
   或 worktree 推断业务场景。
5. `consumption` 当前固定表达 `not_observed`，直到真实消费者、结果回写、权限和责任人
   明确后，才设计独立反馈契约；不在本阶段改动核心状态机或新增第二事实源。

## Consequences

- J1 可以按真实事件观察完成率、验证率、恢复率、关闭率和复盘队列，而不是按声明数统计。
- 产品可以明确告诉操作者“完成了什么”和“还不知道什么”，为后续真实场景激活提供基线。
- 外部连接、知识资源和智能策略仍需通过 Scene Card、admission、receipt 和人工消费回执
  进入正式业务闭环。
- 结果消费反馈是下一阶段的独立产品契约，不会被当前运营投影偷偷推断。

## Verification

- OMO operations projection targeted tests: PASS
- Cockpit operations API targeted tests: PASS
- Workflow Mesh event state machine unchanged
