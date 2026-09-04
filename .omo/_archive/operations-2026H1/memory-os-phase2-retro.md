---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-04
related:
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ./memory-os-phase1-retro.md
  - ../architecture/memory-os.md
title: Memory OS Phase 2 — 复盘
type: doc
---

# Memory OS Phase 2 — 复盘

## 交付

| 项 | 结果 |
|----|------|
| `mos.forget` | raw `memory.forget` + theta hide + mem0 forget |
| Mem0 shadow | `MOS_MEM0=1` 本地适配，无 Qdrant/mem0ai 依赖 |
| Eval harness v0 | 15 cases（intent / preference / forget） |
| BOS | `bos://memory/mos/forget` stdio |
| Tests | 24 pytest green |

## 迭代

- 遗忘后 recall 必须过滤 `forgotten` / `forgotten_ids`，不能只删事件。
- Mem0 默认 off；on 时 preference_self 路由才挂 `mem0` backend。

## 仍未做（P3+）

- consolidate → gbrain dream 编排
- 真·OMO broker / 真·gbrain 网络端口
- 50+ 生产评测集、Graphiti、ACL、UI
