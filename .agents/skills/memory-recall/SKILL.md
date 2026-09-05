---
name: memory-recall
description: >
  Unified memory recall/write routing for omostation agents (Memory OS).
  Use when searching knowledge, recalling user preferences, writing episodic
  memory, forgetting facts, or deciding between kos / gbrain / cards / inbox.
  Prefer bos://memory/mos/* (phase1+ live; phase10 as_of + optional live backends).

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Memory Recall — Agent 默认记忆入口

> **SSOT**: ADR-0372 · `.omo/_truth/registry/memory-os.yaml` (phase10) · `docs/architecture/memory-os.md`  
> **运维**: `.omo/standards/memory-os-ops.md` · `make memory-os-check`  
> **史诗复盘**: `docs/operations/memory-os-epic-retro.md`

## 何时使用

- 用户/任务需要「找笔记、ADR、卡片、偏好、实体关系」
- 需要决定 call 哪个 BOS URI
- 写跨会话偏好或 episodic 痕迹
- 明确**不要**把代码结构检索和笔记检索混在一起

## 默认策略（Phase 1–10 当前）

```text
召回:  bos://memory/mos/recall   { query, scope?, intent?, as_of? }
写入:  bos://memory/mos/write    { type, content|content_ref, confidence?, subject?, predicate?, object? }
状态:  bos://memory/mos/status
遗忘:  bos://memory/mos/forget   { memory_id, reason? }
巩固:  bos://memory/mos/consolidate  { dry_run?, phases? }
引用:  bos://memory/mos/knowledge-ref  { query, intent? }

CLI:   cockpit memory {status,recall,write,forget,consolidate,knowledge-ref}
       cockpit memory                          # 无子命令 = 状态摘要 + 用法帮助
       cockpit memory recall -h                # 含 --as-of 说明
Agora: resolve/invoke 上列 BOS URI（stdio + --with neo4j；MCP lifespan 注入 NEO4J_*/MOS_*）
HTTP:  /api/memory/* · 面板 /memory
```

### 常用 CLI

```bash
source bin/memory-os-env.sh
cockpit memory status --json
cockpit memory recall "偏好" --json
cockpit memory recall "Alice" --intent temporal_fact --as-of 2021-06-01T00:00:00Z --json
cockpit memory write --type semantic --content "…" --json
cockpit bos resolve bos://memory/mos/status
```

### 开关（默认安全）

| 变量 | 默认 | 含义 |
|------|------|------|
| `NEO4J_URI` | example 填 bolt://localhost:7687 | 图写/读门控 |
| `MOS_RBAC` | 1 | 策略表 RBAC |
| `MOS_TEMPORAL` | 1 | TemporalShadow |
| `MOS_LIVE_KOS` | 0 | 1 → HTTP KOS 检索 |
| `MOS_LIVE_GBRAIN` | 0 | 1 → gbrain search 子进程 |
| `MOS_LIVE_GBRAIN_WRITE` | 0 | 1 → write 时 best-effort gbrain put |

图库：`bash bin/memory-os-neo4j-up.sh` · 模板：`docs/operations/memory-os.env.example`

经 Agora：`resolve_bos_uri` / BOS invoke / `cockpit bos`。  
**禁止** L3 代码硬 import kairon/gbrain 内核。

### 回退（MOS/Agora 不可用时）

按 **intent** 选后端（与 registry `intent_routes` 对齐）：

| Intent | 主路径 | 备注 |
|--------|--------|------|
| `file_note` / 找文档 ADR | `bos://memory/kos/search` 或 mcp-server-kos | 机构知识 |
| `general` | kos + gbrain（MOS 内 RRF；回退时顺序扇出） | |
| `preference_self` | mos write semantic → theta facts | Mem0 仍默认 off |
| `entity_relation` / `temporal_fact` | mos recall → neo4j FACT（需 NEO4J_URI）+ temporal；可传 `as_of` | |
| `card_ops` | cockpit `/api/knowledge/*`；事件 `memory/events/card_updated` | brain URI 仍 dual-accept |
| `code_structure` | codebase-memory / GitNexus | **禁止**与笔记混搜 |
| `task_debt` | omo / governance | **不是** memory |

## Intent 快速分类提示

- 「XX 在哪个文档/ADR」→ `file_note`
- 「我上次说的偏好/约束」→ `preference_self`
- 「A 和 B 什么关系 / 谁投资了」→ `entity_relation`
- 「2021 年时的关系」→ `temporal_fact` + `as_of`
- 「谁调用了这个函数」→ `code_structure`
- 「有什么开放任务/债务」→ `task_debt`

## 红线

1. 不把 Mem0/MemTheta/graphiti-core 半成品当已生产闭环（见 adapter audit / status.adapters）
2. 不把检索成功当成任务完成（ADR-0315）
3. 不把密钥/高 PII 正文写入 OMO log
4. 不引入第二套 consolidate 引擎（用 gbrain dream）
5. 新代码优先 `bos://memory/events/*`（brain 域仅 dual-accept 遗留）
6. Live 后端失败必须 degrade，不得拖垮 write/recall 主路径

## 相关

- 架构: `docs/architecture/memory-os.md`
- 本机 Neo4j: `docs/operations/memory-os-neo4j-local.md`
- 史诗复盘: `docs/operations/memory-os-epic-retro.md`
- 审计: `docs/operations/memory-os-adapter-audit.md`
- 附着: `.agents/skills/external-agent-attach/SKILL.md`
- 发现: `.agents/skills/bos-service-discovery/SKILL.md`
