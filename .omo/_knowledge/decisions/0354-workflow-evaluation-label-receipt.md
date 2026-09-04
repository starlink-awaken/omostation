---
id: ADR-0354
title: Workflow Mesh evaluation label receipt and dual-review release queue
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: workflow mesh evaluation and cockpit operations
date: 2026-08-03
---

# ADR-0354: Workflow Mesh 人工评测标签回执与双人放行队列

## Context

Phase 59 已经能够从 Workflow Mesh 事件、外部 receipt 和 outcome feedback 派生评测样本准备度，Phase 60 又补齐了外部资源
目录的受治理刷新。但 `ready` 只说明运行事实完整，仍没有独立的人工作判断事实、双人一致性和冲突 adjudication，因此不能直接
生成真实评测 manifest，更不能把运行投影当作训练标签。

## Decision

1. OMO 持久化 `workflow-mesh-evaluation-label/v1` append-only receipt。标签只接受有限枚举的阶段、结论、选择质量、结果质量、
   置信度、证据引用、复核人引用和摘要哈希；原文、prompt、模型输出、自由文本备注、凭据和未知字段必须拒绝。
2. Cockpit 提供 `POST /api/workflow-mesh/evaluation-label`，统一交给 OMO broker 落盘。接口不创建 WorkflowRun、不启动 worker、不
   调用 provider，固定输出 `activation=forbidden`、`provider_invocation=false`、`workflow_run_creation=false` 和
   `worker_launch=false`。
3. OMO 派生 `workflow-mesh-evaluation-label-queue/v1`，以 evaluation_id 关联 readiness 与标签。样本只有两名主标注一致，或完成
   adjudication 且最终结论为 `accept`，才计入 `label_ready_count`。
4. 标签回执、外部执行回执和结果消费反馈保持三类独立事实；未来 manifest 只能通过可审计 join 生成，不能修改历史回执或覆盖原始 OCR。

## Boundary

- 当前阶段不生成训练集、不训练预测模型、不改变资源路由或 Workflow Mesh 策略。
- `ready`、`consensus` 和 `label_ready` 是不同状态，前者不代表人工确认，后者也不代表模型生产放行。
- `note_digest` 只能是摘要哈希，UI 不提供原文输入；证据引用必须可定位但不携带敏感载荷。
- 真实低风险消费者、双人标注和脱敏 manifest 形成后，才允许进入规则/人工基线、离线评测和 shadow 预测阶段。

## Verification

- OMO label receipt and queue tests: 9 passed;
- Cockpit Workflow Mesh API tests: 12 passed;
- Cockpit UI full baseline: 167 passed, 1 skipped; Vite build and preview HTTP 200 passed;
- root workflow verification and CI are required before closeout.
