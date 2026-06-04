# Phase 9 — 多人多组织 🏢

> **周期**: 8周 (Wave 9.1: 2周, Wave 9.2: 2周, Wave 9.3: 2周, Wave 9.4: 2周)
> **负责人**: TBD (执行Agent + 用户审批)
> **目标**: 跨组织创建Task、共享能力、审计追踪——从单人OS到多组织联邦
> **前置**: Phase 8 (多Agent协作/降级模式)
> **门禁**: 跨组织Task创建→认领→完成链路跑通，身份凭证可签发/验证
> **风险**: 密码学知识（DID/密钥管理）可能不够；跨进程状态同步

---

## 现有状态盘点

| 组件 | 当前状态 | Phase 9 要做什么 |
|------|---------|------------------|
| `IdentityEnvelope` | 宪法概念定义，无Eidos Schema，无代码 | 定稿Schema+签发器+验证器 |
| `CapabilityGrant` | 宪法概念定义，无Eidos Schema，无代码 | 定稿Schema+授权中间件+CLI |
| `Agora KeyManager` | 已有API Key创建/校验/吊销 | 扩展为CA模式签发身份 |
| `Agora TenantManager` | 已有多租户+令牌+限流 | 扩展为租户级身份+跨租户路由 |
| `KOS Collab visibility_scope` | 字段存在但无执行 | 实现scope过滤+跨组织Task |
| `KOS Self` | 只有单人profile | 扩展为多用户身份管理 |
| Cost Accounting | 只有本地usage.db | 扩展为跨组织成本归属 |

---

## 依赖关系

```
Wave 9.1 (2周) — IdentityEnvelope 做实
  ├── T122 Eidos IdentityEnvelope Schema
  ├── T123 → 身份签发器 (CA模块)
  └── T124 → Hermes携带身份凭证 + MCP注入

Wave 9.2 (2周) — CapabilityGrant 可执行 (依赖9.1)
  ├── T125 Eidos CapabilityGrant Schema (含Tenant+ResourceScope)
  ├── T126 → Agora授权门禁中间件
  └── T127 → grant签发/吊销CLI

Wave 9.3 (2周) — 跨组织协作 (依赖9.1+9.2)
  ├── T128 → visibility_scope执行 (team/org/public)
  ├── T129 → 跨组织Task E2E + 外部Agent认领
  └── T130 → 跨组织Resource Accounting

Wave 9.4 (2周) — 生态宪法 (依赖9.3)
  ├── T131 → 生态宪法文档 (最小互通协议)
  ├── T132 → 节点类型定义 (Full/Light/External/Human)
  └── T133 → 异构节点Adapter模板

回滚策略:
  - Identity签发失败 → 退回token-based auth (现有Agora TenantManager)
  - CapabilityGrant中间件影响性能 → feature flag控制，默认pass-through
  - 跨组织Task收不到 → 退回到单一org，manual转发
```

---

## Wave 9.1 — IdentityEnvelope 做实 (2周, 3 Tasks)

### T122: IdentityEnvelope Schema 定稿

**文件**: `~/Workspace/eidos/schemas/identity-envelope.schema.json`

**当前**: identity-role.schema.json 是给 L4 Self 用的角色画像，不是跨用户身份凭证。

**新建**: IdentityEnvelope schema 定义可验证的身份凭证：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://workspace.local/contracts/identity-envelope.schema.json",
  "title": "IdentityEnvelope",
  "description": "跨组织可验证身份凭证。由CA签发，含proof_ref和expires_at。",
  "type": "object",
  "required": [
    "subject_id", "subject_type", "issuer", "issued_at", "proof_ref"
  ],
  "properties": {
    "subject_id": {
      "type": "string",
      "pattern": "^(user|agent|org|node):[a-zA-Z0-9_-]+$",
      "description": "主体ID，如 user:老王、agent:hermes、org:partner"
    },
    "subject_type": {
      "type": "string",
      "enum": ["user", "agent", "org", "node", "service"],
      "description": "主体类型"
    },
    "issuer": {
      "type": "string",
      "description": "签发者CA标识，如 ca:agora.starlink.local"
    },
    "issued_at": {
      "type": "string",
      "format": "date-time",
      "description": "签发时间"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time",
      "description": "过期时间（空=永不过期）"
    },
    "proof_ref": {
      "type": "string",
      "description": "签名/密钥引用，如 did:key:z6Mk..."
    },
    "proof_type": {
      "type": "string",
      "enum": ["did:key", "x509", "hmac", "jwt"],
      "description": "证明方式",
      "default": "did:key"
    },
    "tenant": {
      "type": "string",
      "description": "所属租户，如 starlink-core、partner-org"
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "description": "扩展信息"
    }
  }
}
```

**注册**: 追加到 `eidos/schemas/registry.json`

**验证**:
```bash
# 注册后验证
python3 -c "
import json
with open('/Users/xiamingxing/Workspace/eidos/schemas/identity-envelope.schema.json') as f:
    schema = json.load(f)
assert schema['title'] == 'IdentityEnvelope'
assert 'subject_id' in schema['required']
print('T122: Schema OK')
" 2>&1
```

**验收**:
```
☐ identity-envelope.schema.json 定稿
☐ registry.json 已注册
☐ JSON Schema 校验通过
```

---

### T123: CA身份签发器

**文件**: 
- `~/Workspace/agora/src/agora/identity_ca.py` — CA核心
- `~/Workspace/agora/src/agora/cli/commands_identity.py` — CLI命令

**核心逻辑**:

```python
"""agora/identity_ca.py — 身份凭证签发与验证。"""

import json
import time
import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path
from agora.persistence_db import _get_db

CA_DB_PATH = Path.home() / ".kos" / "identity.db"

@dataclass
class Identity:
    subject_id: str
    subject_type: str  # user/agent/org/node
    issuer: str
    issued_at: str
    expires_at: str
    proof_ref: str
    proof_type: str = "hmac"
    tenant: str = ""
    revoked: bool = False

class IdentityCA:
    """Local CA — 签发/吊销/验证身份凭证。"""
    
    def __init__(self, db_path: str = None, ca_id: str = "ca:agora.starlink.local"):
        self._db_path = db_path or str(CA_DB_PATH)
        self.ca_id = ca_id
        self._ensure_schema()
    
    def _ensure_schema(self):
        conn = _get_db(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS identities (
                subject_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                issuer TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT DEFAULT '',
                proof_ref TEXT NOT NULL,
                proof_type TEXT DEFAULT 'hmac',
                tenant TEXT DEFAULT '',
                revoked INTEGER DEFAULT 0
            )
        """)
        # CA自身的密钥对
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ca_keys (
                key_id TEXT PRIMARY KEY,
                secret_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    
    def init_ca(self) -> str:
        """初始化CA密钥。返回公钥引用。"""
        conn = _get_db(self._db_path)
        key_id = "key:" + secrets.token_hex(8)
        raw_secret = secrets.token_hex(32)
        secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT OR REPLACE INTO ca_keys (key_id, secret_hash, created_at) VALUES (?, ?, ?)",
            (key_id, secret_hash, ts),
        )
        conn.commit()
        return f"hmac:{key_id}"
    
    def issue_identity(self, subject_id: str, subject_type: str,
                       tenant: str = "", expires_days: int = 365) -> dict:
        """签发身份凭证。"""
        conn = _get_db(self._db_path)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        expires = ""
        if expires_days > 0:
            expires = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                    time.gmtime(time.time() + expires_days * 86400))
        
        # 生成HMAC proof
        raw = secrets.token_hex(16)
        proof_hash = hashlib.sha256(raw.encode()).hexdigest()
        proof_ref = f"hmac:{proof_hash[:16]}"
        
        conn.execute(
            """INSERT OR REPLACE INTO identities
               (subject_id, subject_type, issuer, issued_at, expires_at,
                proof_ref, proof_type, tenant)
               VALUES (?, ?, ?, ?, ?, ?, 'hmac', ?)""",
            (subject_id, subject_type, self.ca_id, now, expires,
             proof_ref, tenant),
        )
        conn.commit()
        
        return {
            "subject_id": subject_id,
            "subject_type": subject_type,
            "issuer": self.ca_id,
            "issued_at": now,
            "expires_at": expires,
            "proof_ref": proof_ref,
            "proof_type": "hmac",
            "proof_secret": raw,  # Show once!
            "tenant": tenant,
        }
    
    def verify_identity(self, subject_id: str, proof_secret: str = "") -> dict:
        """验证身份凭证有效性。"""
        conn = _get_db(self._db_path)
        row = conn.execute(
            "SELECT * FROM identities WHERE subject_id = ? AND revoked = 0",
            (subject_id,),
        ).fetchone()
        if not row:
            return {"valid": False, "reason": "not_found"}
        
        cols = ["subject_id", "subject_type", "issuer", "issued_at",
                "expires_at", "proof_ref", "proof_type", "tenant", "revoked"]
        d = dict(zip(cols, row))
        
        if d["expires_at"] and d["expires_at"] < time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()):
            return {"valid": False, "reason": "expired"}
        
        if proof_secret:
            expected_hash = hashlib.sha256(proof_secret.encode()).hexdigest()
            if not d["proof_ref"].endswith(expected_hash[:16]):
                return {"valid": False, "reason": "proof_mismatch"}
        
        return {"valid": True, "identity": d}
    
    def revoke_identity(self, subject_id: str) -> bool:
        conn = _get_db(self._db_path)
        conn.execute("UPDATE identities SET revoked = 1 WHERE subject_id = ?", (subject_id,))
        conn.commit()
        return True
    
    def list_identities(self, tenant: str = "") -> list[dict]:
        conn = _get_db(self._db_path)
        if tenant:
            rows = conn.execute(
                "SELECT subject_id, subject_type, issuer, issued_at, expires_at, tenant, revoked FROM identities WHERE tenant = ?",
                (tenant,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT subject_id, subject_type, issuer, issued_at, expires_at, tenant, revoked FROM identities"
            ).fetchall()
        cols = ["subject_id", "subject_type", "issuer", "issued_at", "expires_at", "tenant", "revoked"]
        return [dict(zip(cols, r)) for r in rows]

def send_jsonrpc(data: dict) -> None:
    import sys
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def run_mcp_stdio():
    """MCP stdio server loop for identity tools."""
    import sys
    line = sys.stdin.readline()
    if not line: return
    msg = json.loads(line)
    if msg.get("method") != "initialize": return
    send_jsonrpc({"jsonrpc": "2.0", "id": msg["id"], "result": {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "identity-ca", "version": "1.0.0"},
        "capabilities": {"tools": {}},
    }})
    sys.stdin.readline()
    
    ca = IdentityCA()
    ca.init_ca()
    
    while True:
        line = sys.stdin.readline()
        if not line: return
        msg = json.loads(line)
        if msg.get("method") == "tools/list":
            send_jsonrpc({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [
                {"name": "identity.issue", "description": "签发身份凭证",
                 "inputSchema": {"type": "object", "properties": {
                     "subject_id": {"type": "string"},
                     "subject_type": {"type": "string", "enum": ["user","agent","org","node"]},
                     "tenant": {"type": "string"},
                     "expires_days": {"type": "integer", "default": 365},
                 }, "required": ["subject_id", "subject_type"]}},
                {"name": "identity.verify", "description": "验证身份凭证",
                 "inputSchema": {"type": "object", "properties": {
                     "subject_id": {"type": "string"},
                 }, "required": ["subject_id"]}},
                {"name": "identity.revoke", "description": "吊销身份凭证",
                 "inputSchema": {"type": "object", "properties": {
                     "subject_id": {"type": "string"},
                 }, "required": ["subject_id"]}},
                {"name": "identity.list", "description": "列出所有凭证",
                 "inputSchema": {"type": "object", "properties": {
                     "tenant": {"type": "string"},
                 }}},
            ]}})
        elif msg.get("method") == "tools/call":
            p = msg.get("params", {})
            tn = p.get("name", "")
            a = p.get("arguments", {})
            handlers = {
                "identity.issue": lambda: ca.issue_identity(**a),
                "identity.verify": lambda: ca.verify_identity(**a),
                "identity.revoke": lambda: ca.revoke_identity(**a),
                "identity.list": lambda: ca.list_identities(a.get("tenant", "")),
            }
            h = handlers.get(tn)
            if h:
                try:
                    r = h()
                    send_jsonrpc({"jsonrpc": "2.0", "id": msg["id"],
                                  "result": {"content": [{"type": "text", "text": json.dumps(r)}]}})
                except Exception as e:
                    send_jsonrpc({"jsonrpc": "2.0", "id": msg["id"],
                                  "result": {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}})
```

**CLI命令** (`agora identity` 子命令):
```python
def cmd_identity(args):
    ca = IdentityCA()
    if args.identity_cmd == "init":
        ref = ca.init_ca()
        print(f"CA initialized: {ref}")
    elif args.identity_cmd == "issue":
        r = ca.issue_identity(args.subject, args.type, args.tenant, args.expires)
        print(f"Issued: {r['subject_id']}")
        print(f"Secret: {r['proof_secret']}  (show once!)")
    elif args.identity_cmd == "verify":
        r = ca.verify_identity(args.subject)
        print(f"Valid: {r['valid']}" + (f" ({r['reason']})" if not r['valid'] else ""))
    elif args.identity_cmd == "revoke":
        ca.revoke_identity(args.subject)
        print(f"Revoked: {args.subject}")
```

**验证**:
```bash
python3 -c "
import sys; sys.path.insert(0, '~/Workspace/agora/src')
from agora.identity_ca import IdentityCA
ca = IdentityCA()
ref = ca.init_ca()
print(f'CA: {ref}')
r = ca.issue_identity('user:测试用户', 'user', 'starlink-core', 30)
print(f'Issued: {r[\"subject_id\"]}, secret available')
v = ca.verify_identity('user:测试用户')
assert v['valid'], f'Verify failed: {v}'
print('T123: ALL PASSED')
" 2>&1
```

**验收**:
```
☐ IdentityCA 能签/验/销身份
☐ identity MCP Server 正常运行
☐ 注册到Agora (agora add-route --tool "identity.*" --service "identity-ca")
☐ prove_secret只显示一次
```

---

### T124: Hermes携带身份凭证

**目标**: Hermes调用MCP时携带IdentityEnvelope，Agora中间件解析身份。

**文件**: `~/.hermes/adapters/identity_middleware.py`

```python
"""Identity Middleware — Hermes MCP调用时注入身份凭证。"""

import json
from pathlib import Path

IDENTITY_CACHE = Path.home() / ".kos" / "identities.json"

def load_identity() -> dict:
    if IDENTITY_CACHE.exists():
        return json.loads(IDENTITY_CACHE.read_text())
    return {
        "subject_id": "agent:hermes",
        "subject_type": "agent",
        "issuer": "ca:agora.starlink.local",
        "tenant": "starlink-core",
    }

def inject_identity_header(headers: dict = None) -> dict:
    identity = load_identity()
    headers = headers or {}
    headers["X-Identity-Subject"] = identity.get("subject_id", "")
    headers["X-Identity-Tenant"] = identity.get("tenant", "")
    headers["X-Identity-Issuer"] = identity.get("issuer", "")
    return headers

# 在Hermes call_tool时调用:
# mcp_call(tool, args, headers=inject_identity_header())
```

**验证**:
```bash
python3 -c "
from hermes.adapters.identity_middleware import inject_identity_header
h = inject_identity_header()
assert 'X-Identity-Subject' in h
print(f'Identity: {h[\"X-Identity-Subject\"]} @ {h[\"X-Identity-Tenant\"]}')
print('T124: OK')
" 2>&1
```

**验收**:
```
☐ 每个MCP调用携带X-Identity-*头
☐ Hermes启动时加载身份文件
☐ KOS/Agora能解析身份头
```

---

## Wave 9.2 — CapabilityGrant 可执行 (2周, 3 Tasks)

### T125: CapabilityGrant Schema

**文件**: `~/Workspace/eidos/schemas/capability-grant.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://workspace.local/contracts/capability-grant.schema.json",
  "title": "CapabilityGrant",
  "description": "谁有权限以什么范围调用什么能力。",
  "type": "object",
  "required": ["grant_id", "subject", "capability"],
  "properties": {
    "grant_id": {
      "type": "string",
      "pattern": "^grant:[a-z0-9-]+$"
    },
    "subject": {
      "type": "string",
      "description": "被授权者ID (user/agent/org)"
    },
    "capability": {
      "type": "string",
      "description": "能力标识，如 minerva.research、collab.*"
    },
    "resource_scope": {
      "type": "string",
      "description": "资源范围，如 project:joint-research、org:partner"
    },
    "constraints": {
      "type": "object",
      "properties": {
        "max_cost_usd": { "type": "number" },
        "max_calls": { "type": "integer" },
        "expire_at": { "type": "string", "format": "date-time" }
      }
    },
    "issued_by": {
      "type": "string",
      "description": "签发者CA标识"
    },
    "issued_at": { "type": "string", "format": "date-time" },
    "revoked": { "type": "boolean", "default": false },
    "revoked_at": { "type": "string", "format": "date-time" }
  }
}
```

**验证**: Schema语法校验同T122。

---

### T126: Agora授权门禁中间件

**文件**: `~/Workspace/agora/src/agora/authorizer.py`

**核心**:
- 在路由前检查：当前请求的subject是否有CapabilityGrant
- 无对应grant → 403
- grant过期/吊销 → 403
- grant约束(成本/调用次数) → 达到上限后拒绝

```python
"""Agora Authorizer — 在路由前校验CapabilityGrant。"""

import json
import time
from pathlib import Path
from agora.persistence_db import _get_db

GRANTS_DB = Path.home() / ".kos" / "grants.db"

class Authorizer:
    def __init__(self, db_path: str = None):
        self._db_path = db_path or str(GRANTS_DB)
        self._ensure_schema()
    
    def _ensure_schema(self):
        conn = _get_db(self._db_path)
        conn.execute("""
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
            )
        """)
        conn.commit()
    
    def create_grant(self, subject: str, capability: str,
                     resource_scope: str = "", constraints: dict = None,
                     issued_by: str = "ca:agora.starlink.local") -> dict:
        import secrets
        conn = _get_db(self._db_path)
        grant_id = f"grant:{secrets.token_hex(8)}"
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT INTO grants (grant_id, subject, capability, resource_scope, constraints, issued_by, issued_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (grant_id, subject, capability, resource_scope,
             json.dumps(constraints or {}), issued_by, ts),
        )
        conn.commit()
        return {"grant_id": grant_id, "subject": subject, "capability": capability}
    
    def check_call(self, subject: str, tool: str, cost: float = 0) -> dict:
        """路由前校验。返回allowed/denied + reason。"""
        conn = _get_db(self._db_path)
        
        # 1. 找匹配的grant
        rows = conn.execute(
            "SELECT * FROM grants WHERE subject = ? AND revoked = 0",
            (subject,),
        ).fetchall()
        
        applicable = []
        for row in rows:
            cols = ["grant_id","subject","capability","resource_scope",
                    "constraints","issued_by","issued_at","revoked",
                    "revoked_at","call_count","total_cost"]
            g = dict(zip(cols, row))
            g["constraints"] = json.loads(g["constraints"])
            
            # 匹配capability (支持通配符)
            cap = g["capability"]
            if cap == "*" or cap == tool or (cap.endswith(".*") and tool.startswith(cap[:-2])):
                applicable.append(g)
        
        if not applicable:
            return {"allowed": False, "reason": f"No grant for {subject} to call {tool}"}
        
        # 2. 检查约束
        for g in applicable:
            cons = g["constraints"]
            if cons.get("expire_at") and cons["expire_at"] < time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()):
                continue  # 过期的grant跳过
            if cons.get("max_calls") and g["call_count"] >= cons["max_calls"]:
                continue
            if cons.get("max_cost_usd") and g["total_cost"] >= cons["max_cost_usd"]:
                continue
            
            # 更新计数器
            conn.execute(
                "UPDATE grants SET call_count = call_count + 1, total_cost = total_cost + ? WHERE grant_id = ?",
                (cost, g["grant_id"]),
            )
            conn.commit()
            return {"allowed": True, "grant_id": g["grant_id"]}
        
        return {"allowed": False, "reason": "All applicable grants exceeded constraints"}
    
    def revoke_grant(self, grant_id: str) -> bool:
        conn = _get_db(self._db_path)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute("UPDATE grants SET revoked = 1, revoked_at = ? WHERE grant_id = ?", (ts, grant_id))
        conn.commit()
        return True
    
    def list_grants(self, subject: str = "") -> list[dict]:
        conn = _get_db(self._db_path)
        if subject:
            rows = conn.execute("SELECT * FROM grants WHERE subject = ?", (subject,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM grants").fetchall()
        cols = ["grant_id","subject","capability","resource_scope",
                "constraints","issued_by","issued_at","revoked","revoked_at","call_count","total_cost"]
        result = []
        for r in rows:
            d = dict(zip(cols, r))
            d["constraints"] = json.loads(d["constraints"])
            result.append(d)
        return result

def authorize_middleware(subject: str, tool: str, cost: float = 0) -> dict:
    """在路由前调用的门禁中间件"""
    az = Authorizer()
    return az.check_call(subject, tool, cost)
```

**Agora Router集成**: 在`router.py`的`route_call`开头，先调`authorize_middleware()`，如果denied直接返回403。

```python
# 在 route_call 开头插入:
from agora.authorizer import authorize_middleware
auth = authorize_middleware(subject, tool_name)
if not auth["allowed"]:
    return {"error": f"403 Forbidden: {auth['reason']}"}
```

**验证**:
```bash
python3 -c "
import sys; sys.path.insert(0, '~/Workspace/agora/src')
from agora.authorizer import Authorizer
az = Authorizer()
az.create_grant('user:老王', 'collab.*')
r = az.check_call('user:老王', 'collab.create_task')
assert r['allowed'], f'Expected allowed: {r}'
print(f'Check: {r}')
r2 = az.check_call('user:unknown', 'collab.create_task')
assert not r2['allowed']
print(f'Denied: {r2}')
print('T126: ALL PASSED')
" 2>&1
```

**验收**:
```
☐ Authorizer能创建/校验/吊销grant
☐ Router集成：denied返回403
☐ 成本计数器在grant上自增
☐ 通配符capability匹配 (collab.*)
```

---

### T127: grant签发/吊销CLI

**文件**: `~/Workspace/agora/src/agora/cli/commands_grant.py`

```python
def cmd_grant(args):
    from agora.authorizer import Authorizer
    az = Authorizer()
    if args.grant_cmd == "create":
        r = az.create_grant(args.subject, args.capability, args.scope, args.constraints)
        print(f"Grant created: {r['grant_id']}")
        print(f"  {r['subject']} → {r['capability']}")
    elif args.grant_cmd == "revoke":
        az.revoke_grant(args.grant_id)
        print(f"Revoked: {args.grant_id}")
    elif args.grant_cmd == "list":
        grants = az.list_grants(args.subject)
        for g in grants:
            status = "REVOKED" if g["revoked"] else "active"
            print(f"  {g['grant_id']:25s} {g['subject']:20s} {g['capability']:20s} {status}")
    elif args.grant_cmd == "check":
        r = az.check_call(args.subject, args.tool)
        print(f"{'✅ ALLOWED' if r['allowed'] else '❌ DENIED'}: {r.get('reason', '')}")
```

**集成到Agora CLI**: 注册为 `agora grant create/revoke/list/check`。

---

## Wave 9.3 — 跨组织协作 (2周, 3 Tasks)

### T128: visibility_scope执行

**当前**: KOS collab的`create_task`已接受`visibility_scope`参数（`private/team/org/public`），但`list_tasks`和`get_task`不做scope过滤。

**改动**: 在`collab/api.py`中：
1. `list_tasks()`加`visibility_scope`过滤参数
2. `get_task()`校验调用者scope
3. 新增`update_visibility(task_id, scope)` API

```python
# 在list_tasks中增强过滤
def list_tasks(status: str = "", creator: str = "",
               visibility_scope: str = "",  
               viewer_subject_id: str = "",
               limit: int = 20) -> list[dict]:
    conn = _get_db()
    _ensure_table(conn)
    query = "SELECT * FROM kos_collab_tasks WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if creator:
        query += " AND creator=?"
        params.append(creator)
    if visibility_scope:
        query += " AND visibility_scope=?"
        params.append(visibility_scope)
    elif viewer_subject_id:
        # 非管理员只看自己能见的
        query += " AND (creator=? OR visibility_scope IN ('public', 'org'))"
        params.extend([viewer_subject_id])
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    ...
```

**MCP工具新增**:
```python
"collab.update_visibility": {
    "description": "修改Task的可见范围",
    "inputSchema": {"type": "object", "properties": {
        "task_id": {"type": "string"},
        "visibility_scope": {"type": "string", "enum": ["private", "team", "org", "public"]},
    }, "required": ["task_id", "visibility_scope"]},
}
```

**验证**:
```bash
python3 -c "
from kos.collab.api import create_task, list_tasks, update_task
t = create_task('跨组织测试', '验证scope', 'user:老王', visibility_scope='public',
                subtasks=[{'id':'s1','title':'外部参与','status':'pending','tags':['research']}])
print(f'Task: {t[\"task_id\"]} scope={t[\"visibility_scope\"]}')
tasks = list_tasks(visibility_scope='public')
assert any(t2['task_id'] == t['task_id'] for t2 in tasks), 'public list failed'
print('T128: ALL PASSED')
" 2>&1
```

---

### T129: 跨组织Task E2E

**目标**: 外部组织（非starlink-core）的Agent能发现public Task并认领。

**场景**:
```
组织A (starlink-core):   创建public Task "联合研究报告"
  ├── subtask: research (tags: [research]) → Hermes认领
  └── subtask: review   (tags: [review])   → 外部Agent认领

组织B (partner-org):     安装kos MCP → list_tasks(scope=public)
  → 发现有可用subtask → claim_subtask(task_id, subtask_id="review", assignee="agent:partner-bot")
  → 完成 → add_artifact → complete_subtask
```

**验证**:
```bash
# E2E脚本见phase9_e2e_test.py (同Phase 8模式)
python3 -c "
# 模拟跨组织Task
from kos.collab.api import create_task, list_tasks, claim_subtask, complete_subtask, add_artifact
import sys

# Step 1: 组织A创建public Task
t = create_task('跨组织研究报告', '验证外部Agent可认领', 'user:老王',
                visibility_scope='public',
                subtasks=[
                    {'id':'research','title':'调研','status':'pending','tags':['research']},
                    {'id':'review','title':'同行评审','status':'pending','tags':['review']},
                ])
task_id = t['task_id']
print(f'[A] Created: {task_id}')

# Step 2: 外部Agent发现
tasks = list_tasks(visibility_scope='public')
found = [ti for ti in tasks if ti['task_id'] == task_id]
assert len(found) == 1, f'Task not found by external agent: {found}'
print(f'[B] External agent found task: {found[0][\"title\"]}')

# Step 3: 外部Agent认领+完成
r = claim_subtask(task_id, subtask_id='review', assignee='agent:partner-bot')
print(f'[B] Claimed: {r.get(\"status\", \"\")}')

r = complete_subtask(task_id, subtask_id='review', assignee='agent:partner-bot',
                     output='/tmp/review-report.md')
print(f'[B] Completed: {r.get(\"subtask_id\", \"\")}')

# Step 4: 组织A验证
from kos.collab.api import get_task
final = get_task(task_id)
progress = final.get('progress', 0)
print(f'[A] Task progress: {progress}%')
assert progress > 0
print('T129: ALL PASSED')
" 2>&1
```

**验收**:
```
☐ public Task能被外部Agent发现
☐ 外部Agent能认领并完成subtask
☐ 组织A能看到进度更新
☐ E2E脚本全部通过
```

---

### T130: 跨组织Resource Accounting

**目标**: 跨组织调用时，成本归集到各自usage.db，汇总报告按组织分开。

**文件**: `~/Workspace/scripts/cost-track-org.py`

```python
"""跨组织成本追踪 — 在现有usage.db基础上加org字段。"""
import sqlite3, json
from pathlib import Path

USAGE_DB = Path.home() / ".kos" / "usage.db"

def _ensure_org_column():
    conn = sqlite3.connect(str(USAGE_DB))
    # 尝试加列（幂等）
    try:
        conn.execute("ALTER TABLE usage ADD COLUMN org TEXT DEFAULT 'starlink-core'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 已存在
    return conn

def log_call(agent: str, tool: str, cost: float, tokens: int = 0,
             org: str = "starlink-core"):
    conn = _ensure_org_column()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO usage (timestamp, agent, tool, tokens, cost, org) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, agent, tool, tokens, cost, org),
    )
    conn.commit()
    conn.close()

def cost_summary_by_org(days: int = 7):
    conn = sqlite3.connect(str(USAGE_DB))
    rows = conn.execute(
        "SELECT org, COUNT(*) as calls, SUM(cost) as total_cost, SUM(tokens) as total_tokens "
        "FROM usage WHERE timestamp > datetime('now', ?) "
        "GROUP BY org ORDER BY total_cost DESC",
        (f'-{days} days',),
    ).fetchall()
    conn.close()
    result = []
    for org, calls, cost, tokens in rows:
        result.append({
            "org": org,
            "calls": calls,
            "cost": round(cost or 0, 4),
            "tokens": tokens or 0,
        })
    return result
```

**验证**:
```bash
python3 -c "
import sys; sys.path.insert(0, '~/Workspace/scripts')
from cost_track_org import log_call, cost_summary_by_org

log_call('agent:partner-bot', 'collab.claim_subtask', 0.001, 500, org='partner-org')
log_call('agent:hermes', 'research', 0.05, 5000, org='starlink-core')

summary = cost_summary_by_org(days=7)
for s in summary:
    print(f\"  {s['org']:20s} cost: \${s['cost']:.4f}  calls: {s['calls']}  tokens: {s['tokens']}\")
assert len(summary) >= 2, f'Expected 2 orgs, got {len(summary)}'
print('T130: ALL PASSED')
" 2>&1
```

---

## Wave 9.4 — 生态宪法 (2周, 3 Tasks)

### T131: 生态宪法文档

**文件**: `~/Documents/基建架构/10-生态宪法-最小互通协议.md`

**内容提纲**:
```markdown
# 生态宪法 — 最小互通协议

## 一、参与节点类型
- Full Node: 完整4+1+3架构实例（如starlink-core）
- Light Node: 仅有Agent能力，无OS基础设施（如个人开发者单机）
- External Node: 非Workspace体系的外部系统（如GitHub Actions）
- Human Node: 人类操作员

## 二、核心协议
1. Identity Protocol — 身份凭证签发与验证（Wave 9.1成果）
2. Capability Protocol — 能力授权与审计（Wave 9.2成果）
3. Task Protocol — 跨组织任务创建与认领（Wave 9.3成果）
4. Event Protocol — 事件订阅与推送（复用Agora EventBus）

## 三、发现机制
- 每个Agora实例公开AgentCard（A2A规范）
- 静态对等列表（配置驱动，bootstrapping阶段）
- 通过跨Agora事件同步状态

## 四、互通约束
- 最小共识：只需所有节点实现Identity+T two协议即可互通
- 可选增强：Capability+Task+Event是可选的
- 版本协商：调用时声明协议版本，回退到共同支持的版本

## 五、治理
- 生态入口文档（本文件）
- 变更流程：提出PR→公示期→评审→合并
- 分歧解决：保留到组织级别的共识（X3 Consensus的递归模型）
```

---

### T132: 节点类型定义

**文件**: `~/Workspace/eidos/schemas/node-type.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://workspace.local/contracts/node-type.schema.json",
  "title": "NodeType",
  "description": "生态中参与节点的类型与能力描述",
  "type": "object",
  "required": ["node_id", "node_type", "capabilities"],
  "properties": {
    "node_id": { "type": "string", "pattern": "^node:[a-z0-9_-]+$" },
    "node_type": { "type": "string", "enum": ["full", "light", "external", "human"] },
    "capabilities": {
      "type": "array",
      "items": { "type": "string" },
      "description": "支持的协议列表"
    },
    "endpoint_url": { "type": "string" },
    "a2a_endpoint": { "type": "string" },
    "identity_ref": { "type": "string", "description": "该节点的身份凭证ID" },
    "owner": { "type": "string", "description": "所属组织" },
    "version": { "type": "string" }
  }
}
```

---

### T133: 异构节点Adapter模板

**文件**: `~/Workspace/agora/src/agora/adapters/node_adapter.py`

**目标**: 提供一个Adapter基类，外部系统只需实现4个方法就能接入联邦。

```python
"""异构节点Adapter模板 — 外部系统接入联邦只需实现4个接口。"""

from abc import ABC, abstractmethod
from typing import Any


class NodeAdapter(ABC):
    """外部节点Adapter基类。
    
    外部系统继承此class，实现4个抽象方法即可接入生态。
    """
    
    @abstractmethod
    def get_node_info(self) -> dict:
        """返回节点基本信息（node_id, type, capabilities）。"""
        ...
    
    @abstractmethod
    def call_tool(self, tool: str, args: dict) -> dict:
        """调用外部节点的能力。"""
        ...
    
    @abstractmethod
    def submit_task(self, task_data: dict) -> dict:
        """向外部节点提交一个Task。"""
        ...
    
    @abstractmethod
    def get_task_status(self, task_id: str) -> dict:
        """查询外部节点上Task的状态。"""
        ...
    
    def health_check(self) -> bool:
        """可选：健康检查，默认返回True。"""
        return True


# ── 完整节点Adapter示例 ──

class FullNodeAdapter(NodeAdapter):
    """接入一个完整的4+1+3架构节点（如starlink-core）。"""
    
    def __init__(self, node_id: str, endpoint: str, a2a_endpoint: str = ""):
        self.node_id = node_id
        self.endpoint = endpoint
        self.a2a_endpoint = a2a_endpoint or f"{endpoint}/mcp"
    
    def get_node_info(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": "full",
            "capabilities": ["identity", "capability", "task", "event", "knowledge"],
            "endpoint_url": self.endpoint,
            "a2a_endpoint": self.a2a_endpoint,
        }
    
    def call_tool(self, tool: str, args: dict) -> dict:
        import json
        from urllib import request
        payload = json.dumps({"tool": tool, "arguments": args}).encode()
        req = request.Request(
            f"{self.endpoint}/api/call",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    
    def submit_task(self, task_data: dict) -> dict:
        # 完整节点走MCP创建Task
        return self.call_tool("collab.create_task", {
            "title": task_data["title"],
            "goal": task_data.get("goal", ""),
            "creator": task_data.get("creator", "agent:external"),
            "visibility_scope": "public",
            "subtasks": task_data.get("subtasks", []),
        })
    
    def get_task_status(self, task_id: str) -> dict:
        return self.call_tool("collab.get_task", {"task_id": task_id})


# ── 外部系统Adapter示例（GitHub Actions） ──

class GitHubActionsAdapter(NodeAdapter):
    """接入GitHub Actions作为外部节点。"""
    
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token
    
    def get_node_info(self) -> dict:
        return {
            "node_id": f"node:github-{self.repo.replace('/', '-')}",
            "node_type": "external",
            "capabilities": ["task", "ci_cd"],
            "endpoint_url": f"https://api.github.com/repos/{self.repo}",
            "owner": "github",
        }
    
    def call_tool(self, tool: str, args: dict) -> dict:
        # 映射到GitHub API
        import json
        from urllib import request
        if tool == "github.dispatch_workflow":
            url = f"https://api.github.com/repos/{self.repo}/actions/workflows/{args['workflow_id']}/dispatches"
            payload = json.dumps({"ref": args.get("ref", "main")}).encode()
            req = request.Request(url, data=payload, method="POST",
                                  headers={"Authorization": f"Bearer {self.token}",
                                           "Accept": "application/vnd.github.v3+json"})
            resp = request.urlopen(req, timeout=30)
            return {"status": "dispatched"}
        return {"error": f"unknown tool: {tool}"}
    
    def submit_task(self, task_data: dict) -> dict:
        return {"task_id": None, "fallback": "not supported"}
    
    def get_task_status(self, task_id: str) -> dict:
        return {"status": "unknown"}
```

**验证**:
```bash
python3 -c "
import sys; sys.path.insert(0, '~/Workspace/agora/src')
from agora.adapters.node_adapter import FullNodeAdapter, GitHubActionsAdapter

# 完整节点测试
full = FullNodeAdapter('node:test', 'http://localhost:7430')
info = full.get_node_info()
assert info['node_type'] == 'full'
assert 'identity' in info['capabilities']
print(f'Full node: {info[\"node_id\"]} capabilities={info[\"capabilities\"]}')

# 外部节点测试
gh = GitHubActionsAdapter('user/repo', 'fake-token')
gh_info = gh.get_node_info()
assert gh_info['node_type'] == 'external'
print(f'External node: {gh_info[\"node_id\"]} capabilities={gh_info[\"capabilities\"]}')

print('T133: ALL PASSED')
" 2>&1
```

---

## 门禁条件

```
☐ IdentityEnvelope Schema定稿 + CA签发/验/销全链路
☐ Hermes携带身份凭证（X-Identity-*头）
☐ CapabilityGrant Schema定稿 + Authorizer中间件
☐ Agora路由前校验grant（denied → 403）
☐ grant创建/吊销CLI
☐ visibility_scope执行（过滤+更新）
☐ 跨组织Task E2E（外部Agent发现→认领→完成）
☐ 跨组织成本归集
☐ 生态宪法文档
☐ 节点类型定义 + Adapter模板
```

---

## TASK_POOL 映射

| ID | Task | Wave | 预估 | 依赖 |
|----|------|------|------|------|
| T122 | Eidos IdentityEnvelope Schema | 9.1 | 1天 | — |
| T123 | CA身份签发器（MCP+CLI） | 9.1 | 5天 | T122 |
| T124 | Hermes身份凭证注入 | 9.1 | 2天 | T123 |
| T125 | Eidos CapabilityGrant Schema | 9.2 | 1天 | — (可与9.1并行) |
| T126 | Agora Authorizer中间件 | 9.2 | 4天 | T125 |
| T127 | grant CLI | 9.2 | 2天 | T126 |
| T128 | visibility_scope执行+更新API | 9.3 | 3天 | T122 |
| T129 | 跨组织Task E2E | 9.3 | 4天 | T128+Authorizer |
| T130 | 跨组织成本归集 | 9.3 | 2天 | — |
| T131 | 生态宪法文档 | 9.4 | 2天 | T129 |
| T132 | 节点类型Schema+定义 | 9.4 | 1天 | T131 |
| T133 | 异构节点Adapter模板 | 9.4 | 4天 | T132 |

**总计**: 12 Tasks, 8周, ~2000LOC

> **健康评分目标**: Phase 9完成时总分≥85 (D1=95, D2=90, D5=90)
