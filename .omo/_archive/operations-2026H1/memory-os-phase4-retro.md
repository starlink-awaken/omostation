---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-04
related:
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ./memory-os-phase3-retro.md
title: Memory OS Phase 4 — 复盘
type: doc
---

# Memory OS Phase 4 — 复盘

## 交付

| 项 | 结果 |
|----|------|
| TemporalShadowAdapter | Graphiti 形态 bi-temporal 边；无 Neo4j；`MOS_TEMPORAL` 默认 on |
| 时效写读 | subject/predicate/object + valid_from/to；失效后 current-state 不可见 |
| Scope ACL | recall `scope.principal_id` 过滤 |
| knowledge_ref | ADR-0315 引用元数据（query_hash + hit_ids），raw 无正文 |
| CLI | write 三元组 flags；`knowledge-ref` 子命令 |
| Tests | 33 pytest |

## 迭代

- 中文「有效期」匹配去掉 `\b`（ASCII 词界对 CJK 失效）
- 失效只保证 temporal backend；theta 文本仍可搜（诚实双层）

## 明确未做

- 真 Graphiti/Neo4j 生产图
- cockpit UI 面板
- multi-agent 细粒度 ACL 表
