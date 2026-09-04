---
id: ADR-0348
title: External Resource Connection Plan UI
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: cockpit-ui external connection fabric
date: 2026-08-03
---

# ADR-0348: 外部能力连接计划 UI 产品化

## Context

Phase 54 已提供 Cockpit connection-plan API，但只有 API 仍不足以支持日常判断。用户需要在现有外部能力目录中看到“下一步是什么、谁负责、缺什么证据”，而不应再增加一个平行的插件或连接器管理入口。

## Decision

在既有 `/external-resources` 页面增加只读“连接计划”区，消费
`external-resource-connection-plan/v1`。页面展示资源数、可复核数、阻塞数，以及每项资源的 `next_step`、状态、责任人、权限引用、阻塞原因和 `required_inputs`。

前端对 response schema 做防御性校验：旧后端或接口返回 catalog projection 时，不渲染连接计划项，也不把旧数据解释成新能力。接口不可用时提供明确状态和独立重试入口。

## Boundary

- UI 不写 OMO，不创建 WorkflowRun，不调用 provider，不改变 admission 或 activation。
- `available` 只表示“可进入人工/治理复核”，不是 admitted/active。
- `attention` 只表示存在证据或健康缺口，不是业务失败。
- 产品入口继续收敛在外部能力目录，不新增顶级导航。

## Verification

- `ExternalResourceCatalogView` Vitest: 7 passed。
- ESLint passed。
- `bun run build` passed。
- schema guard 覆盖旧 catalog projection 兼容场景。
