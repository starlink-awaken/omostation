---
id: ADR-0331
title: Cockpit UI 外部资源只读人工复核队列消费面
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0330-external-resource-review-queue.md
  - 0329-external-resource-change-review.md
---

# ADR-0331: Cockpit UI 外部资源只读人工复核队列消费面

## 背景

Phase 37 已经提供 Cockpit 后端复核队列，但如果 UI 只展示资源目录和候选评估，人工仍然需要
切换工具才能看到 descriptor 变化。与此同时，产品不能因为“有一个复核按钮”就生成第二套审批事实，
也不能在没有观测时使用实时发现填充一个看似可信的队列。

## 决策

1. 在现有“外部能力目录”页面增加复核区，调用 `GET /api/external-resources/review-queue`，不
   新增独立导航、缓存事实库或第二个工作台。
2. UI 只消费 `external-resource-review-queue/v1`，展示 `attention`、`clear`、`empty`、
   `unavailable` 四态，以及待复核计数、运营观察计数、风险码和变化字段。
3. UI 不提供批准、激活、派发、修改生命周期或写入复核状态的动作；`attention` 只代表需要人看，
   `activation=forbidden` 始终可见。
4. 队列失败独立于资源目录失败：复核接口不可用时保留目录观察面，并提供只读重试；不会用目录实时
   fallback 伪造复核结果。
5. 正式处理仍沿用 Scene Card、preflight、OMO admission、WorkflowRun、receipt/evidence，
   UI 只负责把风险信息放到人的工作路径上。

## 验证

- `ExternalResourceCatalogView`：5 passed。
- Vite production build：通过。
- 本次变更文件 ESLint：通过。
- 覆盖 `attention`、`empty`、`unavailable` 和独立重试路径。
