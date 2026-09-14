---
id: ADR-0314
title: Workflow Mesh explicit outcome feedback contract
status: ACCEPTED
date: 2026-08-02
last-reviewed: 2026-08-02
owner: engineering-team
lifecycle: spec
related:
  - ../../../docs/operations/outcome-feedback.md
  - ../../../docs/operations/workflow-mesh-operations.md
  - ../../../projects/omo/src/omo/outcome_feedback.py
  - ../../../projects/cockpit-ui/src/components/WorkflowMeshOperationsView.tsx
type: ssot
---

# ADR-0314: Workflow Mesh 显式结果消费反馈契约

## Context

Phase 20 已经能聚合 Workflow Mesh 的执行、验证、交付和复盘队列，但 `closed`、`verified`、
`PRMerged` 和 `EvidenceRecorded` 都不能证明业务结果被消费。继续把 `consumption` 固定为
`not_observed` 会让产品无法形成 J1 的真实运营闭环；直接新增运行态事件则会把业务价值观察
混进执行生命周期，并引入第二套状态机。

## Decision

1. 以独立的 `outcome-feedback/v1` append-only 日志记录结果消费回执，WorkflowRun 状态机保持不变。
2. OMO 独占持久化、场景绑定校验、结果资格校验、幂等和隐私字段校验；Cockpit 只提供 API 和
   人工表单，不持有第二份结果数据库。
3. 只有 `succeeded/verified/merged/closed` 且完整 `scene_binding` 一致的运行可以提交反馈；
   `scene_id`、`journey_id`、`outcome_metric` 不允许被调用方改写。
4. 反馈允许 `reviewed/adopted/submitted/dispatched/cited/rejected`，备注原文只生成
   `sha256:` 摘要，凭据和原始载荷递归拒绝。
5. 运营投影将反馈明确映射为 `not_observed`、`observed` 或 `rejected`；消费状态不触发外部
   资源激活、任务派发、WorkflowRun 状态迁移或模型训练。
6. 外部知识、数据、方法、工具和渠道继续遵守 Scene Card、admission、receipt、权限和回滚
   门禁；本 ADR 不改变“无真实业务场景则 proposal-only/sandbox”的策略。

## Consequences

- J1 有了可操作的结果消费反馈入口，能区分工程完成和价值消费。
- 反馈可以通过稳定 idempotency key 安全重试，并可被运营投影按场景聚合。
- 真实业务系统接入仍需要新的受治理 adapter 和责任人，不会因为 Cockpit 表单存在而自动激活。
- 反馈质量、消费者真实性和业务价值仍需要后续真实标注集和人工抽样评估，不能把提交数量当作价值。

## Verification

- OMO outcome feedback tests: PASS
- OMO operations/eval/workflow mesh regression: PASS
- Cockpit outcome feedback API tests: PASS
- cockpit-ui outcome feedback component tests: PASS
- cockpit-ui production build: PASS
