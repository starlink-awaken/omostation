# 数据流向规范

> 定义 Starlink Awaken 生态中知识从**摄取 → 结构化 → 推导 → 研究**的端到端数据流。
> 更新: 2026-05-24

---

## 一、总览

```
                     数据契约层
                   ┌──────────────┐
                   │   Eidos      │
                   │  (Schema)    │
                   └──────┬───────┘
                          │ 验证/导出
                          ▼
┌────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│ Kronos │───▶│  Ontoderive  │───▶│   Minerva    │───▶│   输出     │
│ (摄取)  │    │  (事实推导)    │    │  (深度研究)    │    │ (知识/报告) │
└────────┘    └──────────────┘    └──────────────┘    └────────────┘
     │               │                   │
     ▼               ▼                   ▼
┌──────────┐  ┌────────────┐  ┌──────────────────┐
│ 原始内容  │  │ 事实集      │  │ 研究报告/SQLite    │
│ JSON/MD  │  │ ontoderive │  │ KnowledgeStore    │
│          │  │ -v1 格式   │  │                   │
└──────────┘  └────────────┘  └──────────────────┘
```

---

## 二、各阶段数据格式

### 2.1 Kronos 输出（摄取层）

**格式标识**: `format_version: "kronos-v1"`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `format_version` | string | ✅ | `"kronos-v1"` |
| `url` | string | ✅ | 原始 URL |
| `content_type` | string | ✅ | `article/paper/social/video/policy/resource` |
| `fallback_chain` | list | ✅ | 5 层 fallback 链结果 |
| `total_layers` | number | ✅ | 成功层数 |

**完整 Schema**: `kronos/schemas/pipeline-schemas.json` → `RawContent`

**输出位置**:
- 通过 MCP 工具返回 (stdout JSON)
- 结构化提取后写入 KOS / Obsidian vault

### 2.2 Ontoderive 输出（事实推导层）

**格式标识**: `format_version: "ontoderive-v1"`

| 字段 | 类型 | 说明 |
|------|------|------|
| `format_version` | string | `"ontoderive-v1"` |
| `facts/` | directory | 推导出的事实 Markdown 文件 |
| `confidence` | float | 0-1 置信度 |
| `derivation_path` | string | 推导路径记录 |

**输出位置**:
- CLI stdout / `facts/` 目录
- 可作为 minerva 研究输入

### 2.3 Sophia 输出（范式编译层）

**格式**: `ParadigmProgram` JSON

```json
{
  "operations": [...],
  "name": "...",
  "description": "...",
  "max_iterations": 5
}
```

**输出位置**:
- Python 内存对象 → minerva pipeline 消费
- 非持久化存储

### 2.4 Minerva 输出（研究层）

| 级别 | 输出格式 | 存储 |
|------|----------|------|
| L0 | L0Report (dataclass) | SQLite KnowledgeStore |
| L1 | 结构化搜索摘要 | SQLite |
| L2 | DeepRead 分析 | SQLite + Markdown |
| L3 | 研究报告 (PDF/MD) | knowledge_store + 文件系统 |
| L4 | 深度研究报告 | knowledge_store + 文件系统 |

**输出位置**:
- SQLite: `~/.minerva/knowledge_store.db`
- 文件: `minerva/outputs/`

### 2.5 Eidos Schema 验证层

Eidos 提供三类预注册 Schema，可作为跨项目数据验证的标准：

| Schema | 用途 | 消费方 |
|--------|------|--------|
| `KnowledgeCard` | 知识条目验证 | kronos, minerva |
| `Fact` | 事实数据验证 | ontoderive |
| `OntologyNode` | 本体节点验证 | ontoderive, KOS |

**接口**: `eidos_export` MCP 工具 → 标准化 JSON Schema

---

## 三、数据格式兼容性

### 原则

1. **所有 MCP 工具输出必须带 `format_version`**（Eidos 除外，它本身是 Schema 层）
2. **所有结构化输出必须向后兼容** — 新增字段不能删除已有字段
3. **版本迁移路径** — 通过 Eidos SchemaMigration 支持版本升级

### 当前版本快照

| 项目 | 格式版本 | 输出位置 | Schema 定义 |
|------|---------|----------|-------------|
| kronos | `kronos-v1` | MCP stdout / KOS / vault | `kronos/schemas/pipeline-schemas.json` |
| ontoderive | `ontoderive-v1` | `facts/` 目录 / CLI stdout | 自约定 Markdown 格式 |
| sophia | — | Python 内存对象 | ParadigmProgram dataclass |
| minerva | — | SQLite / 文件系统 | KnowledgeStore 表结构 |
| eidos | `registry-v1` | `~/.eidos/registry.json` | `Schema.to_dict()` / `to_json_schema()` |

---

## 四、数据流向示例

### 示例：文章知识摄取

```
1. Kronos
   └─ handle_fetch(url="https://example.com/article")
      └─ 输出: {format_version: "kronos-v1", url, content_type: "article", fallback_chain: [...]}
          │
2. LLM 提取 (kronos extractor / 外部 LLM)
   └─ 提取: title, summary, key_points, entities
      └─ 输出: StructuredContent JSON
          │
3. Eidos 验证
   └─ eidos_validate(data={...}, schema_type="KnowledgeCard")
      └─ 输出: {is_valid: true, errors: []}
          │
4. Ontoderive 事实推导（可选）
   └─ 从提取结果推导新事实
      └─ 输出: facts/ 目录下的 Markdown 文件
          │
5. Minerva 深度研究（可选）
   └─ 将提取结果作为研究输入
      └─ 输出: L0-L4 研究报告 → KnowledgeStore
          │
6. 分发存储
   ├─ KOS (知识图谱索引)
   ├─ Obsidian Vault (阅读友好)
   └─ WPS Note (随手查阅)
```

---

## 五、改进建议

### 已完成

- ✅ `kronos/schemas/pipeline-schemas.json` 定义了完整管线数据格式
- ✅ `kronos/mcp_server.py` 输出增加了 `format_version: "kronos-v1"` 标识
- ✅ `eidos/mcp_server.py` 增加了 `eidos_export` 工具用于导出标准化 Schema
- ✅ kronos → Eidos KnowledgeCard 适配器（`adapters.py` + `kronos_extract` 工具）
- ✅ minerva / sophia / agora MCP 工具增加 `format_version` 字段
- ✅ ontoderive → Eidos Fact 适配器（`adapters.py` + `to_eidos_fact()`）
- ✅ minerva → Eidos KnowledgeCard 适配器（`adapters.py` + `research_now`/`knowledge_ingest` 的 `eidos_card` 字段）

### 待持续推进

1. **Eidos Schema 消费集成**
   - [x] kronos extractor → 输出兼容 Eidos KnowledgeCard（`adapters.py` + `kronos_extract` 工具）
   - [x] ontoderive → 事实写入支持 Eidos Fact Schema（`adapters.py` + `to_eidos_fact()`）
   - [x] minerva ingest → 输出可选写入 Eidos KnowledgeCard（`adapters.py` + `research_now`/`knowledge_ingest` 工具的 `eidos_card` 字段）

2. **跨项目数据契约**
   - [ ] 创建 `starlink-types` 包（或模块）定义共享数据类
   - [ ] 导入约定：无需安装 `starlink-types`，各项目自持格式定义但遵循契约

3. **格式版本化**
   - [x] 所有 MCP 工具统一 `format_version` 命名规范（已完成：kronos/kronos-v1, ontoderive/ontoderive-v1, pallas/pallas-v1, eidos/registry-v1, minerva/minerva-v1, sophia/sophia-v1, agora/agora-v1）
   - [ ] Eidos SchemaMigration 管线化：新版本 Schema 发布时自动触发迁移

---

## 六、相关文件索引

| 文件 | 说明 |
|------|------|
| `kronos/schemas/pipeline-schemas.json` | Kronos 管线数据格式完整定义 |
| `docs/llm-dependency-matrix.md` | LLM 依赖矩阵（数据流中 LLM 使用节点） |
| `gateway/ARCHITECTURE.md` | Gateway 前端层架构（数据流入口） |
| `agora/ARCHITECTURE.md` | Agora 服务治理（数据流注册中心） |
