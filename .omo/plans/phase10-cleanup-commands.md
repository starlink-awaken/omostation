# Phase 10 收尾 — 10个子任务执行命令

> 目标: 所有25个子任务完成 → 全Phase E2E全绿
> 前置: 15个核心引擎任务已完成 (tree_engine/compressor/evolution_engine/py3.9兼容)
> 并行: T135/T138.1/T141.1/T143.2/T145.1 可同时启动 (无依赖交叉)
> 门禁: 全部done + Phase 10 E2E PASS

---

## 执行命令（按依赖顺序）

### Step 1: 并行启动 5 个无依赖任务

**T135 — MCP工具增强 (2天)**
```
文件: ~/.hermes/memory/mcp_server.py (增强)

在现有TOOLS和HANDLERS中追加:
TOOLS新增:
  "memory.tree_get": { "description": "按node_id获取树节点", "inputSchema": { "type": "object", "properties": { "node_id": {"type": "string"}, "include_children": {"type": "boolean"} }, "required": ["node_id"] } }
  "memory.tree_search": { "description": "搜索记忆树", "inputSchema": { "type": "object", "properties": { "query": {"type": "string"}, "limit": {"type": "integer", "default": 10}, "min_score": {"type": "integer", "default": 0} }, "required": ["query"] } }
  "memory.tree_fold": { "description": "折叠分支", "inputSchema": { "type": "object", "properties": { "branch_id": {"type": "string"} }, "required": ["branch_id"] } }

HANDLERS新增:
  "memory.tree_get": lambda kw: handle_tree_get(kw["node_id"], kw.get("include_children", False))
  "memory.tree_search": lambda kw: handle_tree_search(kw["query"], kw.get("limit", 10), kw.get("min_score", 0))
  "memory.tree_fold": lambda kw: handle_tree_fold(kw["branch_id"])

import语句: from hermes.memory.tree_engine import MemoryTree
mt = MemoryTree()

验证:
  echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m hermes.memory.mcp_server 2>&1 | grep -c "tree_"
  # 应返回 3 (3个tree工具)
```

**T138.1 — Router集成 (1.5天)**
```
文件: ~/Workspace/agora/src/agora/router.py (增强)

在route_call函数开头插入:
from agora.compressor import Compressor
_compressor = Compressor()

def _compress_params(self, params):
    compressed = {}
    for k, v in params.items():
        if isinstance(v, str) and len(v) > 500:
            r = _compressor.compress(v)
            compressed[k] = r.content
        else:
            compressed[k] = v
    return compressed

在route_call中调用: params = self._compress_params(params)

验证:
  python3 -c "
  from agora.router import Router
  r = Router()
  result = r._compress_params({'query': 'x'*2000})
  assert len(result['query']) < 1000, 'Compression not working'
  print('T138.1: Router compression integrated')
  "
```

**T141.1 — 审批列表+CLI (1.5天)**
```
文件: ~/.hermes/scripts/evolution_engine.py (增强)

追加类 EvolutionApproval:
  def list_pending(self, type_filter='') -> list[dict]
    从 ~/.hermes/evolution/pending.json 读取
    按impact排序, 可选type_filter

  def approve(self, suggestion_id) -> dict
    标记为approved → 调用auto_apply

  def reject(self, suggestion_id, reason='') -> dict
    标记为rejected, 记录原因

CLI命令 (追加到末尾main):
  if sys.argv[1] == 'pending': print(list_pending())
  elif sys.argv[1] == 'approve': approve(sys.argv[2])
  elif sys.argv[1] == 'reject': reject(sys.argv[2], sys.argv[3] if len(sys.argv)>3 else '')

验证:
  python3 -c "
  from hermes.scripts.evolution_engine import EvolutionApproval
  ea = EvolutionApproval()
  pending = ea.list_pending()
  print(f'Pending: {len(pending)} suggestions')
  # 应返回0或已有待审批数据
  print('T141.1: approval CLI ready')
  "
```

**T143.2 — 自回收引擎 (1天)**
```
文件: ~/.hermes/scripts/self_reclaim.py

class SelfReclaim:
  def audit_logs(self) -> dict
    扫描 ~/.hermes/cron/output/ 下的日志
    超过90天 → 标记为stale
    返回 {total, stale, cleanable}

  def reclaim_old_consensus(self) -> int
    从KOS读取过期consensus
    过期+active → 摘要化 (只保留前200字+metadata)
    返回清理条数

  def quarterly_report(self) -> str
    汇总审计和回收结果
    格式: Markdown

  def run_all(self) -> dict
    执行完整自回收流程
    返回 {logs, reclaim, report}

验证:
  python3 -c "
  from hermes.scripts.self_reclaim import SelfReclaim
  sr = SelfReclaim()
  r = sr.run_all()
  print(f'Audit: {r[\"logs\"]}, Reclaim: {r[\"reclaim\"]}')
  print('T143.2: self-reclaim engine ready')
  "
```

**T145.1 — 混沌场景设计 (0.5天)**
```
文件: ~/Workspace/tests/phase10_chaos_test.py

CHAOS_SCENARIOS = [
  {'name': 'agora_down', 'action': 'stop agora', 'verify': 'agent still works via A2A'},
  {'name': 'memory_db_corrupt', 'action': 'rm memory_store.json', 'verify': 'auto-recreate'},
  {'name': 'kos_db_locked', 'action': 'lock kos.db', 'verify': 'retry+graceful'},
  {'name': 'disk_full', 'action': 'simulate no space', 'verify': 'graceful error'},
  {'name': 'network_offline', 'action': 'block internet', 'verify': 'local mode works'},
  {'name': 'all_mcp_down', 'action': 'kill MCP servers', 'verify': 'CLI fallback'},
]

def run_chaos(scenario: dict) -> dict:
  # 1. baseline: 正常发请求
  # 2. inject: 注入故障
  # 3. verify: 验证降级行为
  # 4. recover: 恢复
  # 5. verify_recovery

验证: print('T145.1: 6 chaos scenarios defined')
```

---

### Step 2: 依赖 Step 1 的任务

**T138.2 — 压缩统计日志 (0.5天, 依赖T138.1)**
```
文件: ~/Workspace/agora/src/agora/compressor.py (增强)

在Compressor.compress()末尾加:
from agora.persistence_db import _get_db
conn = _get_db()
conn.execute(
  'INSERT INTO compression_stats (tool, original_len, compressed_len, ratio, types_used) VALUES (?,?,?,?,?)',
  (tool_name, r.original_len, r.compressed_len, r.ratio, json.dumps(types_used))
)

确保 usage.db 有 compression_stats 表:
CREATE TABLE IF NOT EXISTS compression_stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tool TEXT, original_len INTEGER, compressed_len INTEGER,
  ratio REAL, types_used TEXT, timestamp TEXT DEFAULT (datetime('now'))
)

验证:
  python3 -c "
  from agora.compressor import Compressor
  c = Compressor()
  before = len('test')
  # 触发一次压缩
  print('T138.2: compression stats logging enabled')
  "
```

**T139 — 监控CLI (1.5天, 依赖T138.2)**
```
文件: ~/.hermes/scripts/compression_stats.py

Usage: python3 compression_stats.py [--today|--week|--month]

逻辑:
  conn = sqlite3.connect(USAGE_DB)
  if arg == '--today':
    rows = conn.execute('SELECT ... WHERE date(timestamp)=date("now")')
    输出:
    ═══ Today's Compression ═══
    Calls compressed: 142/200 (71%)
    Avg compression ratio: 35%
    Total saved: 45,382 chars (~11K tokens)
    Estimated cost saved: $0.23
    Top tools: collab.* 60 calls 38%, minerva.* 45 calls 52%

Cron:
  加入 ~/.hermes/cron: 每天1次 compression_stats --today 推送到微信

验证:
  python3 ~/.hermes/scripts/compression_stats.py --today
  # 应输出压缩统计看板
```

**T141.2 — 回滚机制 (1.5天, 依赖T141.1)**
```
文件: ~/.hermes/scripts/evolution_engine.py (增强)

在EvolutionApproval中追加:
  def rollback(self, action_id) -> dict
    读取 ~/.hermes/evolution/applied.log
    找到匹配action_id的条目
    执行reverse操作 (memory_update → memory.delete, skill_patch → skill_manage revert)
    记录回滚日志

  def clear_applied(self, days=90) -> int
    清理90天前的已应用日志

验证:
  python3 ~/.hermes/scripts/evolution_engine.py rollback <id>
```

**T145.2 — 混沌测试执行 (1.5天, 依赖T145.1)**
```
文件: ~/Workspace/tests/phase10_chaos_test.py (实现)

def run_all() -> list[dict]:
  results = []
  for s in CHAOS_SCENARIOS:
    r = run_chaos(s)
    results.append(r)
    status = '✅' if r['passed'] else '❌'
    print(f'{status} {s[\"name\"]}: {r.get(\"details\", \"\")}')
  return results

if __name__ == '__main__':
  results = run_all()
  passed = sum(1 for r in results if r['passed'])
  total = len(results)
  print(f'\nChaos Test: {passed}/{total} passed ({passed/total*100:.0f}%)')
  sys.exit(0 if passed == total else 1)

验证:
  python3 ~/Workspace/tests/phase10_chaos_test.py
  # 应输出6个场景结果
```

---

### Step 3: 依赖 Step 1+2 的任务

**T136.2 — 向后兼容+E2E (1天, 依赖T135+T136.1)**
```
文件: ~/Workspace/tests/phase10_e2e_test.py

集成测试:
1. memory.get 仍可用 (旧API兼容)
2. memory.set 写入 → 自动进入树
3. memory.tree_search 返回树结构
4. 自动折叠验证 (25条→fold)
5. 迁移工具: migrate → verify

E2E场景:
  python3 -c "
  from hermes.memory.mcp_server import handle_memory_get, handle_memory_set
  from hermes.memory.tree_engine import MemoryTree
  import tempfile
  
  # 1. 旧API兼容
  handle_memory_set('兼容测试', tags=['test'])
  r = handle_memory_get('兼容')
  assert r['count'] >= 1, 'Old API broken'
  print('✅ Old API: compatible')
  
  # 2. 记忆树
  mt = MemoryTree(db_path=tempfile.mktemp(suffix='.db'))
  mt.ingest('树结构测试', tags=['test'], source='user', score=5)
  results = mt.search('树结构')
  assert len(results) >= 1
  print('✅ MemoryTree: ingest+search OK')
  
  print('Phase10 E2E: ALL PASSED')
  "

验证:
  python3 ~/Workspace/tests/phase10_e2e_test.py
  # 全部PASS → Phase 10 完成
```

---

## 并行调度（执行Agent用）

```
立即启动 5 路并行:
  laowang → T135 (MCP工具增强)        ~/.hermes/memory/mcp_server.py
  laowang → T138.1 (Router集成)     ~/Workspace/agora/src/agora/router.py
  laowang → T141.1 (审批CLI)         ~/.hermes/scripts/evolution_engine.py
  laowang → T143.2 (自回收)          ~/.hermes/scripts/self_reclaim.py
  laowang → T145.1 (混沌场景)         ~/Workspace/tests/phase10_chaos_test.py

完成后启动:
  laowang → T138.2 (压缩统计)         ~/Workspace/agora/src/agora/compressor.py
  laowang → T139 (监控CLI)           ~/.hermes/scripts/compression_stats.py
  laowang → T141.2 (回滚)            ~/.hermes/scripts/evolution_engine.py
  laowang → T145.2 (混沌执行)         ~/Workspace/tests/phase10_chaos_test.py

最后:
  laowang → T136.2 (E2E)            ~/Workspace/tests/phase10_e2e_test.py
```

---

## 验收（全部完成时）

```bash
# 验证所有交付物存在
ls -la ~/.hermes/memory/mcp_server.py                          # T135: MCP增强
grep -c "tree_" ~/.hermes/memory/mcp_server.py                 # 应有>=3
grep -c "compressor" ~/Workspace/agora/src/agora/router.py     # T138: Router
wc -l ~/.hermes/scripts/self_reclaim.py                        # T143: 自回收
wc -l ~/Workspace/tests/phase10_chaos_test.py                  # T145: 混沌测试
wc -l ~/Workspace/tests/phase10_e2e_test.py                    # T136: E2E

# 运行E2E
python3 ~/Workspace/tests/phase10_e2e_test.py

# 更新STATE
# → Phase 10: [██████████] 100% (25/25) ✅
# → 总体进度: 100% (201/201) 🎉
```
