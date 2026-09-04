---
id: ADR-0318
title: Agora 能力健康作为 Cockpit 准入证据
status: ACCEPTED
date: 2026-08-03
owner: architecture-governance
scope: Workflow Mesh / Cockpit / Agora
lifecycle: spec
last_updated: 2026-08-03
---

# ADR-0318: Agora 能力健康作为 Cockpit 准入证据

- 状态: **ACCEPTED**
- 日期: 2026-08-03
- 范围: Workflow Mesh / Cockpit / Agora

## 背景

Phase 24 已经把 `WorkflowRequested` 接到 OMO 的 admission preview/apply，但调用方仍需
手工提交 `capability_health`。这会使准入证据不可追溯，也让产品界面无法验证真实运行态。
Agora 已有只读 `workflow_capability_health` 投影，能够汇总 agent、节点、服务和 backend 的
能力来源与健康状态。

## 决策

Cockpit 通过内部 `/v1/tools/call` 只读调用 Agora 的 `workflow_capability_health`，新增
`GET /api/workflow-mesh/capability-health` 作为稳定产品边界。响应必须保留 `source`、
`observed_at`、逐能力健康和来源，并显式声明 `external_side_effects=disabled`、
`worker_launch=false`。

Workflow Mesh 运营工作台按以下顺序工作：

```text
required_capabilities -> server-owned health -> read-only preview -> human confirmation -> OMO admission
```

健康不可用或响应缺少 provenance 时 fail-closed；preview 不写状态，admission 只承接已有
请求并继续不启动 worker。外部资源连接和业务写操作不因本 ADR 自动开放。

## 取舍与边界

- Cockpit 负责产品投影和错误语义，Agora 负责能力健康事实，OMO 仍是准入与运行状态真相。
- 当前不引入健康缓存、预测模型或第二套状态机，避免把陈旧快照当成执行授权。
- 后续接入真实外部场景时，必须在同一条链上增加 Scene Card、权限、预算、receipt 和补偿证据。

## 验证

- Cockpit API 覆盖成功投影、Agora 不可用和空能力拒绝。
- cockpit-ui 覆盖健康查询和 Workflow Mesh 运营工作台的安全状态展示。
- `make gac-local-gate`、Cockpit 定向测试和 cockpit-ui build/test 作为交付门禁。
