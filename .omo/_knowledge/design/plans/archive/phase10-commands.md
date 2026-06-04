# Phase 10 — 命令集 (执行Agent用)

> 核心指令: 4个Wave全部可并行执行, 按任务粒度分配
> 负责人: laowang (执行Agent)
> 门禁: 所有Wave交付物E2E测试通过

---

## 并行拓扑

```
Week 1-2 ════════════════════════════════════════════════════════════
            Wave 10.1A (记忆树核心)            Wave 10.2A (TokenJuice引擎)
            ┌─────────────┐                    ┌──────────────┐
            │ T134.1 Schema│ ← 无依赖          │ T137.1 类型检测│
            │ T134.2 存储+搜索│ ← 依赖T134.1   │ T137.2 JSON/HTML│ ← 无依赖
            │ T134.3 折叠展开│ ← 依赖T134.1    │ T137.3 URL+Trace│ ← 无依赖
            │ T134.4 评分  │ ← 依赖T134.1      │ T137.4 去重+基准│ ← 依赖前三个
            └─────────────┘                    └──────────────┘

            Wave 10.3A (进化引擎核心)           Wave 10.4A (债务清零)
            ┌──────────────┐                   ┌──────────────┐
            │ T140.1 模式识别│                   │ T142 py3.9修复│
            │ T140.2 建议生成│ ← 依赖T140.1      │ T143 日志审计  │
            │ T140.3 自动落地│ ← 依赖T140.2      │ T144 文件清理  │
            └──────────────┘                   └──────────────┘

Week 3 ═════════════════════════════════════════════════════════════
  Wave 10.1B                 Wave 10.2B              Wave 10.3B
  T135 MCP工具               T138 Router集成          T141 审批管道
  T136 迁移工具               T139 监控报表

Week 4 ═════════════════════════════════════════════════════════════
  Wave 10.4B: T145 混沌测试 + 全Phase E2E
```

---

## Wave 10.1 — Memory Tree (3周, 7个子任务)

### T134.1 — 树结构+SQLite Schema (1天)
**文件**: `~/.hermes/memory/tree_engine.py`
```python
# models.py 或 tree_engine.py 顶部
# 两个SQLite表: memory_tree_nodes + memory_tree_leaf_content
# 表结构见 task-prompts/phase10-t134-memory-tree.md
# 
# 实现:
# class MemoryTree:
#     def __init__(self, db_path=None)
#     def _ensure_schema(self)  # 创建表
#     def _get_conn(self)       # 获取连接
```
**验证**:
```bash
python3 -c "
from hermes.memory.tree_engine import MemoryTree
import tempfile
mt = MemoryTree(db_path=tempfile.mktemp(suffix='.db'))
conn = mt._get_conn()
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
assert ('memory_tree_nodes',) in tables
assert ('memory_tree_leaf_content',) in tables
print('T134.1: Schema OK')
"
```

### T134.2 — ingest + search 实现 (1.5天)
**文件**: `~/.hermes/memory/tree_engine.py`
```python
# 实现:
# def ingest(self, content, tags=None, source='', score=5) -> str
#   - 创建叶子节点 (node_type='leaf')
#   - 自动挂到对应branch下 (按tags自动创建branch)
#   - 返回node_id
#
# def search(self, query, limit=10, min_score=0) -> list[dict]
#   - 用SQL的LIKE做关键词匹配
#   - 返回含父节点的完整树路径
#   - 按score排序
```
**验证**:
```bash
python3 -c "
from hermes.memory.tree_engine import MemoryTree
import tempfile
mt = MemoryTree(db_path=tempfile.mktemp(suffix='.db'))
nid = mt.ingest('架构先行理论驱动', tags=['principle'], source='user', score=8)
assert nid
results = mt.search('架构', min_score=5)
assert len(results) >= 1
print(f'Search: {len(results)} results')
print('T134.2: PASSED')
"
```

### T134.3 — fold/expand/auto_fold 实现 (1.5天)
```python
# def fold(self, branch_id, llm_summarize=True) -> dict
#   - 将branch下所有叶子→摘要Node
#   - llm_summarize=True时调用LLM生成摘要
#   - llm_summarize=False时只取首条叶子内容
#
# def expand(self, node_id) -> list[dict]
#   - 展开折叠的节点→原始叶子列表
#
# def auto_fold(self, threshold=20) -> int
#   - 遍历所有branch
#   - 叶子数≥threshold → 自动折叠
#   - 返回折叠的branch数
```
**验证**: 同T134验证命令

### T134.4 — 评分机制实现 (0.5天)
```python
# 评分规则:
# 新存入: score=5 (默认)
# 再次命中(搜索到): score += 1 (每命中+1, max=10)
# 3个月未查询: score -= 1
# 6个月未查询: score -= 2 → 自动折叠
# 12个月未查询: score -= 3 → 自动归档(摘要化)
#
# def touch(self, node_id)  # 查询时调用, +1
# def age_decay(self)       # 定期调用, 对所有节点做时效衰减
# def set_score(self, node_id, score)  # 手动调分
```

### T135 — Memory Tree MCP工具增强 (2天)
**文件**: `~/.hermes/memory/mcp_server.py` (增强)
```python
# 保留: memory.get, memory.set, memory.list_tags ← 向后兼容
# 新增:
#   memory.tree_get(node_id, include_children=false)
#   memory.tree_search(query, limit=10, min_score=0)
#   memory.tree_fold(branch_id)
#   memory.tree_branches(tag_filter='')
#
# 所有新增工具遵循MCP stdio协议 (同现有memory.get的实现模式)
```
**验证**:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
  python3 -m hermes.memory.mcp_server 2>&1 | head -5
# 应返回memory.tree_get, memory.tree_search等
```

### T136 — 平面记忆迁移工具 (1天)
**文件**: `~/.hermes/scripts/migrate_memory.py`
```python
# def migrate_from_flat(flat_path='~/.hermes/memory_store.json')
#   - 读取旧JSON文件
#   - 每条记录调一次MemoryTree.ingest()
#   - 按tags分组为branch
#   - 返回迁移条目数
#
# def migrate_from_hermes_memory()
#   - 直接从Hermes内置memory tool读取
#   - 批量迁移
```
**验证**:
```bash
python3 -c "
from hermes.scripts.migrate_memory import migrate_from_flat
# 先创建测试数据
import json, tempfile, os
f = tempfile.mktemp(suffix='.json')
json.dump([{'id':'m1','content':'测试记忆1','tags':['test']}], open(f,'w'))
count = migrate_from_flat(f, db_path=tempfile.mktemp(suffix='.db'))
assert count == 1
os.unlink(f)
print(f'Migrated: {count}')
"
```

### T136.2 — 向后兼容+E2E测试 (1天)
**文件**: `~/Workspace/tests/phase10_wave1_e2e.py`
```python
# E2E场景:
# 1. memory.get 仍可用 (旧API)
# 2. memory.set 写入→自动进入树
# 3. memory.tree_search 返回树结构
# 4. 自动折叠触发 (25条→自动fold)
# 5. 迁移工具正常工作
```

---

## Wave 10.2 — TokenJuice (3周, 7个子任务, 与10.1完全并行)

### T137.1 — 类型检测+基础压缩 (1天)
**文件**: `~/Workspace/agora/src/agora/compressor.py`
```python
class Compressor:
    def detect_type(self, content: str) -> str
        # auto → json | html | code | plaintext | error
        # 检测规则: 看首字符/标签/关键字
    
    def compress(self, content: str, content_type='auto') -> CompressedResult
        # content_type='auto' → 先detect_type再选策略
```

### T137.2 — JSON短key + HTML→Markdown (1天)
```python
def compress_json(self, content: str) -> str:
    # JSON.parse → 递归短key替换 → JSON.stringify
    # key_mapping: {'very_long_name': 'a', ...} → 独立存储映射表
    
def compress_html(self, content: str) -> str:
    # 利用现有的html2text库 (或bs4)
    # html.parser → extract text → 去空白
```

### T137.3 — URL压缩 + Stack trace (1天)
```python
def compress_urls(self, content: str) -> tuple[str, dict]:
    # re.findall URLs → replace with {ref_N}
    # 返回 (压缩后文本, {ref_N: original_url})
    
def compress_stacktrace(self, content: str) -> str:
    # 检测Traceback关键字
    # 只保留: 异常类型 + 首行 + 最后一行
```

### T137.4 — 去重摘要 + 基准测试 (1天)
```python
def dedup_summary(self, content: str, threshold=0.85) -> str:
    # 简单指纹去重 (不需要向量相似度)
    # content → hash → 查缓存 → 有缓存只保留摘要
    
# 基准测试脚本 (T137.4自带):
def benchmark():
    samples = [...]
    total_before, total_after = 0, 0
    for content, ctype in samples:
        r = Compressor().compress(content, ctype)
        total_before += r.original_len
        total_after += r.compressed_len
    ratio = (total_before - total_after) / total_before
    return {'ratio': ratio, 'saved_chars': total_before - total_after}
```
**验证**:
```bash
python3 -c "
from agora.compressor import Compressor, benchmark
r = benchmark()
assert r['ratio'] >= 0.2, f'Compression benchmark failed: {r[\"ratio\"]:.0%}'
print(f'Benchmark: {r[\"ratio\"]:.0%} compression, saved {r[\"saved_chars\"]} chars')
"
```

### T138 — Agora Router 压缩集成 (1.5天)
**文件**: `~/Workspace/agora/src/agora/router.py` (增强)
```python
# 在route_call中的改动:
# from agora.compressor import Compressor
# compressor = Compressor()
# 
# def _compress_params(params):
#     for k, v in params.items():
#         if isinstance(v, str) and len(v) > 500:
#             params[k] = compressor.compress(v).content
#
# 在route_call开始时调用_compress_params()
```
**验证**:
```bash
python3 -c "
# 模拟Router调用带压缩
from agora.compressor import Compressor
from agora.router import Router  # patch后
r = Router()
# 验证大参数被压缩
result = r._compress_params({'query': 'x'*2000})
assert len(result['query']) < 1000
print('T138: Compression in router working')
"
```

### T138.2 — 压缩统计日志 (0.5天)
```python
# 每次压缩记录: {
#   'tool': tool_name,
#   'original_len': len,
#   'compressed_len': len,
#   'ratio': float,
#   'types_used': ['json', 'url']
# }
# 定期写入usage.db的compression_stats表
```

### T139 — 压缩效果监控 (1.5天)
**文件**: `~/.hermes/scripts/compression_stats.py`
```bash
# CLI用法: compression stats --today / --week / --month
#
# 输出:
# Today's compression:
#   Calls compressed: 142/200 (71%)
#   Avg compression: 35%
#   Total saved: 45,382 chars ≈ ~11K tokens
#   Estimated cost saved: $0.23
#
# Top compressors:
#   1. HTML→MD: 60 calls, 52% avg
#   2. JSON短key: 45 calls, 38% avg
#   3. URL压缩: 22 calls, 45% avg
```

### T139.2 — 报表生成+cron (0.5天)
```bash
# 加入cron: 每天汇总一次压缩效果推送到微信
```

---

## Wave 10.3 — 进化闭环 (2周, 5个子任务, 与10.1/10.2完全并行)

### T140.1 — 模式识别引擎 (1天)
**文件**: `~/.hermes/scripts/evolution_engine.py`
```python
class EvolutionEngine:
    def __init__(self, phase_data: dict):
        # phase_data: {tasks: [...], user_corrections: [...], errors: [...], duration: {...}}
    
    def find_patterns(self) -> list[dict]:
        """识别4种模式, 每种返回对应的pattern"""
        patterns = []
        patterns.extend(self._find_repeated_errors())
        patterns.extend(self._find_user_corrections())
        patterns.extend(self._find_efficiency_gaps())
        patterns.extend(self._find_missing_steps())
        return patterns
    
    def _find_repeated_errors(self) -> list[dict]:
        """同一error出现3次以上"""
    
    def _find_user_corrections(self) -> list[dict]:
        """用户纠正agent行为的记录"""
    
    def _find_efficiency_gaps(self) -> list[dict]:
        """超过预估时间2倍以上的task"""
    
    def _find_missing_steps(self) -> list[dict]:
        """task完成但用户补充了步骤"""
```

### T140.2 — 建议生成器 (1天)
```python
def _generate_suggestion(self, pattern: dict) -> dict:
    """模式→建议"""
    # 格式:
    # {
    #   "id": "evol-{date}-{seq}",
    #   "type": "skill_patch" | "memory_update" | "cron_add" | "principle_revise",
    #   "target": str,
    #   "title": str,
    #   "change": str,
    #   "impact": "low" | "medium" | "high",
    #   "auto_apply": bool,
    #   "evidence": [str],
    #   "status": "pending"
    # }
    #
    # 自动决定auto_apply:
    #   - memory_update + 用户明确纠正 → auto
    #   - skill_patch + 步骤明确错误 → auto
    #   - principle_revise → 永远不auto
    #   - cron_add → 仅基础cron auto
```

### T140.3 — 自动落地执行器 (1天)
```python
def auto_apply(self, suggestion: dict) -> dict:
    """自动落地"""
    result = {"id": suggestion["id"], "status": "failed"}
    if suggestion["type"] == "memory_update":
        # 调用memory.set
        from hermes.memory.mcp_server import handle_memory_set
        r = handle_memory_set(suggestion["change"], suggestion.get("tags", ["auto-evolve"]))
        result = {"id": suggestion["id"], "status": "applied", "memory_id": r.get("id")}
    
    elif suggestion["type"] == "skill_patch":
        # 调用skill_manage
        result = {"id": suggestion["id"], "status": "applied", "note": f"Patch {suggestion['target']}"}
    
    elif suggestion["type"] == "cron_add":
        # 调用cronjob
        result = {"id": suggestion["id"], "status": "applied", "note": f"Cron created"}
    
    return result

def apply_pending(self, suggestion_id: str) -> dict:
    """手动审批一条建议"""
    # 人在环中: 用户确认后执行相同逻辑
```

### T141.1 — 待审批列表+审批流程 (1.5天)
```python
def list_pending(self, type_filter: str = "") -> list[dict]:
    """列出待审批建议"""
    # 从 ~/.hermes/evolution/pending.json 读取
    # 按impact排序

# CLI: evolution pending [--type skill_patch]
# CLI: evolution approve <id>
# CLI: evolution reject <id> [--reason "..."]
```

### T141.2 — 执行日志+回滚 (1.5天)
```python
# 每次落地记录到 ~/.hermes/evolution/applied.log
# 格式: [{id, type, target, applied_at, status, rollback_command}]
# 提供rollback: evolution rollback <id>
```

---

## Wave 10.4 — 债务清零+稳定性 (4周, 6个子任务, 与前三Wave完全并行)

### T142 — py3.9兼容全面修复 (1.5天)
```bash
# 扫描所有项目中的 `| None` 语法
grep -rn "| None" ~/Workspace/kos/kos/*.py ~/Workspace/kos/kos/**/*.py \
  ~/Workspace/agora/src/agora/*.py 2>/dev/null | grep -v __pycache__

# 对每个匹配文件:
# 1. 在文件顶部加: from __future__ import annotations
# 2. 或者改为: Optional[...] / Union[..., None]
#
# 优先加 from __future__ import annotations (一行搞定)
```
**验证**:
```bash
python3 --version  # 确认是3.9
python3 -c "from kos.self.api import get_profile; print('OK')" 2>&1
python3 -c "from kos.collab.api import create_task; print('OK')" 2>&1
python3 -c "from agora.authorizer import Authorizer; print('OK')" 2>&1
python3 -c "from agora.compressor import Compressor; print('OK')" 2>&1
```

### T143 — 日志审计+自回收 (2天)
**文件**: `~/.hermes/scripts/self_reclaim.py`
```python
# 自回收规则 (从09架构文档§X2):
# 1. 6个月未触发的保鲜策略→自动归档
# 2. 过期的共识记录→只保留摘要
# 3. 每个季度人肉review一次抗熵策略

class SelfReclaim:
    def audit_logs(self) -> dict:
        """审计所有cron日志"""
        log_dir = Path.home() / ".hermes" / "cron" / "output"
        stats = {"total_logs": 0, "stale_logs": 0, "cleanable": 0}
        for f in log_dir.glob("*"):
            stats["total_logs"] += 1
            age = (time.time() - f.stat().st_mtime) / 86400
            if age > 90:
                stats["stale_logs"] += 1
                # 超过90天→归档摘要
        return stats
    
    def reclaim_old_consensus(self) -> int:
        """过期共识→摘要化"""
        from kos.consensus.api import list_consensus
        consensuses = list_consensus()
        reclaimed = 0
        for c in consensuses:
            # 过期+active → 摘要化
            reclaimed += 1
        return reclaimed
    
    def quarterly_report(self) -> str:
        """季度自回收报告"""
        logs = self.audit_logs()
        reclaim = self.reclaim_old_consensus()
        ...
```

### T144 — 未用文件清理 (0.5天)
```bash
# 检查:
# 1. 旧task-prompts (Phase 1-4)是否还引用
# 2. 旧plan文件是否已archived
# 3. __pycache__ 清理
# 4. .pyc 文件清理 (find . -name "*.pyc" -delete)
#
# 执行:
find ~/Workspace -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find ~/Workspace -name "*.pyc" -delete
```

### T145.1 — 混沌测试场景设计 (0.5天)
**文件**: `~/Workspace/tests/phase10_chaos_test.py`
```python
# 测试场景数组:
CHAOS_SCENARIOS = [
    {"name": "agora_down", "action": "stop agora", "verify": "agent still works"},
    {"name": "memory_db_corrupt", "action": "delete memory_store.json", "verify": "auto-recreate"},
    {"name": "kos_db_locked", "action": "lock kos.db", "verify": "retry mechanism"},
    {"name": "disk_full", "action": "simulate no space", "verify": "graceful error"},
    {"name": "network_offline", "action": "block internet", "verify": "local mode still works"},
    {"name": "all_mcp_down", "action": "kill all MCP servers", "verify": "fallback to CLI"},
]
```

### T145.2 — 执行+验证 (1.5天)
```python
def run_chaos(scenario: dict) -> dict:
    """执行一个混沌测试场景"""
    # 1. 建立基线 (正常状态下发请求)
    # 2. 注入故障
    # 3. 验证降级行为
    # 4. 恢复
    # 5. 验证恢复
    return {"scenario": scenario["name"], "passed": bool, "details": str}

def run_all() -> list[dict]:
    results = []
    for s in CHAOS_SCENARIOS:
        r = run_chaos(s)
        results.append(r)
        if not r["passed"]:
            print(f"⚠️ {s['name']}: FAILED — {r['details']}")
    return results
```

### T145.3 — 混沌测试报告 (0.5天)
```bash
# 输出:
# Phase 10 混沌测试报告
# ═══════════════════════
# ✅ agora_down — 降级到A2A直连正常
# ✅ memory_db_corrupt — 自动重建
# ✅ kos_db_locked — 重试3次后报优雅错误
# ⚠️ disk_full — 仍待修复 (需要更优雅的错误处理)
# ✅ network_offline — 本地模式正常工作
# ✅ all_mcp_down — CLI fallback正常
# 
# 通过率: 5/6 (83%) — 建议修复disk_full后进入下一阶段
```

---

## 全局E2E测试

**文件**: `~/Workspace/tests/phase10_e2e_test.py` (Phase 10全部完成后运行)
```python
# 测试内容:
# 1. Memory Tree: ingest→search→fold→expand→auto_fold
# 2. TokenJuice: compress→stats→Router集成
# 3. Evolution Engine: pattern→suggestion→auto_apply
# 4. Self Reclaim: audit_logs→reclaim_old
# 5. Chaos Test: 6个场景全部通过
# 6. py3.9兼容: 所有模块可import
```

---

## 总结: 并行调度表

```
Week 1:
  laowang T134.1 ─┐
  laowang T134.2 ─┤ Wave 10.1 — Memory Tree (3人并行)
  laowang T137.1 ─┤ Wave 10.2 — TokenJuice (完全并行)
  laowang T140.1 ─┤ Wave 10.3 — 进化引擎 (完全并行)
  laowang T144.0 ─┤ Wave 10.4 — 债务 (完全并行, 最快)

Week 2:
  laowang T135 ───┤ Memory Tree MCP
  laowang T138 ───┤ TokenJuice Router集成
  laowang T140.2 ─┤ Evolution Engine建议生成
  laowang T142 ───┤ py3.9兼容修复
  laowang T143 ───┤ 日志审计

Week 3:
  laowang T136 ───┤ Memory Tree 迁移
  laowang T139 ───┤ TokenJuice 监控
  laowang T141 ───┤ Evolution Engine 审批管道
  laowang T145.1 ─┤ 混沌测试场景设计

Week 4:
  laowang T145.2 ─┤ 混沌测试执行
  laowang E2E ────┤ 全Phase E2E验证
  laowang STATE ──┤ 更新STATE.md
```

**最大并行度**: 5个子任务同时执行 (Wave 10.1/10.2/10.3/10.4各一个)
**最短工期**: 4周 (如果4个laowang并行)
**单人工期**: 10周 (串行)

---

> 执行: 将上述子任务注册到TASK_POOL, 标记状态, 按并行调度表依次执行
> 注意: 每个子任务完成后自动跑验证命令, 不过不停
