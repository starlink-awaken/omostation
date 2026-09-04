---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-05
related:
  - ./memory-os-epic-retro.md
  - ./memory-os-neo4j-local.md
  - ../architecture/memory-os.md
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/_truth/registry/memory-os.yaml
title: Memory OS Phase 10 — 能力加深复盘
type: doc
---

# Memory OS Phase 10 — 能力加深复盘

## 交付

| 项 | 结果 |
|----|------|
| Neo4j bi-temporal `as_of` | SEARCH_CYPHER + FakeDriver；CLI/cockpit `--as-of` |
| Live KOS | `MOS_LIVE_KOS=1` → HTTP `KOS_API_URL` |
| Live gbrain | `MOS_LIVE_GBRAIN=1` search；`MOS_LIVE_GBRAIN_WRITE=1` put |
| 文档 / help | architecture §6/§10 · ops · skill · mos README · cockpit `memory` help |
| kairon | `9ac7d761` · 56 mos tests |
| PR | #987 |

## 用法指针

见 `docs/architecture/memory-os.md` §10「操作入口」与 `.omo/standards/memory-os-ops.md` Phase 10。

## 诚实边界

- Live 默认 off；不可用时 degrade 到 fixture，不阻断主路径
- graphiti-core / Mem0 生产闭环仍未宣称
