---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-04
related:
  - ./memory-os-phase5-retro.md
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/_truth/registry/memory-rbac.yaml
title: Memory OS Phase 6 — 复盘
type: doc
---

# Memory OS Phase 6 — 复盘

## 交付

| 项 | 结果 |
|----|------|
| Neo4j production writer | `mos.neo4j_writer.Neo4jFactWriter` — `NEO4J_URI` 门控；Cypher UPSERT/INVALIDATE；FakeDriver 单测 |
| Graphiti bridge | 状态面报告 `neo4j_uri_set` + production_path；无 URI 时仍 TemporalShadow |
| 策略表 RBAC | `.omo/_truth/registry/memory-rbac.yaml` + `mos.rbac`；service/CLI/HTTP 强制（`MOS_RBAC=0` 可关） |
| Cockpit 面板 | `/memory` HTML + `/api/memory/*` 注入 `X-Mos-Role` / `X-Agent-Profile` |
| 文档 lifecycle | phase1–5 retro + adapter-audit → `history`（过 doc-governance enum） |

## 诚实边界

- **默认环境无 Neo4j**：未设 `NEO4J_URI` 时不写图库，仅 shadow temporal（不声称已连生产图）
- **graphiti-core 可选**：`MOS_GRAPHITI=1` 且包已装才标记 bridge；生产 FACT 写路径走 Neo4j Cypher，不强制 graphiti-core
- **RBAC 表级非行级**：角色→动作矩阵，非 per-memory ACL 替换（细 ACL 仍是 principal/agent/scene）

## 验证（合入后复盘）

| 检查 | 结果 |
|------|------|
| mos pytest | **43 passed**（含 `test_phase6_neo4j_rbac`） |
| cockpit `test_api_memory` | **2 passed**（header 403 + MEMORY_DASHBOARD_HTML） |
| doc-governance | **PASS**（lifecycle=history；warning budget 恢复） |
| evidence-gate | **PASS**（bos-registry live=156 同步） |
| gac-gate / phase-gate | **PASS**（branch protection 必过项） |
| PR #959 | **MERGED** `fbc820a43` squash 2026-08-04T13:29:45Z |
| workflow closeout | `<run-id>` ok |

## 教训

1. **lifecycle enum 硬约束**：`retrospective`/`audit` 不在允许集，会冲 warning budget 变 error；复盘文档统一 `history`。
2. **子模块 guard 看 `.subtrees/*`**：cockpit 推 main 后需 FF `.subtrees/cockpit`，否则 root commit 被 submodule-guard 拒绝。
3. **诚实生产路径**：Neo4j 只在 `NEO4J_URI` 时写；未配置时 status 明确 `neo4j_configured=false`，不宣称 Graphiti 生产就绪。
