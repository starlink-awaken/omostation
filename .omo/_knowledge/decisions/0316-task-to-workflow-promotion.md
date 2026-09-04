---
id: ADR-0316
title: 知识行动任务到 Workflow Mesh 请求的晋升边界
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../docs/STRATEGY-3YEAR-PANORAMA.md
  - 0300-adaptive-digital-officer-decision-loop.md
---

# ADR-0316: 知识行动任务到 Workflow Mesh 请求的晋升边界

## 背景

J2 已经能够把带知识引用的结果创建为 OMO planned task，但如果下一步直接复用 worker dispatch，
任务会跳过场景绑定、证据计划和 Workflow Mesh 的可审计请求阶段。当前外部业务场景仍未达到正式
激活门槛，因此需要先把“想让工作流继续推进”做成可观察、可重复、不可越权的产品动作。

## 决策

1. 新增 OMO `request_workflow_from_task()` broker，只接受 planned 且带 `knowledge_refs` 的任务。
2. 请求必须携带完整 `scene_binding`、工作流名称/版本、operation level 和证据计划；超过任务允许
   的 operation level 直接 fail-closed。
3. broker 只追加一条 `WorkflowRequested` 事件，并追加同一 `workflow_run_id` 的
   `knowledge-action/v1` `workflow_requested` 回执；不创建 admission grant、不启动 worker、不调用
   外部 provider。
4. 高风险任务或 L2/L3 操作保留 `approval_required`，请求可以被记录，但只有既有人工审批和
   `admit_workflow()` 链路才能继续准入。
5. 请求身份由任务、工作流、场景、证据计划和操作级别确定，重复请求返回 `deduplicated`，不得
   重复产生 Mesh 事件或行动回执。
6. Cockpit 与知识到行动页面提供人工触发入口，产品状态明确显示“请求已记录”和“未启动 worker”，
   不把请求状态伪装成执行成功。

## 结果

这一步把 J2 的漏斗从 `task_created` 延伸到可审计的 `workflow_requested`，为后续真实场景中的
approval -> admission -> dispatch、结果回执和离线评测提供稳定锚点；同时保持外部连接和副作用关闭。
下一阶段仍需在有真实场景、指标、责任人与样本后，才允许从请求进入正式 admission。

## 验收

- OMO 测试覆盖成功请求、审批阻断、缺少知识引用、超额 operation level 和幂等回放；
- Cockpit API 能返回请求态并明确 `worker_launch=false`、`external_side_effects=disabled`；
- UI 能在任务创建后人工发起请求，并为该请求记录知识行动回执；
- Workflow Mesh 快照停留在 `planned`，没有 `WorkflowAdmitted` 或 worker 事件。
