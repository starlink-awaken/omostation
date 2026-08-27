---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: T123 — CA身份签发器

> 类型: P9 Task | 预估: 5天 | Wave: 9.1 | Phase: 9
> 前置: T122 (IdentityEnvelope Schema定稿)

## 一、目标

实现本地CA（Certificate Authority）模块，用于签发/验证/吊销身份凭证。每个身份凭证包含subject_id、subject_type、issuer、proof_ref、tenant等字段。

## 二、文件

### 2.1 `~/Workspace/agora/src/agora/identity_ca.py` — CA核心 (~150LOC)

**核心类 `IdentityCA`**:
- `__init__(db_path, ca_id)` — 初始化，传入数据库路径和CA标识
- `init_ca()` — 生成CA密钥对，返回公钥引用
- `issue_identity(subject_id, subject_type, tenant, expires_days)` — 签发身份
  - 写入SQLite `identities` 表
  - 生成HMAC proof，proof_secret只显示一次
  - 返回完整身份凭证字典
- `verify_identity(subject_id, proof_secret)` — 验证身份
  - 检查是否存在、是否被吊销、是否过期
  - 可选验证proof_secret
- `revoke_identity(subject_id)` — 吊销
- `list_identities(tenant)` — 列出

**数据库表**:
```sql
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
);

CREATE TABLE IF NOT EXISTS ca_keys (
    key_id TEXT PRIMARY KEY,
    secret_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);
```

**MCP stdio server** (`run_mcp_stdio()`):
- `identity.issue` → 签发身份
- `identity.verify` → 验证身份
- `identity.revoke` → 吊销身份
- `identity.list` → 列出凭证

参考 Phase 8 memory/skills MCP server 的 stdio loop 实现。

### 2.2 `~/Workspace/agora/src/agora/cli/commands_identity.py` — CLI命令 (~50LOC)

`agora identity init/issue/verify/revoke/list` 子命令。

在 `cli.py` 中注册。

### 2.3 注册到Agora

```bash
agora service register \
  --name "identity-ca" \
  --command "python3" \
  --args "-m agora.identity_ca"

agora add-route --tool "identity.*" --service "identity-ca"
```

## 三、验证

```bash
# 3.1 MCP stdio server 启动测试
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 -m agora.identity_ca 2>&1

# 3.2 单元测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/Workspace/agora/src')
from agora.identity_ca import IdentityCA
import tempfile, os

# 使用临时DB
db = tempfile.mktemp(suffix='.db')
ca = IdentityCA(db_path=db, ca_id='ca:test')
ref = ca.init_ca()
assert ref.startswith('hmac:'), f'CA init failed: {ref}'

r = ca.issue_identity('user:测试', 'user', 'starlink-core', 30)
assert r['subject_id'] == 'user:测试'
assert r['issuer'] == 'ca:test'
print(f'Issued: {r[\"subject_id\"]} proof_secret available')

v = ca.verify_identity('user:测试')
assert v['valid'], f'Verify failed: {v}'

v2 = ca.verify_identity('user:测试', r['proof_secret'])
assert v2['valid'], f'Verify with proof failed: {v2}'

ca.revoke_identity('user:测试')
v3 = ca.verify_identity('user:测试')
assert not v3['valid'], f'Revoke failed: {v3}'

identities = ca.list_identities()
print(f'Total identities: {len(identities)}')

os.unlink(db)
print('T123: ALL PASSED')
" 2>&1
```

## 四、验收

```
☐ IdentityCA能签发/验证/吊销身份凭证
☐ proof_secret只显示一次（show once模式）
☐ MCP stdio server正常运行
☐ identity.* 工具注册到Agora
☐ 单元测试全部通过
