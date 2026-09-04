---
id: ADR-0317
title: WorkflowRequested 到受治理 admission 的晋升边界
status: ACCEPTED
date: 2026-08-03
owner: engineering-team
scope: Workflow Mesh / OMO / Cockpit
lifecycle: spec
last_updated: 2026-08-03
---

# ADR-0317: WorkflowRequested 到受治理 admission 的晋升边界

## 背景

Phase 23 已把知识行动任务提升为 `WorkflowRequested`，但请求态不能直接被当作已获准执行。
旧的 admission broker 面向“从任务直接 admission”的兼容入口，会同时创建请求事件；它不能安全
承接已有的请求事件，否则会重复写入请求或违反 Mesh 状态机。

## 决策

1. 新增 `preview_requested_workflow()`，只读取已有请求、任务、审批、能力健康和预算事实，输出
   `eligible` 或带原因的 `blocked`，不得追加事件、改变任务状态或启动 worker。
2. 新增 `admit_requested_workflow()`，只接受已有 `WorkflowRequested` 且状态为 `planned` 的运行。
   它要求任务已经进入 `active`，审批、能力健康和预算门禁全部通过后只追加一个
   `WorkflowAdmitted`，并复用请求的 `scene_binding`。
3. apply 不允许隐式创建请求，不允许调用 worker，不允许触达外部连接；返回中固定携带
   `external_side_effects=disabled` 和 `worker_launch=false`。
4. 对已 admission 的相同运行返回幂等的 `deduplicated`；场景绑定冲突、请求缺失、任务不在 active
   或任一门禁失败均 fail-closed。
5. `workflow-request-eval/v1` 纳入所有请求态样本，记录当前状态、审批要求、准入结果、事件来源和
   场景绑定，不记录 prompt、原文、模型输出、凭据或 provider 载荷。

## 影响

- J2 的真实漏斗从 `task_created -> workflow_requested -> preview -> admission -> dispatch` 可观测，
  请求未准入不再被丢出评测集。
- OMO 继续拥有状态机和准入裁决；Cockpit 只提供显式 preview/apply API 与真实状态展示。
- 真实外部场景仍须另行通过 Scene Card、权限、健康、期限、回滚和 receipt 门禁；本 ADR 不激活
  任何外部连接。

## 验收

- OMO admission、dispatch、request evaluation 测试通过。
- Cockpit API 对 preview/apply 只返回受治理结果，且不启动 worker。
- cockpit-ui 显示请求等待真实门禁，并在运营投影中呈现请求/待准入计数。
