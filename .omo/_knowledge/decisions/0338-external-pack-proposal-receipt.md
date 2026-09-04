---
id: ADR-0338
title: External Resource Pack Proposal Observation Receipt
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/external-connection-fabric.md
  - 0337-external-pack-catalog-preview.md
---

# ADR-0338: External Resource Pack Proposal Observation Receipt

## Context

Phase 41-44 已经能够对外部扩展包做静态合同检查并展示未探活目录预览，但人工评审完成后没有一条
持久、脱敏、可幂等的决策记录。若直接把这一步接到 admission，会把“提交下一阶段”误读为批准；若
完全不落盘，后续 catalog discovery/evaluation 又无法知道为何进入下一步。

## Decision

新增 OMO broker `record_external_resource_pack_proposal()`，以
`external-resource-pack-proposal-observation/v1` 追加记录人工评审回执。Cockpit API 在持久化前重新
运行 pack checker，只接受 `proposal_only` 和 `ready_for_catalog_preview`；blocked pack 保持不持久化。

回执只保留安全摘要、`proposal_id`、`review_action`、actor、可选的 `evidence://` 或
`vault://redacted/` 引用、未探活目录预览和下一阶段。稳定身份使用 `proposal_id + projection_digest`，
相同重试幂等，冲突拒绝。

`submit`、`defer`、`request_changes` 都是人工观察事实，不是批准。broker 不写 Workflow Mesh 状态，
不产生 `EvidenceRecorded`，不创建 admission/WorkflowRun，不加载 provider，不运行健康探针。

## Consequences

动态扩展具备了“预检 -> 人工判断 -> 可追踪下一步”的完整观察链，同时保持连接器、目录、场景准入和
执行证据的所有权边界。代价是 proposal receipt 不能证明 provider 可用、业务价值或生产批准，后续仍需
catalog discovery、Scene Card、OMO admission 和真实 receipt。

## Verification

```bash
cd projects/omo && PYTHONPATH=src uv run --no-project --with pytest --with pyyaml --with pydantic python -m pytest -q tests/test_omo_external_pack.py
cd projects/cockpit && PYTHONPATH="src:../omo/src" uv run --no-project --with pytest --with fastapi --with httpx --with pydantic --with pyyaml python -m pytest -q src/cockpit/tests/test_api_external_resources.py
cd projects/cockpit-ui && bun run test:unit -- src/components/__tests__/ExternalResourcePackPreflightPanel.test.tsx
```
