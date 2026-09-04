---
id: ADR-0347
title: External Resource Connection Plan Cockpit Surface
status: archived
type: adr
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-03
type: decision
scope: Cockpit external connection fabric
date: 2026-08-03
---

# ADR-0347: Cockpit 外部能力连接计划只读触达面

## Context

Phase 53 增加了 `external-resource-connection-plan/v1`，但如果它只停留在根仓 CLI，业务负责人仍然无法在日常产品入口看到外部能力为什么不可触达、下一步缺什么证据。把它做成写入页面又会把 Cockpit 误变成准入或运行状态的第二真相。

## Decision

Cockpit 增加 `GET /api/external-resources/connection-plan`，仅消费根仓的 directory/connection-plan 投影。

读取顺序固定为：

1. OMO 最新 `external-resource-observation/v1` 中的 catalog；
2. OMO 观察不存在时，Agora 的显式只读 discovery；
3. 同一根仓 builder 生成 directory，再生成 connection plan。

API 状态只表达产品观察态：`available`、`attention`、`empty`、`unavailable`。它固定返回
`external_side_effects=disabled`、`worker_launch=false`，并且不调用 provider 业务方法、不创建 WorkflowRun、不改变 admission。

## Consequences

- 业务侧能在 Cockpit 看到能力地图之外的证据缺口和责任引用，减少“系统明明发现了但不知道怎么接”的黑盒。
- OMO 仍拥有持久观察、准入、运行和证据；Agora 仍拥有 discovery/routing；Cockpit 只负责呈现。
- connection plan 的 `attention` 不是失败，也不是批准；只有真实消费者、场景绑定、权限、结果指标、receipt 和反馈齐备后，才可进入正式 Workflow Mesh 路径。
- standalone Cockpit 在根仓 builder 不可用时必须显示 `unavailable`，不能伪造空计划或成功连接。

## Verification

- Cockpit connection-plan endpoint tests: 2 passed。
- Cockpit external resource API suite: 22 passed, 1 pre-existing standalone-clone failure。
- Ruff and diff checks passed。
