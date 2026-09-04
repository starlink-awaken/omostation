---
id: ADR-0328
title: 外部资源目录 freshness、失效与回退边界
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0319-external-resource-observation-surfaces.md
  - 0326-external-activation-preflight.md
---

# ADR-0328: 外部资源目录 freshness、失效与回退边界

## 背景

External Connection Fabric 已经能够发现资源、探测 health、记录目录观察并运行只读 preflight，
但目录观察本身没有独立的有效期。只要资源仍带有 `available`，一份过期快照就可能被误读成当前
能力，尤其会影响动态发现的知识源、数据源、方法包、工具、模型和渠道。

## 决策

1. `external-resource-catalog/v1` 增加 `catalog_ttl_seconds`，默认 3600 秒；它只约束目录观察
   的有效期，不替代 `health_ttl_seconds` 或 descriptor 的 `expires_at/review_at`。
2. activation preflight 在进入 `ready_for_admission_preview` 前必须检查 `catalog_freshness`。
   `fresh` 才能继续；`stale`、`unknown`、缺失观察时间、非法时间或非法 TTL 一律 `blocked`。
3. freshness 结果只保留观察时间、年龄、TTL 和 reason code，不读取原文、不调用 provider、不写
   OMO、不创建 WorkflowRun，也不改变 Agora admission。
4. 目录刷新采用“刷新观察 -> 重新 preflight -> 重新 admission”的顺序。过期结论、旧 grant、旧
   route 或旧 receipt 不得复用为新的激活许可。
5. Cockpit 在没有可用目录时继续返回显式 unavailable projection，并声明同一 TTL；不得用空列表
   或旧快照伪装为 fresh。

## 验证

- 根仓外部目录与 preflight：14 passed。
- Agora 外部连接：16 passed。
- Cockpit 外部资源 API：8 passed。
- 根仓、Agora、Cockpit 变更文件 Ruff 和 `git diff --check` 通过。
