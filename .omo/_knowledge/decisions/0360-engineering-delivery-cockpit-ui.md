---
id: ADR-0360
title: Engineering Delivery Cockpit UI 收件箱与人工复核边界
status: ACCEPTED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last_updated: 2026-08-04
---

# ADR-0360: Engineering Delivery Cockpit UI 收件箱与人工复核边界

## 背景

Phase 66 已提供工程交付复核的 L3 API，但责任人仍需要直接调用接口才能查看队列和提交决策。Phase 67 需要提供正式 UI，
同时避免浏览器端读取 `.omo`、复制状态机或把人工决策误解为 WorkflowRun/业务策略的自动变更。

## 决策

1. Cockpit UI 新增独立的工程交付复核入口，队列只消费 `engineering-delivery-review-queue/v1` 投影。
2. UI 以摘要、收件箱和详情表单承接场景；详情只显示后端投影中的结构化元数据、场景绑定和证据计数，不读取工程原文。
3. 表单只允许提交 `workflow_run_id`、`actor_ref`、`delivery_id`、`decision`、`reviewed_at` 和 `evidence_refs`；至少一条证据引用是前端交互闸门，后端仍是最终校验者。
4. UI 固定展示并遵守 `workflow_state_mutation=false`、`provider_invocation=false`、`automatic_promotion=false`，不在本地维护第二套 review 状态。
5. 队列不可用、复核提交失败或数据不完整时 fail-closed；成功提交后通过查询失效刷新真实投影，不用本地乐观状态掩盖持久化结果。

## 影响

- 工程责任人获得可扫描、可选择、可提交的日常复核工作台。
- L3 只负责呈现和窄 envelope 传输，OMO 继续拥有字段安全、状态约束、幂等和 append-only 持久化。
- 该页面只完成工程交付元数据的人机闭环，不替代真实业务样本、双人标注、adjudication 或预测模型放行条件。

## 验证

```bash
cd projects/cockpit-ui
bun run vitest run src/components/__tests__/EngineeringDeliveryReviewView.test.tsx
bun run build
bunx eslint src/api/endpoints.ts src/api/hooks.ts src/routes.tsx src/components/EngineeringDeliveryReviewView.tsx src/components/__tests__/EngineeringDeliveryReviewView.test.tsx
```
