---
id: ADR-0411
title: "算力路由双 Owner 收敛决策 — AetherForge 单一所有权"
status: archived
lifecycle: spec
owner: governance-team
created: 2026-08-16
last-reviewed: 2026-08-16
related:
  - ./0409-documents-capability-route-owner-convergence.md
type: ssot
---

# ADR-0411: 算力路由双 Owner 收敛决策 — AetherForge 单一所有权

## 判定

**算力路由单一 owner = aetherforge**，弃用孤立的 `gac-mesh-router`。

## 实测证据 (2026-08-16)

| 维度 | aetherforge | gac-mesh-router |
|---|---|---|
| BOS 服务登记 | ✅ `bos://memory/aetherforge/mcp-server` + `forge_*` tools | ❌ 无 BOS 登记 |
| 主仓引用 | ✅ 9 处（AGENTS.md / registry / ci-architecture 等） | ❌ 零引用（仅自身文件） |
| governance-checks 接线 | ✅ 有 | ❌ 未接线 |
| 活跃度 | 活跃 | 无近期提交证据 |
| 端口 | 7422/7431 体系 | 7437 孤立端口 |

## 决策理由

1. `aetherforge` 已承担实际算力网关职责（BOS 服务 + `forge_*` FastMCP tools + 活跃开发），是生态实际消费方。
2. `gac-mesh-router` 主仓零引用、未接 BOS/governance，是孤立实现。
3. 收敛到 `aetherforge` 符合能力市场方向（BOS 是唯一能力入口，mesh 路由应作为 `aetherforge` 内部能力而非独立二进制）。

## 落地与后果

1. `gac-mesh-router` 状态置为 `deprecated`（`docs/project-registry.yaml` status: deprecated）。
2. 所有本地与集群算力统一经 AetherForge + omlxc 数据面路由。
