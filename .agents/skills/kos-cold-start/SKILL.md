---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-26
type: skill
name: kos-cold-start
description: "KOS 冷启动 skill：会话启动时从 KOS 加载状态/检索知识/实体，对齐历史决策（v1.1 实测校准）"
title: KOS Cold Start
version: "1.1.0"
triggers: 
---


# kos-cold-start — KOS 知识冷启动（v1.1 实测校准版）

> v1.1（2026-09-26，BET-Y2Q4-T3-02 端到端验证）：修正工具名与真实 API 的偏差，
> 补齐今日可用的 kos-cli 路径，如实记录索引覆盖缺口。

## 触发条件

- 新 session 启动
- 上下文压缩后恢复
- 需要重新对齐架构理解

## 现状与边界（2026-09-26 实测，勿虚报）

| 项 | 实测状态 |
|---|---|
| KOS 索引 | `data/kos/kos-index.sqlite`：12,553 documents + 63 entities，活跃更新 |
| `kos-mcp` 服务端 | **已实现**：`projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py`（`FastMCP("kos-mcp")`），工具面 = `search_knowledge` / `get_knowledge` / `get_system_status` / `list_domains` / `get_entity` / `cross_domain_sync` |
| `kos-mcp` 客户端挂载 | **未挂载**（workspace 无任何 MCP 配置引用） |
| 旧文档工具名勘误 | v1.0 引用的 `query_custom_sql` / `search_kos` / `list_entities` 与真实 API **不符**，已修正 |
| 覆盖缺口 | 索引语料以个人 Documents 为主；workspace 治理语料（`.omo/_knowledge` 455 ADR / 550 retro / 37 pattern）**未摄入**——治理知识冷启动需先摄入（见提案） |

## 执行步骤（kos-cli 路径，今日可用）

### Step 1: 系统状态

```bash
python3 projects/knowledge/kairon/packages/kos/kos-cli.py status
```

读取 documents/domains 计数，确认索引活性。

### Step 2: 跨域检索

```bash
python3 projects/knowledge/kairon/packages/kos/kos-cli.py search "<主题关键词>"
```

跨域全文检索（jieba 分词，OR 匹配）。注意：当前命中以个人语料为主；
workspace ADR 检索需待治理语料摄入后可用（0 命中如实记录，D1）。

### Step 3: LLM-ready 上下文

```bash
python3 projects/knowledge/kairon/packages/kos/kos-cli.py context "<主题>"
```

输出带 budget 控制的 JSON 上下文（task/knowledge 分节），可直接注入会话。

### 可选: 实体样本

```bash
sqlite3 data/kos/kos-index.sqlite \
  "SELECT entity_id, label, entity_type FROM kos_entities LIMIT 50;"
```

## 挂载后路径（待 `kos-mcp` 注册进客户端 MCP 配置）

挂载后上述三步等价替换为 MCP 工具：`get_system_status` / `search_knowledge` /
`get_entity`（工具名以 `fastmcp_app.py` 为准）。挂载与摄入提案见
`docs/reports/kos-reuse-loop-verification-2026-09-26.md`。

## 输出

- 索引活性计数（documents/domains）
- 检索命中列表（如实记录 0 命中，D1）
- LLM-ready 上下文 JSON
- 活跃 BET 列表与未关闭债务 → 以 BRIEF.md / `bet-ledger.py status` 为权威源

## 相关

- CLAUDE.md §1 — Startup Protocol
- `.omo/_knowledge/decisions/` — ADR 索引（本地目录权威源）
- `docs/plans/3y-bet-ledger.yaml` — BET 台账
- `.omo/_knowledge/retros/BET-Y2Q4-T3-02.md` — 本次验证 retro
