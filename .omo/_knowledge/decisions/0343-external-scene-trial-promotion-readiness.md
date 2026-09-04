---
id: ADR-0343
title: External scene trial promotion readiness projection
status: archived
type: adr
date: 2026-08-03
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
decision: "以 append-only 试运行、评审、WorkflowRun、外部 receipt 和 outcome-feedback 重建只读晋升就绪度；ready 只表示可以提交人工晋升提案。"
---

# ADR-0343: 外部场景试运行晋升就绪度投影

## 背景

Phase 47 和 Phase 48 已经把外部场景试运行与人工评审持久化，但仍缺少一个统一的可审计判定：当前场景是否真的有
真实消费者、WorkflowRun、外部调用回执和结果消费反馈。若没有这个判定，人工评审容易被误读为业务验证完成。

## 决策

新增 `external-scene-trial-promotion-readiness/v1` 只读投影，由 OMO
`projects/omo/src/omo/omo_external_scene_readiness.py` 重建，检查：

- 试运行记录存在，且最新评审动作是 `continue`；
- 存在同一 `scene_binding` 的 WorkflowRun，并处于 `succeeded`、`verified`、`merged` 或 `closed`；
- 该运行拥有 `external-connection-receipt/v1` 的 `EvidenceRecorded`；
- 该运行拥有正向 `outcome-feedback/v1`，且不是 `rejected`。

OMO CLI 和 Cockpit API/UI 只读取投影，返回 `empty`、`blocked`、`ready` 或 `unavailable` 及阻断码。所有入口固定
`activation=forbidden`、`provider_invocation=false`、`workflow_run_creation=forbidden`、`admission_mutation=forbidden`。

## 边界

`ready` 不是自动晋升、准入、激活或上线，只是允许人提交下一步 proposal。投影不读取 provider 原文、不保存凭据、不
创建运行、不改变 Workflow Mesh 状态。没有真实业务消费者时，系统必须保持 blocked，而不是用合成数据伪造 ready。

## 验证

- OMO 外部场景就绪度及相关 receipt/feedback 测试通过；
- Cockpit `/api/external-resources/scene-trials/readiness` 只读边界测试通过；
- Cockpit UI 展示阻断项并保持 proposal-only 语义；
- registry、standard 和 Workflow Mesh implementation 文档已同步。
