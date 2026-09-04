---
id: ADR-0336
title: Cockpit UI External Resource Pack Preflight Surface
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0335-external-resource-pack-review-surface.md
  - 0334-external-resource-pack-conformance.md
---

# ADR-0336: Cockpit UI External Resource Pack Preflight Surface

## Context

Phase42 已提供 Cockpit API，但人工使用仍需要手工构造 JSON 请求。外部能力动态扩展要成为可日常使用的
工作流，需要在已有外部能力目录中提供输入、反馈和可解释状态，同时保持当前没有真实业务场景时的冻结边界。

## Decision

在现有 External Resource Catalog 页面中增加 `ExternalResourcePackPreflightPanel`，通过既有 API client
调用 `/api/external-resources/packs/preflight`。UI 提供受控 JSON manifest 输入和默认沙盒示例，展示
`blocked`、`proposal_only`、`ready_for_catalog_preview` 三态、reason codes 和执行禁止策略。

UI 不提供安装、探活、调用、准入或激活动作；任何结果都显示 `activation: forbidden`，并明确安装、provider
加载、health probe、OMO 写入和业务调用均被禁止。这样 UI 是人工合同评审面，不是插件市场或运行时控制面。

## Consequences

- 连接器开发者和业务负责人可以在同一工作台完成 manifest 初检，不需要直接操作终端或隐式绕过边界。
- 结果仍只是静态预检，真实 provider 发现、健康、场景准入和执行证据继续由既有层负责。
- UI 将 JSON 作为受控输入，后续若扩展结构化表单也必须复用同一 API 和 schema，不能新增第二种状态语义。

## Verification

```bash
cd projects/cockpit-ui
bun run test:unit -- src/components/__tests__/ExternalResourcePackPreflightPanel.test.tsx src/components/__tests__/ExternalResourceCatalogView.test.tsx
bun run build
```
