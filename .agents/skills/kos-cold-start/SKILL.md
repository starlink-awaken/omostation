---
name: kos-cold-start
title: KOS Cold Start
description: KOS 冷启动协议 - 加载 BRIEF.md/ADR/entities 上下文对齐
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - new session
  - context compaction
  - architecture realignment
---

# kos-cold-start — KOS 知识冷启动

> 将 CLAUDE.md Step A KOS Cold-Start 3 步查询转为可执行 skill

## 触发条件

- 新 session 启动
- 上下文压缩后恢复
- 需要重新对齐架构理解

## 执行步骤

### Step 1: 查询当前决策与目标

```bash
mcp-server-kos::query_custom_sql(sql="SELECT doc_id, title, canonical_path FROM documents WHERE canonical_path LIKE '%BRIEF.md%' LIMIT 1")
```

读取结果的 BRIEF.md 路径，获取活跃技术债务和 X3 指标。

### Step 2: 遍历 ADR 决策

```bash
mcp-server-kos::search_kos(query="ADR-012")
```

重点关注 ADR-0124 (S1 retrospective) 和 ADR-0125 (S2 retrospective)。

### Step 3: 识别领域 Schema

```bash
mcp-server-kos::list_entities(limit=50)
```

## 输出

- 活跃 BET 列表
- 未关闭的技术债务
- 当前架构约束

## 相关

- CLAUDE.md §1 — Startup Protocol
- `.omo/_knowledge/decisions/` — ADR 索引
- `docs/plans/3y-bet-ledger.yaml` — BET 台账
