---
id: ADR-0337
title: External Resource Pack Catalog Preview Semantics
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/external-connection-fabric.md
  - 0334-external-resource-pack-conformance.md
  - 0336-external-resource-pack-ui-surface.md
---

# ADR-0337: External Resource Pack Catalog Preview Semantics

## Context

Phase 41-43 已经能够在根仓、Cockpit API 和 UI 中完成外部扩展包静态预检，但
`ready_for_catalog_preview` 如果只返回 descriptor，人工仍无法区分“可以形成目录形态”和“已经被
provider 探活”。尤其 descriptor 自带的 health 字段不能直接成为运行时健康事实。

## Decision

在 `external-resource-pack-check/v1` projection 中增加可选的
`external-resource-pack-catalog-preview/v1`。该投影只从已校验 descriptor 提取安全元数据，并固定：

- `mode=read_only_pack_preview`、`activation=forbidden`；
- `availability=unobserved`、`health.status=unobserved`；
- 来源为 `external-resource-pack-manifest`；
- 不包含 provider 响应、原文、凭据或业务结果。

普通资源的下一步是只读 catalog discovery 和健康探针；proposal-only 资源的下一步是 proposal/evaluation，
不能进入生产路由候选。Cockpit 可以展示该预览，但不得由此写 OMO、加载 provider、执行探针、创建
WorkflowRun 或形成 admission。

## Consequences

外部扩展的过渡状态变得可解释：人可以先审阅资源形态和权限边界，同时保持静态声明、运行时观测、
业务准入和执行结果四层事实隔离。代价是任何真实可用性判断都必须等待 catalog 探活，不能仅凭 manifest
提前得到“健康”结论。

## Verification

```bash
uv run --with pyyaml --with pytest python -m pytest -q tests/test_external_resource_pack.py
cd projects/cockpit && PYTHONPATH="src:../omo/src" uv run --no-project --with pytest --with fastapi --with httpx --with pydantic --with pyyaml python -m pytest -q src/cockpit/tests/test_api_external_resources.py
cd projects/cockpit-ui && bun run test:unit -- src/components/__tests__/ExternalResourcePackPreflightPanel.test.tsx
```
