---
id: ADR-0351
title: Task Center Workflow request projection and admission navigation
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: cockpit task center and workflow mesh operations
date: 2026-08-03
---

# ADR-0351: 任务中心 Workflow 请求投影与准入触达

## Context

Phase 57 已能从任务中心创建 `WorkflowRequested`，但请求成功后任务详情仍只显示场景绑定，用户必须手工跳转到
Workflow Mesh 运营页并重新输入运行 ID，导致业务任务、运行事实和准入动作脱节。

## Decision

Cockpit 从 OMO append-only Workflow Mesh 事件派生只读 `workflow_request` 投影，按任务关联最新的
`WorkflowRequested`，再读取对应运行快照，提供：

- `workflow_run_id`、workflow name/version 和当前运行状态；
- request、approval、admission 三类状态；
- 安全的三元场景绑定和有限证据计划；
- 最小化的下一步动作提示。

Task Center 在任务详情展示该投影，并提供进入既有 Workflow Mesh 准入工作台的导航。请求成功后主动刷新任务查询。

## Boundary

- 投影不复制 Workflow Mesh 账本，不写入 Cockpit 自有状态；
- 不暴露原始 Scene Card 输入、provider 内容、凭据、任意路径或未审计结果；
- Task Center 不执行 admission、不计算能力健康、不修改审批、不启动 worker；
- Admission Preview、审批、预算、准入和 dispatch 仍由 OMO/Cockpit 既有 broker 分层负责；
- 没有真实 WorkflowRequested 事件时，投影为空，不用静态任务字段伪造运行状态。

## Verification

- Cockpit task API targeted tests pass, including event-derived safe projection and existing admission routes.
- Cockpit UI build passes.
- Workflow Mesh operations UI tests pass.
- Task Center ESLint passes.
