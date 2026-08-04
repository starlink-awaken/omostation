---
name: memory-recall
description: >
  Unified memory recall/write routing for omostation agents (Memory OS).
  Use when searching knowledge, recalling user preferences, writing episodic
  memory, forgetting facts, or deciding between kos / gbrain / cards / inbox.
  Prefer bos://memory/mos/* once Phase 1 is live; until then use documented fallbacks.
---

# Memory Recall — Agent 默认记忆入口

> **SSOT**: ADR-0372 · `.omo/_truth/registry/memory-os.yaml` · `docs/architecture/memory-os.md`

## 何时使用

- 用户/任务需要「找笔记、ADR、卡片、偏好、实体关系」
- 需要决定 call 哪个 BOS URI
- 写跨会话偏好或 episodic 痕迹
- 明确**不要**把代码结构检索和笔记检索混在一起

## 默认策略（按 Phase）

### Phase 1+（当前默认）

```text
召回:  bos://memory/mos/recall   { query, scope?, intent? }
写入:  bos://memory/mos/write    { type, content|content_ref, confidence? }
状态:  bos://memory/mos/status
遗忘:  bos://memory/mos/forget   { memory_id, reason? }  # Phase 2
CLI:   uv run --directory projects/kairon --package mos python -m mos {write,recall,forget,status}
巩固:  bos://memory/mos/consolidate  (Phase 3+，异步)
Mem0:  MOS_MEM0=1 启用 shadow 双写（默认 off，无 Qdrant）
```

经 Agora：`resolve_bos_uri` / cockpit bos 代理。  
**禁止** L3 代码硬 import kairon/gbrain 内核。

### 回退（MOS/Agora 不可用时）

按 **intent** 选后端（与 registry `intent_routes` 对齐）：

| Intent | 主路径 | 备注 |
|--------|--------|------|
| `file_note` / 找文档 ADR | `bos://memory/kos/search` 或 mcp-server-kos | 机构知识 |
| `general` | kos + gbrain（MOS 内 RRF；回退时顺序扇出） | |
| `preference_self` | mos write semantic → theta facts | Mem0 仍默认 off |
| `entity_relation` | gbrain graph / traverse | |
| `card_ops` | cockpit `/api/knowledge/*`；事件 `memory/events/card_updated` | brain URI 仍 dual-accept |
| `code_structure` | codebase-memory / GitNexus | **禁止**与笔记混搜 |
| `task_debt` | omo / governance | **不是** memory |

卡片写入仍用 cockpit knowledge PUT（emit 已迁 memory 域，indexer dual-accept）。

## Intent 快速分类提示

- 「XX 在哪个文档/ADR」→ `file_note`
- 「我上次说的偏好/约束」→ `preference_self`
- 「A 和 B 什么关系 / 谁投资了」→ `entity_relation`
- 「谁调用了这个函数」→ `code_structure`
- 「有什么开放任务/债务」→ `task_debt`

## 红线

1. 不把 Mem0/MemTheta 半成品当已生产闭环（见 adapter audit）
2. 不把检索成功当成任务完成（ADR-0315）
3. 不把密钥/高 PII 正文写入 OMO log
4. 不引入第二套 consolidate 引擎（用 gbrain dream）
5. `bos://brain/events/*` 为过渡债；新代码优先 `bos://memory/events/*`（迁移完成后）

## 相关

- 架构: `docs/architecture/memory-os.md`
- 审计: `docs/operations/memory-os-adapter-audit.md`
- 附着: `.agents/skills/external-agent-attach/SKILL.md`
- 发现: `.agents/skills/bos-service-discovery/SKILL.md`
