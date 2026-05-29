# Task Prompt: T126 — Agora Authorizer中间件

> 类型: P9 Task | 预估: 4天 | Wave: 9.2 | Phase: 9
> 前置: T125 (CapabilityGrant Schema)

## 一、目标

在Agora Router的路由前插入CapabilityGrant校验。每个MCP调用先查grant表，无匹配或约束超限则返回403。

## 二、设计

### 2.1 `~/Workspace/agora/src/agora/authorizer.py` (~160LOC)

**核心类 `Authorizer`**:

```python
class Authorizer:
    def __init__(self, db_path: str = None):
        # grants.db SQLite
    
    def create_grant(self, subject, capability, resource_scope, constraints, issued_by)
    def check_call(self, subject, tool, cost=0) -> dict  # {"allowed": True/False, "reason": "...", "grant_id": "..."}
    def revoke_grant(self, grant_id) -> bool
    def list_grants(self, subject="") -> list[dict]
```

**数据库表**:
```sql
CREATE TABLE IF NOT EXISTS grants (
    grant_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    capability TEXT NOT NULL,
    resource_scope TEXT DEFAULT '',
    constraints TEXT DEFAULT '{}',
    issued_by TEXT DEFAULT '',
    issued_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,
    revoked_at TEXT DEFAULT '',
    call_count INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0
);
```

**核心逻辑 — check_call**:
1. 按subject查所有非吊销grant
2. 匹配capability（支持 `*`、`collab.*` 通配符）
3. 检查每个匹配grant的constraints（expire_at/max_calls/max_cost_usd）
4. 第一个通过的grant → 更新call_count/total_cost → 返回allowed
5. 没有通过的 → 返回denied + 原因

**约束检查顺序**:
```
1. expire_at 过期 → 跳过此grant
2. max_calls 超限 → 跳过
3. max_cost_usd 超限 → 跳过
4. 全部通过 → 使用此grant
```

### 2.2 Router集成 `~/Workspace/agora/src/agora/router.py`

在 `route_call` 函数开头插入：

```python
# 从请求头或上下文中提取subject
subject = headers.get("X-Identity-Subject", "anonymous")
tool_name = params.get("tool_name", "")

# 授权校验
auth = authorize_middleware(subject, tool_name)
if not auth["allowed"]:
    return {"error": f"403 Forbidden: {auth['reason']}"}
```

### 2.3 `~/Workspace/agora/src/agora/cli/commands_grant.py` (~50LOC)

`agora grant create/revoke/list/check` 子命令：

```bash
# 创建授权
agora grant create --subject "user:老王" --capability "collab.*" --scope "project:research"

# 吊销
agora grant revoke --grant-id "grant:abc123"

# 列出
agora grant list --subject "user:老王"

# 检查
agora grant check --subject "user:老王" --tool "collab.create_task"
```

### 2.4 Feature Flag控制

首次部署时默认 **pass-through**（不会拒绝请求），只记录审计。确认稳定后切换为强制模式：

```python
# authorizer.py
ENFORCE_MODE = False  # 默认pass-through

def authorize_middleware(subject, tool, cost=0):
    az = Authorizer()
    r = az.check_call(subject, tool, cost)
    if not ENFORCE_MODE:
        r["_note"] = "pass-through mode, grant check logged only"
    return r
```

## 三、验证

```bash
# 3.1 基础功能测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/Workspace/agora/src')
from agora.authorizer import Authorizer
import tempfile, os

db = tempfile.mktemp(suffix='.db')
az = Authorizer(db_path=db)

# 创建grant
r = az.create_grant('user:老王', 'collab.*', 'project:research', {'max_cost_usd': 10.0})
print(f'Grant: {r[\"grant_id\"]}')

# 检查 (allowed)
r2 = az.check_call('user:老王', 'collab.create_task', 0.01)
assert r2['allowed'], f'Should be allowed: {r2}'

# 检查 (denied — 无grant)
r3 = az.check_call('user:unknown', 'collab.create_task')
assert not r3['allowed'], f'Should be denied: {r3}'

# 通配符匹配
r4 = az.check_call('user:老王', 'collab.list_tasks')
assert r4['allowed'], f'Wildcard match failed: {r4}'

# 吊销后拒绝
az.revoke_grant(r['grant_id'])
r5 = az.check_call('user:老王', 'collab.create_task')
assert not r5['allowed'], f'Should be denied after revoke: {r5}'

os.unlink(db)
print('T126: ALL PASSED')
" 2>&1

# 3.2 成本上限测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/Workspace/agora/src')
from agora.authorizer import Authorizer
import tempfile, os

db = tempfile.mktemp(suffix='.db')
az = Authorizer(db_path=db)
az.create_grant('user:老王', 'research', '', {'max_cost_usd': 0.05})
# 耗尽
for i in range(5):
    az.check_call('user:老王', 'research', 0.01)
r = az.check_call('user:老王', 'research', 0.01)
assert not r['allowed'], f'Should hit cost limit: {r}'
print(f'Cost limit hit: {r}')
os.unlink(db)
print('T126 COST TEST: PASSED')
" 2>&1

# 3.3 调用次数上限测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/Workspace/agora/src')
from agora.authorizer import Authorizer
import tempfile, os

db = tempfile.mktemp(suffix='.db')
az = Authorizer(db_path=db)
az.create_grant('user:老王', 'collab.*', '', {'max_calls': 3})
for i in range(3):
    r = az.check_call('user:老王', 'collab.list_tasks')
    assert r['allowed'], f'Call {i} should be allowed: {r}'
r = az.check_call('user:老王', 'collab.list_tasks')
assert not r['allowed'], f'Call 4 should be denied: {r}'
print(f'Call limit hit: {r}')
os.unlink(db)
print('T126 CALL LIMIT TEST: PASSED')
" 2>&1
```

## 四、验收

```
☐ Authorizer 能创建/校验/吊销grant
☐ check_call 通配符匹配 (collab.* → collab.create_task)
☐ check_call 约束检查 (cost/calls/expire)
☐ Router集成：denied返回403
☐ grant CLI (create/revoke/list/check)
☐ Feature flag：pass-through模式默认开启
☐ 单元测试全部通过
