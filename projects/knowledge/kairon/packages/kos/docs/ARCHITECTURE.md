---
title: ARCHITECTURE
type: doc
---

# KOS — Knowledge Operating System Architecture

> 版本: v2.0 | 日期: 2026-07-08

---

## 一、系统定位

KOS (Knowledge Operating System) 是织星生态 eCOS 的 **L2 内核层**知识引擎，
为上层 AI Agent (cockpit/gbrain/Minerva) 提供统一的知识检索、上下文工程和本体推理能力。

```
┌─────────────────────────────────────────────────────────────────┐
│  L4 自我层  ← TELOS / 信念 / 目标                              │
├─────────────────────────────────────────────────────────────────┤
│  L3 入口层 ← cockpit (Web) / MCP Server / CLI                  │
├─────────────────────────────────────────────────────────────────┤
│  L2 内核层 ← KOS (本层) · gbrain · omo · ecos                  │
├─────────────────────────────────────────────────────────────────┤
│  L1 运行时 ← runtime · 健康监控 · KEI                          │
├─────────────────────────────────────────────────────────────────┤
│  L0 协议层 ← MOF · BOS · SSOT                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、核心能力

| 能力 | 说明 | 技术 |
|------|------|------|
| **混合检索** | 关键词 + 语义 + 图谱三路融合 | FTS5 + LanceDB + RRF |
| **上下文工程** | 检索预算控制 + 结果压缩 + token 预算 | 动态 top-k + 摘要 |
| **本体推理** | 实体识别 + 关系推导 + 图谱遍历 | 规则 + 共现 |
| **三级缓存** | L1 内存 + L2 SQLite + L3 冷检索 | LRU + SQLite |
| **增量索引** | 文件变更检测 + 仅变更部分重建 | SHA-256 + mtime |
| **多模态** | 图片/音频/视频 → 可搜索文本 | OCR + ASR + 描述 |

---

## 三、架构设计

### 3.1 模块结构

```
src/kos/
├── __init__.py              # 顶层库入口
├── cli/                     # CLI 层
│   └── __main__.py          # argparse 路由 (主入口)
├── commands/                # 业务命令
├── config.py                # 配置加载
├── db.py                    # SQLite 连接工具 (WAL + 64MB cache)
├── hybrid_search.py         # 统一混合检索引擎
├── context_engine.py        # 上下文工程引擎
├── cache.py                 # 三级缓存管理器
├── search_features.py       # 搜索建议/聚类/相关搜索/历史
├── memory_tier.py           # 三层记忆架构
├── monitoring.py            # 系统监控
├── semantic/                # 向量语义搜索
│   └── __init__.py          # LanceDB + omlx 双后端
├── ontology/                # 本体模块
│   ├── engine.py            # 实体提取/推理/图谱
│   ├── llm_extractor.py     # LLM 辅助实体抽取
│   ├── evolution.py         # 本体演化引擎
│   └── store.py             # 实体/关系 CRUD
├── indexer/                 # 索引引擎
│   └── engine.py            # SHA-256 指纹增量索引
├── maintenance/             # 运维模块
│   ├── indexer.py           # 增量索引服务
│   ├── watcher.py           # 文件系统监控
│   └── alerts.py            # 健康告警服务
├── mcp/                     # MCP Server
│   └── server.py            # 22 tools (stdio JSON-RPC)
├── agent/                   # Agent 集成
│   ├── client.py            # Agent SDK
│   └── subscription.py      # 知识订阅服务
├── gbrain_bridge.py         # KOS ↔ gbrain 桥接
├── minerva/                 # Minerva 集成
│   └── bridge.py            # 研究流水线
├── multimodal/              # 多模态处理
│   └── __init__.py          # 图片/音频/视频
├── adapters/                # 外部适配器
│   └── __init__.py          # Minerva / Semantic Scholar
├── related/                 # 相关内容
├── web/                     # FastAPI Dashboard
│   └── app.py               # REST API
├── push_engine.py           # 推送告警
├── freshness.py             # 时效性管理
├── knowledge_bridge.py      # 知识集成桥
├── query_service.py         # 知识查询服务
├── context_injector.py      # 上下文注入器
├── trust_layer.py           # 信任层
└── meta_types.py            # 元类型定义
```

### 3.2 数据流

```
                    搜索请求
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
     ┌──────────┐ ┌────────┐ ┌────────┐
     │ FTS5     │ │LanceDB │ │ 图谱   │
     │ 关键词   │ │ 向量   │ │ 遍历   │
     └────┬─────┘ └───┬────┘ └───┬────┘
          │           │          │
          └───────────┼──────────┘
                      ▼
              ┌───────────────┐
              │  RRF 融合     │
              │  + 提升排序   │
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │  去重 + 裁剪  │
              └───────┬───────┘
                      ▼
                  搜索结果
```

### 3.3 存储层

| 存储 | 用途 | 技术 |
|------|------|------|
| **SQLite** | 文档索引 + 本体 + 关系 + 缓存 | FTS5 + WAL |
| **LanceDB** | 向量索引 (4096d/384d) | IVFPQ/HNSW |
| **JSON 文件** | 搜索历史 + 订阅 + 桥接状态 | 文件系统 |
| **内存 LRU** | 热缓存 (1000 条, TTL 5min) | OrderedDict |

---

## 四、检索模式

### 4.1 关键词检索 (keyword)

```
Query → jieba 分词 → FTS5 MATCH → 提升排序 → 结果
```

- 中文: jieba 分词 + OR 连接
- English: 保留原词 + 前缀匹配
- 排序: fts_rank - cards_boost - author_boost - entity_boost - freshness_boost

### 4.2 语义检索 (semantic)

```
Query → embedding (本地/omlx) → LanceDB ANN → Top-K 结果
```

- 本地模型: all-MiniLM-L6-v2 (384d, ~7ms/text)
- omlx 模型: qwen3-embedding-8b (4096d, ~174ms/text)
- 支持域过滤

### 4.3 图谱检索 (graph)

```
Query → 实体匹配 → 关联文档查找 → 结果
```

- 通过本体实体标签匹配查询
- 通过 kos_entity_docs 找到关联文档

### 4.4 混合检索 (hybrid)

```
RRF 融合: score(d) = Σ w_s / (k + rank_s(d))

权重: keyword=1.0, semantic=1.2, graph=0.8
k=60 (避免低排名过度奖励)
多源命中额外 +20% 加成
```

---

## 五、上下文工程

```
┌─────────────────────────────────────────────────────────────┐
│                     Context Engine                          │
│                                                             │
│  查询复杂度 ──▶ 检索预算                                    │
│  ├─ concise:  3 chunks / 1000 tokens                      │
│  ├─ balanced: 7 chunks / 2000 tokens                      │
│  └─ detailed: 15 chunks / 4000 tokens                     │
│                                                             │
│  结果压缩 ──▶ snippet 裁剪 (200/300/500 chars)            │
│  Token 估算 ──▶ 中文 1.5 char/token, 英文 3.5 char/token   │
│  预算控制 ──▶ 超出时裁剪知识段落                            │
│                                                             │
│  输出: LLM-ready prompt (Role + Task + Knowledge)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│                      三级缓存                               │
│                                                             │
│  L1: 内存 LRU (1000 条, TTL 5min)                         │
│      └─ 命中: <0.1ms                                      │
│                                                             │
│  L2: SQLite search_cache 表 (TTL 1hour)                    │
│      └─ 命中: <10ms                                       │
│      └─ 命中后提升至 L1                                    │
│                                                             │
│  L3: 实际检索 (FTS5 + LanceDB + 图谱)                     │
│      └─ 冷查询: <100ms                                    │
│                                                             │
│  失效策略: query 变更时失效, 新结果自动写入                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 七、运维体系

### 7.1 增量索引

```
filesystem watcher / cron
    │
    ▼
SHA-256 diff (仅变更文件)
    │
    ▼
FTS5 upsert + LanceDB add
```

- mtime 快速跳过未变更文件
- 仅变更 chunk 重新 embedding
- 已删除文档自动标记

### 7.2 健康告警

| 检查项 | 阈值 | 级别 |
|--------|------|------|
| 索引完整性 (FTS ≠ 文档数) | diff > 0 | CRITICAL |
| 向量索引滞后 | >100 chunks | WARNING |
| 搜索延迟 P99 | >500ms | WARNING |
| 缓存命中率 | <50% | INFO |
| 孤立实体数 | >50 | INFO |
| 数据库大小 | >10GB | WARNING |

### 7.3 Cron 任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 增量索引 | 每日 2:00 | 检测变更 + embedding |
| 健康检查 | 每周一 9:00 | 全量健康报告 |
| 本体演化 | 每周一 10:00 | 去重 + 关系推导 |
| 全量重建 | 每月1日 3:00 | 向量索引全量重建 |

---

## 八、生态集成

```
┌─────────────────────────────────────────────────────────────┐
│                      生态集成                               │
│                                                             │
│   KOS ←→ gbrain: 双向同步 (文档 ↔ 三元组)                 │
│   KOS ←→ cockpit: REST API 代理 (/api/kos/*)               │
│   KOS ←→ Minerva: 研究流水线 (检索→上下文→研究→核查)       │
│   KOS ←→ OMC: 22 MCP tools (stdio JSON-RPC)              │
│   KOS ←→ Semantic Scholar: 学术论文搜索                    │
└─────────────────────────────────────────────────────────────┘
```

### MCP Tools (22 个)

| Category | Tools |
|----------|-------|
| 搜索 | search_knowledge, get_knowledge, semantic_search, hybrid_search |
| 上下文 | build_context, ask_knowledge, verify_claim |
| 实体 | get_entity, search_entity, explore_entity, get_entity_timeline |
| 订阅 | subscribe_topic, check_subscription |
| 维护 | run_indexer, full_sync, ontology_rebuild, ontology_graph |
| 监控 | get_system_status, get_stats, monitor_health, memory_stats |
| 研究 | research_pipeline, fact_check |
| 集成 | sync_gbrain |
| 自我 | self.get_profile, self.get_current_role, self.get_vision_summary |
| 协作 | collab.create_task, collab.get_task, collab.list_tasks |
| 共识 | consensus.create, consensus.get, consensus.list_expired |

### REST API (cockpit 代理)

```
GET  /api/kos/search?q=&mode=&limit=
GET  /api/kos/suggest?prefix=&limit=
GET  /api/kos/context?q=&mode=
POST /api/kos/verify
GET  /api/kos/stats
GET  /api/kos/health
```

---

## 九、配置管理

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KOS_HOME` | `~/.kos` | 工作区根目录 |
| `OMLX_URL` | `http://localhost:8000` | omlx 网关地址 |
| `OMLX_API_KEY` | `123456` | omlx API Key |
| `OMLX_EMBED_MODEL` | `embed` | embedding 模型名 |

### manifest.json 结构

```json
{
  "name": "workspace-kos",
  "zones": { ... },          // 知识域配置 (20+ zones)
  "domains": { ... },        // 域描述
  "predicatePatterns": { ... },  // 谓词模式
  "artifacts": { "retrievalDatabase": "kos-index.sqlite" },
  "cron": { ... }            // 定时任务配置
}
```

---

## 十、安全约束

1. **只读 SQL**: SQLite 连接强制 `mode=ro` (自定义除外)
2. **写操作拦截**: 正则拦截 INSERT/UPDATE/DELETE/DROP/ALTER
3. **MCP 确认**: L2 操作 (索引重建) 需 `confirmed=true`
4. **数据隔离**: 域级 zone 过滤，防止跨域泄露
5. **隐私保护**: 搜索结果不注入敏感信息 (财务/医疗)

---

## 十一、性能指标

| 指标 | 值 |
|------|------|
| 文档总数 | 31,944 |
| 向量索引 | 87,022 chunks |
| 搜索延迟 (关键词) | <100ms |
| 搜索延迟 (语义) | <800ms |
| 缓存命中 (L1) | <0.1ms |
| 缓存命中 (L2) | <10ms |
| 增量扫描速度 | ~4000 files/s |
| 向量构建速度 | ~4000 docs/min |

---

## 十二、演进路线

参见 演进路线
