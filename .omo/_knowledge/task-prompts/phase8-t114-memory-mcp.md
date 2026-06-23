---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: T114 — Memory MCP Service

> 类型: P8 Task | 预估: 4天 | Wave: 8.2 | Phase: 8
> 前置: Hermes memory系统就绪

## 一、目标

将Hermes内部的memory tool暴露为MCP服务，任何Agent通过Agora都能查询/写入记忆。

## 二、设计

### 文件: `~/.hermes/memory/mcp_server.py`

```python
#!/usr/bin/env python3
"""Memory MCP Service — 将Hermes记忆暴露给所有Agent"""
import json, sys
from pathlib import Path

MEMORY_FILE = Path.home() / ".hermes" / "memory_store.json"

def _load_memory() -> list:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    return []

def _save_memory(memories: list):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(memories, ensure_ascii=False, indent=2))

def handle_memory_get(query: str, limit: int = 5) -> dict:
    memories = _load_memory()
    # 简单关键词匹配
    results = [m for m in memories if query.lower() in m.get("content", "").lower()]
    return {"results": results[:limit], "count": len(results[:limit])}

def handle_memory_set(content: str, tags: list = None) -> dict:
    memories = _load_memory()
    entry = {
        "id": f"mem-{len(memories)+1}",
        "content": content,
        "tags": tags or [],
        "created_at": __import__('datetime').datetime.now().isoformat()
    }
    memories.append(entry)
    _save_memory(memories)
    return {"status": "saved", "id": entry["id"]}

# MCP Server loop
TOOLS = {
    "memory.get": {
        "description": "查询持久记忆",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 5}
        }, "required": ["query"]}
    },
    "memory.set": {
        "description": "写入持久记忆",
        "inputSchema": {"type": "object", "properties": {
            "content": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}}
        }, "required": ["content"]}
    },
}

HANDLERS = {
    "memory.get": lambda **kw: handle_memory_get(kw["query"], kw.get("limit", 5)),
    "memory.set": lambda **kw: handle_memory_set(kw["content"], kw.get("tags", [])),
}

# 标准MCP stdio loop (参考kos/mcp/server.py)
```

### 注册到Agora

```bash
agora service register \
  --name "hermes-memory" \
  --command "python3" \
  --args "-m hermes.memory.mcp_server"

agora add-route --tool "memory.*" --service "hermes-memory"
```

## 三、验证

```bash
# 1. 独立运行测试
python3 -c "
from hermes.memory.mcp_server import handle_memory_set, handle_memory_get
handle_memory_set('老王偏好架构先行理论驱动', tags=['principle'])
r = handle_memory_get('架构先行')
assert r['count'] >= 1
print('T114: PASSED')
"
```

## 四、验收

```
☐ memory MCP server独立运行
☐ memory.get 可查询
☐ memory.set 可写入
☐ Agora已注册
☐ 非Hermes Agent也可调用
```
