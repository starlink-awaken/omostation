---
id: ADR-0335
title: Cockpit External Resource Pack Review Surface
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0334-external-resource-pack-conformance.md
  - 0330-external-resource-review-queue.md
---

# ADR-0335: Cockpit External Resource Pack Review Surface

## Context

Phase41 增加了根仓 `external-resource-pack/v1` 静态一致性预检，但只有 CLI 入口，业务负责人和连接器
开发者仍需在终端中拼装 manifest，无法在现有 External Resources 人工入口中看到一致的解释结果。
同时，当前没有真实业务场景，不应因为补一个产品入口而引入插件安装、provider 探活或自动激活。

## Decision

在已有 Cockpit External Resources API 下增加
`POST /api/external-resources/packs/preflight`。接口接收一个 pack manifest，调用根仓静态 checker，
返回 `external-resource-pack-check/v1` projection 及 `blocked`、`proposal_only`、
`ready_for_catalog_preview` 状态。

接口固定声明：

- `activation=forbidden`；
- `persistence=none`；
- `provider_invocation=false`；
- `external_side_effects=disabled`；
- `worker_launch=false`。

接口不加载 entry point、不调用健康探针、不写 OMO、不创建 admission 或 WorkflowRun。无效敏感字段只返回
安全错误摘要，不回显凭据、原文或 provider 输出。

## Boundary

Cockpit 负责人工输入和解释；根仓 checker 负责静态合同；catalog/OMO 负责动态发现和观察；Scene Card/OMO
负责业务准入；Agora/Workflow Mesh 负责路由、执行和 receipt。该 API 不是插件市场，不是连接器安装器，
也不是 activation API。

## Verification

```bash
cd projects/cockpit
PYTHONPATH="src:../omo/src" uv run --no-project --with pytest --with fastapi --with httpx --with pydantic --with pyyaml python -m pytest -q src/cockpit/tests/test_api_external_resources.py
```
