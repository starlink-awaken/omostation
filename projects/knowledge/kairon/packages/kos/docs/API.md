---
title: API
type: doc
---

# KOS API 参考

> 版本: v2.0 | 日期: 2026-07-08

---

## CLI 命令

### 搜索命令

#### `kos search` — 混合检索

```bash
kos search <query> [options]

Options:
  -m, --mode {keyword,semantic,graph,hybrid}  检索模式 (默认: hybrid)
  -l, --limit <N>                              最大结果数 (默认: 10)
  --domains <list>                             域过滤 (逗号分隔)
  --zone <zone>                                单域过滤
  --kind <kind>                                文档类型过滤
  --context-mode {concise,balanced,detailed}   上下文模式
  --no-cache                                   跳过缓存
  -f, --format {table,md,json}                 输出格式

Examples:
  kos search "数据治理"
  kos search "数据治理" --mode semantic --limit 5
  kos search "报告" --domains gongwen --format json
```

#### `kos suggest` — 搜索建议

```bash
kos suggest <prefix> [--limit <N>]

Examples:
  kos suggest "数字"
  kos suggest "报告" --limit 5
```

#### `kos related` — 相关搜索

```bash
kos related <query> [--limit <N>]

Examples:
  kos related "数字化平台"
```

#### `kos context` — 上下文构建

```bash
kos context <query> [options]

Options:
  -m, --mode {concise,balanced,detailed}  上下文模式
  -p, --persona <role>                    角色/身份
  --max-tokens <N>                         Token 预算
  --prompt                                输出为 LLM prompt

Examples:
  kos context "数据治理" --mode detailed
  kos context "架构设计" --persona "架构师" --prompt
```

### 索引管理

#### `kos history` — 搜索历史

```bash
kos history {list|add|clear|popular}

Examples:
  kos history list
  kos history add --query "新查询"
  kos history clear
  kos history popular
```

#### `kos memory` — 记忆管理

```bash
kos memory {history|popular|stats|clear}

Examples:
  kos memory stats
  kos memory popular
```

#### `kos index` — 索引管理

```bash
kos index [options]

Options:
  --incremental    增量索引 (仅变更文件)
  --watch          实时监控文件变更
  --domain <zone>  单域索引
  --no-embed       跳过向量索引
```

### 监控告警

#### `kos monitor` — 系统监控

```bash
kos monitor {health|quality|performance|full} [--notify]

Examples:
  kos monitor health
  kos monitor full
  kos monitor quality --notify
```

#### `kos evolve` — 本体演化

```bash
kos evolve {evolve|stats|recommend}

Examples:
  kos evolve evolve     # 运行演化 (去重 + 关系推导)
  kos evolve stats      # 本体统计
  kos evolve recommend  # 改进建议
```

### 多模态处理

#### `kos multimodal` — 处理媒体文件

```bash
kos multimodal <path> [options]

Options:
  --zone <zone>        目标域 (默认: multimodal)
  --recursive          递归处理目录
  --formats            显示支持的格式

Examples:
  kos multimodal ./image.png
  kos multimodal ./media/ --recursive --zone my-media
```

### 缓存管理

#### `kos cache` — 缓存管理

```bash
kos cache {stats|clear|benchmark}

Examples:
  kos cache stats
  kos cache clear
  kos cache benchmark
```

### 知识订阅

#### `kos bridge gbrain` — gbrain 桥接

```bash
kos bridge gbrain {export|import|status} [--limit <N>]

Examples:
  kos bridge gbrain export --limit 100
  kos bridge gbrain import --limit 50
  kos bridge gbrain status
```

### Minerva 集成

#### `kos-minerva` — 深度研究

```bash
kos-minerva {search|ingest|status|report|research}

Examples:
  kos-minerva search "MoE architecture" --level L2
  kos-minerva research "AI Agent 架构" --max-cost 0.5
  kos-minerva status
```

---

## MCP Tools 参考

### 搜索类

#### `search_knowledge`
```json
{
  "query": "搜索查询",
  "domains": "gongwen,obsidian",
  "limit": 10,
  "match_mode": "OR"
}
```

#### `semantic_search`
```json
{
  "query": "自然语言查询",
  "limit": 10
}
```

#### `hybrid_search`
```json
{
  "query": "搜索查询",
  "limit": 10
}
```

### 上下文类

#### `build_context`
```json
{
  "query": "查询",
  "mode": "balanced",
  "persona": "架构师",
  "max_tokens": 0
}
```

#### `ask_knowledge`
```json
{
  "question": "问题",
  "mode": "balanced"
}
```

#### `verify_claim`
```json
{
  "claim": "要验证的声明"
}
```

### 实体类

#### `get_entity`
```json
{
  "entity_id": "P:xia-mingxing"
}
```

#### `search_entity`
```json
{
  "query": "搜索词",
  "entity_type": "Person",
  "limit": 10
}
```

#### `explore_entity`
```json
{
  "entity_id": "P:xia-mingxing",
  "depth": 2
}
```

#### `get_entity_timeline`
```json
{
  "entity_id": "P:xia-mingxing"
}
```

### 订阅类

#### `subscribe_topic`
```json
{
  "topic": "数字化平台",
  "subscriber_id": "agent-1"
}
```

#### `check_subscription`
```json
{
  "sub_id": "abc123"
}
```

### 维护类

#### `run_indexer`
```json
{
  "incremental": true,
  "domain": "",
  "background": true,
  "confirmed": false
}
```

#### `ontology_rebuild`
```json
{
  "confirmed": false
}
```

### 监控类

#### `get_system_status`
```json
{}

#### `get_stats`
```json
{}

#### `monitor_health`
```json
{}

#### `memory_stats`
```json
{}

### 研究类

#### `research_pipeline`
```json
{
  "question": "研究问题",
  "level": "auto",
  "max_cost": 1.0
}
```

#### `fact_check`
```json
{
  "claim": "事实声明"
}
```

### 集成类

#### `sync_gbrain`
```json
{
  "direction": "both",
  "limit": 100
}
```

---

## REST API (cockpit 代理)

### 搜索
```
GET /api/kos/search?q={query}&mode={mode}&limit={limit}
```

### 建议
```
GET /api/kos/suggest?prefix={prefix}&limit={limit}
```

### 上下文
```
GET /api/kos/context?q={query}&mode={mode}
```

### 验证
```
POST /api/kos/verify
Content-Type: application/json

{"claim": "要验证的声明"}
```

### 统计
```
GET /api/kos/stats
```

### 健康
```
GET /api/kos/health
```

---

## 错误码

| 错误 | 说明 |
|------|------|
| `empty query` | 查询为空 |
| `Index not found` | 向量索引未构建 |
| `No embedding backend` | 无可用 embedding 后端 |
| `Unsupported format` | 不支持的文件格式 |
| `File too large` | 文件超过 500MB |
| `L2 confirmation required` | L2 操作需确认 |
