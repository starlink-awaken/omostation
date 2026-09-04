---
title: API_REFERENCE
type: doc
---

# Minerva — MCP & API Reference

> 面向机器（AI Agent / MCP Client / 开发者）：工具规范、调用示例、错误处理

---

## MCP Server

### 启动

```bash
minerva mcp                    # 启动 MCP server (stdio)
minerva-mcp                    # 直接调用
```

### 工具列表

#### 1. research_now

执行即时深度研究。

```
Tool: research_now
Params:
  query       (string, required)  — 研究问题
  level       (string, optional)  — L0/L1/L2/L3/L4/auto (default: auto)
  max_cost    (number, optional)  — 最大费用 USD (default: 1.0)
Returns:
  task_id     (string)  — 任务 ID
  status      (string)  — "completed" | "failed"
  summary     (string)  — 摘要（前 800 字符）
  report_path (string)  — 报告文件路径
  cost        (number)  — 实际费用
  paradigm    (object)  — Sophia 范式分析
  stages      (object)  — 各阶段耗时
```

**Agent 调用示例：**
```json
{
  "method": "tools/call",
  "params": {
    "name": "research_now",
    "arguments": {
      "query": "What is the latest in RAG techniques?",
      "level": "L2",
      "max_cost": 0.5
    }
  }
}
```

**返回值：**
```json
{
  "task_id": "a1b2c3d4",
  "status": "completed",
  "summary": "RAG techniques in 2025 have evolved...",
  "report_path": "~/knowledge/reports/20260514-rag-techniques.md",
  "cost": 0.32,
  "paradigm": {
    "paradigm": "literature_review",
    "operations": ["DECOMPOSE", "SEARCH", "EXTRACT", "SYNTHESIZE", "CONCLUDE"]
  },
  "stages": {"search": 8.5, "deep_read": 32.1, "cross_analyze": 15.2}
}
```

---

#### 2. research_schedule

创建定期研究任务。

```
Tool: research_schedule
Params:
  query       (string, required)  — 研究问题
  cron_expr   (string, required)  — Cron 表达式 (e.g. "0 9 * * 1")
  level       (string, optional)  — 研究级别 (default: L1)
Returns:
  task_id     (string)  — 调度任务 ID
  next_run    (string)  — 下次执行时间 ISO8601
```

**Agent 调用示例：**
```json
{
  "method": "tools/call",
  "params": {
    "name": "research_schedule",
    "arguments": {
      "query": "Latest AI regulation news",
      "cron_expr": "0 9 * * 1",
      "level": "L1"
    }
  }
}
```

---

#### 3. research_watch

监控主题，有新内容时通知。

```
Tool: research_watch
Params:
  topic       (string, required)  — 监控主题
  sources     (string, optional)  — 逗号分隔的来源偏好
Returns:
  watch_id    (string)  — 监控 ID
  status      (string)  — "active"
```

---

#### 4. knowledge_search

搜索已有知识库。

```
Tool: knowledge_search
Params:
  query       (string, required)  — 搜索查询
  top_k       (number, optional)  — 返回数量 (default: 5)
  mode        (string, optional)  — "semantic" | "fts" | "hybrid" (default: hybrid)
Returns:
  results     (array)   — 搜索结果 [{title, content, score, source}]
```

**Agent 调用示例：**
```json
{
  "method": "tools/call",
  "params": {
    "name": "knowledge_search",
    "arguments": {
      "query": "transformer architecture attention mechanism",
      "top_k": 3,
      "mode": "hybrid"
    }
  }
}
```

---

#### 5. knowledge_ingest

向知识库添加新内容。

```
Tool: knowledge_ingest
Params:
  source      (string, required)  — URL 或文件路径
  source_type (string, optional)  — "url" | "file" | "text" (default: url)
  content     (string, optional)  — 直接文本内容 (当 source_type=text)
Returns:
  entity_count   (number)  — 提取的实体数
  relation_count (number)  — 提取的关系数
  source_path    (string)  — 存储路径
```

---

### 错误码

| 状态 | 含义 |
|------|------|
| `"completed"` | 研究成功 |
| `"failed"` | 研究出错（检查 summary 字段） |
| `"rate_limited"` | 触发速率限制（30 req/min） |
| `"budget_exceeded"` | 超过月度预算 |

### 降级模式

当 SQLite 不可用时，MCP Server 自动进入降级模式：
- `knowledge_search` → 仍可用（LanceDB 独立运行）
- `knowledge_ingest` → 仍可用（文件直接处理）
- `research_now` → 不可用（需要 SQLite 存储管道状态）
- `research_schedule` → 不可用

---

## Web API

### 基础信息

- Base URL: `http://localhost:8765`
- 默认绑定: `127.0.0.1`（仅本机访问）
- 认证: `X-API-Key` header 或 `?api_key=` 参数（需设置 `MINERVA_API_KEY`）

### POST /api/research

```bash
curl -X POST http://localhost:8765/api/research \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "query=What is RAG&level=L0"
```

```json
{
  "task_id": "a1b2c3d4",
  "status": "completed",
  "query": "What is RAG",
  "level": "L0",
  "summary": "RAG (Retrieval-Augmented Generation) is...",
  "report_path": "~/knowledge/reports/20260514-what-is-rag.md",
  "cost": 0.0,
  "paradigm": { "paradigm": "scientific_inquiry", "operations": ["SEARCH", "SYNTHESIZE", "CONCLUDE"] },
  "stages": { "search": 5.2, "quality_gate": 0.3, "output": 2.1 },
  "total_time": 7.6
}
```

### GET /api/research/{task_id}

```bash
curl http://localhost:8765/api/research/a1b2c3d4
# → {"task_id": "a1b2c3d4", "found": true}
```

### GET /api/report

```bash
curl "http://localhost:8765/api/report?path=~/knowledge/reports/20260514-rag.md"
# → 返回格式化的 HTML 报告
```

路径限制：仅允许 `~/knowledge/reports/` 和 `~/minerva/reports/` 下的文件。

### GET /api/report/pdf

```bash
curl "http://localhost:8765/api/report/pdf?path=~/knowledge/reports/20260514-rag.md"
# → 返回 A4 打印优化的 HTML
```

### GET /api/paradigm

```bash
curl "http://localhost:8765/api/paradigm?query=Compare Rust vs Go"
```

```json
{
  "query": "Compare Rust vs Go",
  "paradigm": "comparative_analysis",
  "operations": ["DECOMPOSE", "SEARCH", "COMPARE", "SYNTHESIZE", "CONCLUDE"],
  "state_count": 6,
  "transition_count": 5,
  "mermaid": "stateDiagram-v2\n  ...",
  "evolution": null
}
```

### GET /api/stream

SSE 端点，每 5 秒推送系统状态：

```bash
curl -N http://localhost:8765/api/stream
# data: {"status":"ok","checks":{"sqlite":true,"llm":true,"executor":true}}
# data: {"status":"ok",...}
```

### GET /api/progress

```bash
curl http://localhost:8765/api/progress
# → {"status":"ok","checks":{...},"timestamp":"15:30:42"}
```

### GET /health

```bash
curl http://localhost:8765/health
# → {"status":"ok"}
```

### 速率限制

- 30 请求/分钟/IP（对 `/api/research` 路径）
- 查询参数 >2KB → 414
- Body >64KB → 413
- URL >4KB → 414

---

## CLI Reference

```bash
minerva research <query>       # 执行研究
  --level auto|L0|L1|L2|L3|L4  # 管道级别
  --max-cost 1.0               # 最大费用 USD
  --template competitor-analysis|literature-review|policy-audit
  --target "..."               # 模板目标

minerva init                   # 首次设置向导
minerva web                    # 启动 Web API (端口 8765)
minerva mcp                    # 启动 MCP Server
minerva daemon                 # 后台守护进程
minerva check                  # 健康检查
minerva maintenance            # 知识库维护
  --action all|staleness|gaps|contradictions
```

---

## Python API

```python
from minerva.config import MinervaConfig
from minerva.llm.client import OpenAICompatibleClient
from minerva.pipeline.engine import create_default_pipeline
from minerva.search.engine import SearchEngine
from minerva.triage.router import TriageRouter, ResearchLevel
from minerva.knowledge.store import SQLiteKnowledgeStore

# Setup
config = MinervaConfig.load()
llm = OpenAICompatibleClient(base_url=config.llm.base_url, model=config.llm.models["agent"])
search = SearchEngine({"exa_api_key": "..."})
kb = SQLiteKnowledgeStore()
pipeline = create_default_pipeline(llm, search, None, kb)
triage = TriageRouter(llm)

# Quick research
from minerva.pipeline.engine import ResearchContext

ctx = ResearchContext(
    query="What is quantum computing?",
    level=ResearchLevel.L0,
)
result = await pipeline.run(ctx)
print(result.summary)
print(f"Report: {result.report_path}")
```
