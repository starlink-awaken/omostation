---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: T134 — Memory Tree 核心引擎

> 类型: P10 Task | 预估: 5天 | Wave: 10.1 | Phase: 10
> 前置: Phase 8 T114 (Memory MCP Service) — 了解现有平面记忆结构
> 参考: OpenHuman记忆树架构 (独立实现，不碰GPL代码)

## 一、目标

将平面`memory_store.json`升级为层级摘要记忆树，支持评分折叠+树搜索+SQLite存储。保留`memory.get`/`memory.set`向后兼容。

## 二、设计

### 文件: `~/.hermes/memory/tree_engine.py` (~250LOC)

**核心类 MemoryTree**:

```python
class MemoryTree:
    def __init__(self, db_path: str = None):
        # SQLite: memory_tree_nodes + memory_tree_leaf_content
        
    # ── 写入 ──
    def ingest(self, content: str, tags: list[str] = None,
               source: str = "", score: int = 5) -> str:
        """存入叶子节点。如果某个分支叶子超过阈值 → 自动触发折叠"""
    
    def ingest_batch(self, items: list[dict]) -> list[str]:
        """批量存入"""
    
    # ── 读取 ──
    def search(self, query: str, limit: int = 10,
               min_score: int = 0) -> list[dict]:
        """搜索记忆树（含层级展开）"""
    
    def get_branches(self, tag_filter: str = "") -> list[dict]:
        """按标签遍历子树"""
    
    def get_node(self, node_id: str, include_children: bool = False) -> dict:
        """获取单个节点"""
    
    # ── 折叠/展开 ──
    def fold(self, branch_id: str, llm_summarize: bool = True) -> dict:
        """折叠分支：叶子→摘要node。摘要由LLM生成。"""
    
    def expand(self, node_id: str) -> list[dict]:
        """展开node查看原始叶子"""
    
    def auto_fold(self, threshold: int = 20) -> int:
        """自动折叠：叶子超过threshold的分支全部折叠"""
    
    # ── 迁移 ──
    def migrate_from_flat(self, flat_file: str = None) -> int:
        """从旧memory_store.json迁移所有数据到树"""
```

### 数据库设计

```sql
CREATE TABLE IF NOT EXISTS memory_tree_nodes (
    node_id TEXT PRIMARY KEY,
    parent_id TEXT,
    summary TEXT,
    score INTEGER DEFAULT 5,
    node_type TEXT CHECK(node_type IN ('root', 'branch', 'leaf')),
    tags TEXT DEFAULT '[]',
    folded INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_tree_leaf_content (
    leaf_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES memory_tree_nodes(node_id),
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    score INTEGER DEFAULT 5
);

CREATE INDEX idx_nodes_parent ON memory_tree_nodes(parent_id);
CREATE INDEX idx_nodes_type ON memory_tree_nodes(node_type);
CREATE INDEX idx_leaf_node ON memory_tree_leaf_content(node_id);
```

### 评分机制

```python
# Score (1-10) 计算规则:
# 新存入: 默认5
# 再次命中: +1 (每命中一次)
# 用户手动调分: set_score(node_id, score)
# 3个月未查询: -1
# 6个月未查询: -2 → 自动折叠
# 12个月未查询: -3 → 自动归档(摘要化)
# LLM评估: 对内容自动评分 (关键词+重要性)
```

### 向后兼容

```python
# 在memory/mcp_server.py中增强:
# 保留: memory.get, memory.set (写->同时写入树根节点)
# 新增: memory.tree_get, memory.tree_search, memory.tree_fold
# 自动迁移: 首次启动时调用migrate_from_flat()
```

## 三、验证

```bash
# 3.1 基础功能测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/.hermes')
import tempfile, os, json
from memory.tree_engine import MemoryTree

db = tempfile.mktemp(suffix='.db')
mt = MemoryTree(db_path=db)

# 存入
node_id = mt.ingest('架构先行理论驱动是核心方法论', tags=['principle','老王'], source='user', score=8)
assert node_id
print(f'Ingested: {node_id}')

mt.ingest('红蓝对抗安全第一', tags=['principle','security'], source='user', score=9)
mt.ingest('测试驱动开发最有效', tags=['principle','验证'], source='hermes', score=7)
mt.ingest('成本敏感零token优先', tags=['principle','cost'], source='user', score=8)

# 搜索
results = mt.search('架构', min_score=5)
assert len(results) >= 1
print(f'Search \"架构\": {len(results)} results')

# 分支遍历
branches = mt.get_branches()
print(f'Total branches: {len(branches)}')

# 折叠
folded = mt.fold('principle', llm_summarize=False)
print(f'Fold result: {json.dumps(folded, ensure_ascii=False)[:100]}')

# 展开
expanded = mt.expand(folded.get('node_id', ''))
print(f'Expanded: {len(expanded)} children')

os.unlink(db)
print('T134: ALL PASSED')
" 2>&1

# 3.2 自动折叠测试
python3 -c "
from memory.tree_engine import MemoryTree
import tempfile
db = tempfile.mktemp(suffix='.db')
mt = MemoryTree(db_path=db)
# 存入25个叶子 (超过默认阈值20)
for i in range(25):
    mt.ingest(f'知识条目{i}:这是一条测试记忆', tags=['test'], source='test', score=5)
# 自动折叠
folded_count = mt.auto_fold(threshold=20)
assert folded_count >= 1, f'Expected fold, got {folded_count}'
print(f'Auto-folded {folded_count} branches')
import os; os.unlink(db)
print('T134 AUTO-FOLD: PASSED')
" 2>&1

# 3.3 从平面迁移测试
python3 -c "
from memory.tree_engine import MemoryTree
import tempfile, json, os

# 模拟旧平面数据
old_file = tempfile.mktemp(suffix='.json')
with open(old_file, 'w') as f:
    json.dump([
        {'id': 'mem-1', 'content': '老王偏好架构驱动', 'tags': ['principle']},
        {'id': 'mem-2', 'content': '红蓝对抗安全第一', 'tags': ['principle']},
    ], f)

db = tempfile.mktemp(suffix='.db')
mt = MemoryTree(db_path=db)
count = mt.migrate_from_flat(old_file)
assert count == 2, f'Expected 2, got {count}'
print(f'Migrated {count} entries')
os.unlink(old_file); os.unlink(db)
print('T134 MIGRATE: PASSED')
" 2>&1
```

## 四、验收

```
☐ Memory Tree 核心类完整：ingest/search/fold/expand/auto_fold
☐ 评分机制：新存入=5，命中+1，过期-1
☐ 自动折叠：阈值20触发
☐ 向后兼容：memory.get/memory.set 仍可用
☐ 迁移工具：从旧JSON迁移到SQLite树
☐ 所有单元测试通过
