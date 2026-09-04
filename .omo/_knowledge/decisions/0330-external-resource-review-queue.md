---
id: ADR-0330
title: Cockpit 外部资源只读人工复核队列
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0329-external-resource-change-review.md
  - 0326-external-activation-preflight.md
---

# ADR-0330: Cockpit 外部资源只读人工复核队列

## 背景

Phase 36 已经在 Agora diff 和 OMO 观察中标出 `manual_review`，但只有机器可读的摘要，业务和
运营人员还不能在 Cockpit 里直接看到“哪些资源需要看、为什么需要看、发生了哪些安全变化”。
直接增加批准按钮会把产品入口误变成第二套准入状态机；直接实时发现又会绕过 OMO 观察的新鲜度和
审计边界。

## 决策

1. Cockpit 增加 `GET /api/external-resources/review-queue`，只读取 OMO 最新
   `external-resource-observation/v1`，不回退到 Agora 动态发现，不调用 provider，不写 OMO。
2. 接口输出 `external-resource-review-queue/v1`，条目只保留资源 ID、变化类型、变化字段、
   `manual_review`、稳定风险码和白名单安全快照；原文、凭据和未知字段不得进入响应。
3. 队列语义固定为 `latest_observation_delta`：`attention` 代表当前观测包含人工复核变化，
   `clear` 代表当前观测没有人工复核变化，`empty` 代表尚无观测，`unavailable` 代表观测源或
   契约不可用。接口不记录已读、审批、驳回或自动关闭状态。
4. `operational_observation` 变化只进入计数和风险码摘要，不生成复核条目；它不能被误报成描述符
   或准入变化。
5. 任何正式激活仍须沿用 Scene Card、external-activation-preflight、OMO admission、
   WorkflowRun、receipt 和 evidence 链。复核队列本身永远保持 `activation=forbidden`。

## 产品处理链

```text
review queue -> 人工核查 -> Scene Card/preflight -> OMO admission
             -> 受控执行 -> receipt/evidence -> 结果反馈
```

队列是人工判断入口，不是业务任务队列，也不是资源授权列表。没有真实业务场景时，系统可以停在
`empty`、`clear` 或 `attention`，不应为了填充队列而制造外部连接调用。

## 验证

- Cockpit 外部资源 API：11 passed。
- Cockpit 变更文件 Ruff：通过。
- 场景覆盖：最新 OMO 观测、无观测、非法观测、无动态发现回退和 activation fail-closed。
