---
title: security-audit-report-phase2-red-team
type: doc
---

# 🔴 Kairon 项目 Phase 2 — 红队安全审计报告

**审计日期**: 2026-05-30
**审计范围**: `projects/kairon/packages/` — 19 个 Python 包
**审计者**: CodeBuddy Code (general-purpose-6)
**方法**: 静态代码分析，以攻击者视角审视 OWASP Top 10 + 常见漏洞模式

---

## 总体安全评分: **D** (存在多个 CRITICAL/HIGH 级问题)

---

## 发现汇总

| # | 严重度 | 包 | 文件 | 行号 | 漏洞类型 | CWE |
|---|--------|------|------|------|----------|-----|
| 1 | **CRITICAL** | agent-runtime | `tools.py` | 127 | 命令注入 | CWE-78 |
| 2 | **CRITICAL** | agent-runtime | `server.py` | 14-15, 38 | 身份认证缺失 | CWE-306 |
| 3 | **HIGH** | agent-runtime | `tools.py` | 230, 241 | SSRF | CWE-918 |
| 4 | **HIGH** | kos | `push_engine.py` | 25-29 | 代码注入 | CWE-94 |
| 5 | **HIGH** | kos | `pattern_learner.py` | 75-79 | 代码注入 | CWE-94 |
| 6 | **MEDIUM** | agent-runtime | `server.py` | 29 | CORS 缺失 | CWE-942 |
| 7 | **MEDIUM** | iris | `obsidian.py` | 113 | 路径遍历 | CWE-22 |
| 8 | **MEDIUM** | agent-runtime | `tools.py` | 143 | 资源耗尽 (DoS) | CWE-400 |
| 9 | **MEDIUM** | agent-runtime | `server.py` | 148-161 | 敏感信息泄露 | CWE-532 |
| 10 | **LOW** | eidos | `sharedbrain.py` | 166 | SQL 注入 | CWE-89 |
| 11 | **LOW** | cron-service | `db.py` | 131 | SQL 注入 | CWE-89 |
| 12 | **LOW** | kos | `collab/api.py` | 140 | SQL 注入 | CWE-89 |
| 13 | **LOW** | agora | `agent_registry.py` | 43-44 | 不安全文件存储 | CWE-377 |
| 14 | **INFO** | agent-runtime | `tools.py` | 263 | 硬编码敏感信息 | CWE-798 |

---

## 详细发现

### 🔴 CRITICAL-1: 命令注入 — `terminal_run` 工具 (CWE-78)

**文件**: `agent-runtime/src/agent_runtime/tools.py:122-134`
**描述**: `terminal_run` 方法使用 `subprocess.run(command, shell=True, ...)` 将用户输入的 `command` 字符串直接传递给 shell。此方法被暴露为一个 LLM 可调用的工具工具，攻击者可以通过构造恶意的 `command` 参数执行任意系统命令。

```python
# tools.py:126-128
r = subprocess.run(
    command,
    shell=True,
    capture_output=True,
    text=True,
    cwd=cwd or str(ECOS_DIR),
    timeout=timeout,
)
```

**利用场景**:
1. 攻击者发送请求到 Agent Runtime API (如 `/chat` 端点)
2. LLM 调用 `terminal_run` 工具，传入类似 `"cat ~/.ssh/id_rsa; rm -rf /"` 的命令
3. 命令直接传递给 shell 执行，无任何过滤

**修复建议**:
- 避免使用 `shell=True`，改用 `shlex.split(command)` 或直接传参列表
- 或实现对 `command` 的严格白名单过滤（仅允许特定命令）
- 考虑使用 `shlex.quote()` 对命令参数进行转义

---

### 🔴 CRITICAL-2: 身份认证缺失 (CWE-306)

**文件**: `agent-runtime/src/agent_runtime/server.py:14-15, 38`
**描述**: 当 `AGENT_RUNTIME_AUTH_TOKEN` 环境变量未设置时，认证中间件被完全绕过。这意味着所有端点（`/chat`, `/run-task`, `/logs` 等）可以无认证访问。

```python
# server.py:14-15 (中间件中)
if not AUTH_TOKEN:
    return  # 未配置 token 时跳过认证（兼容旧部署）

# server.py:38 (另一处认证检查)
if AUTH_TOKEN:
    ...  # 只有配置了 token 才检查
```

**利用场景**:
1. 默认部署中，`AGENT_RUNTIME_AUTH_TOKEN` 很可能未设置
2. 任意网络可达的攻击者 POST 到 `/chat` 或 `/run-task` 端点
3. 通过 LLM 工具链进一步调用 `terminal_run` 实现 RCE

**修复建议**:
- 移除"兼容旧部署"的跳过逻辑，默认要求认证
- 或当 token 未设置时生成一个随机 token 并打印到日志
- 考虑硬编码一个 fallback 认证机制（如双向 TLS）

---

### 🟠 HIGH-3: SSRF 服务端请求伪造 (CWE-918)

**文件**: `agent-runtime/src/agent_runtime/tools.py:230-238, 241-254`
**描述**: `http_get` 和 `http_post` 方法接受任意 URL 参数，无任何域名/IP 白名单过滤。攻击者可以利用此功能探测内部网络。

```python
# tools.py:230-236
def http_get(url: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")[:5000]
        return {"status": resp.status, "body": body}
```

**利用场景**:
1. 通过 `http_get("http://169.254.169.254/latest/meta-data/")` 获取云服务元数据
2. 探测内部服务：`http_get("http://localhost:7430/health")`
3. 扫描内网 IP：`http_get("http://10.0.0.1:22")`

**修复建议**:
- 实现 URL 白名单（仅允许外部公共 API 或特定内网服务）
- 或禁止对私有 IP 范围（127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16）的请求

---

### 🟠 HIGH-4: 代码注入 — f-string 嵌入子进程 (CWE-94)

**文件**: `kos/src/kos/push_engine.py:25-29`
**文件**: `kos/src/kos/pattern_learner.py:75-79`
**描述**: 通过 f-string 将变量嵌入 Python 代码字符串后，传递给 `subprocess.run(["python3", "-c", f"""..."""])`。`payload_json` 是 `json.dumps(rule)` 的结果，如果 `rule` 中的某个字段（如 `description`）包含恶意构造的字符串（包含 `'`, `)` 等），可能突破字符串边界执行任意代码。

```python
# push_engine.py:25-29
payload_json = json.dumps(rule)
subprocess.run(
    [
        "python3",
        "-c",
        f"""
import sys, json; sys.path.insert(0, '{hermes_src}')
from hermes_ops.events import emit
emit('RULE_GENERATED', {payload_json})
""",
    ],
    capture_output=True,
    timeout=5,
)
```

**利用场景**:
1. Pattern `description` 字段若来自外部输入，可构造 `description = "'); os.system('rm -rf /'); emit('"` 来突破
2. 虽然 `hermes_src` 是硬编码的 `~/Workspace/ops/src`，但代码注入路径是存在的

**修复建议**:
- 不要使用 `python3 -c` 的内联代码模式。改为编写一个固定的辅助脚本
- 或使用 `input=` 参数传入 JSON 数据，脚本从 stdin 读取
- 确保所有 f-string 嵌入的内容经过正确转义

---

### 🟡 MEDIUM-6: CORS 缺失 (CWE-942)

**文件**: `agent-runtime/src/agent_runtime/server.py:29`
**描述**: Agent Runtime FastAPI 应用未配置 CORSMiddleware。在浏览器环境中，跨域请求默认会被同源策略阻止，但攻击者可以寻找到绕过手段或利用其他攻击向量。

```python
app = FastAPI(title="Agent Runtime", version="1.0.0")
# 未添加 CORSMiddleware
```

相比之下，`minerva/web/app.py:61-67` 和 `agora/web/app.py:78-83` 都正确配置了 CORS。

**修复建议**:
- 添加 `CORSMiddleware`，限制 `allow_origins` 到已知前端地址

---

### 🟡 MEDIUM-7: 路径遍历 — Obsidian Connector (CWE-22)

**文件**: `iris/src/iris/connectors/obsidian.py:113`
**描述**: `_walk_md_files` 方法在拼接 `folder` 参数时未进行路径规范化检查。攻击者可以通过 `folder=../../etc` 尝试遍历到 vault 目录外。

```python
# obsidian.py:113
search_dir = (vault / folder) if folder else vault
```

虽然下游的 `relative_to(vault)` 会抛出 `ValueError` 终止遍历，但这本身就是一个 DoS 向量，且在某些实现中可能存在信息泄露。

**注意**: `get_item`（第 188-191 行）和 `_id_to_path`（第 287-289 行）**正确实现了**路径遍历检查，安全等级较高。

**修复建议**:
- 在 `_walk_md_files` 中加入类似 `get_item` 的 `resolve()` 和 `startswith()` 路径校验
- 添加 try/except 捕获 `ValueError` 避免因遍历而崩溃

---

### 🟡 MEDIUM-8: 资源耗尽 — 大文件读取 (CWE-400)

**文件**: `agent-runtime/src/agent_runtime/tools.py:143`
**描述**: `file_read` 方法使用 `p.read_text(encoding="utf-8")` 将整个文件读入内存，然后才截断到 10000 字符。如果一个文件大小为 GB 级别，会导致 OOM。

```python
# tools.py:143
return {"content": p.read_text(encoding="utf-8")[:10000]}
```

**利用场景**:
1. 如果攻击者控制的 LLM 调用 `file_read` 读取 `/var/log/system.log`（可能很大），会导致服务 OOM
2. 或者在 `ALLOWED_PATHS` 内的超大文件

**修复建议**:
- 使用流式读取，或预先检查文件大小：`p.stat().st_size > MAX_SIZE`
- 或使用 `p.open()` 分批读取

---

### 🟡 MEDIUM-9: 敏感信息泄露 — 日志端点 (CWE-532)

**文件**: `agent-runtime/src/agent_runtime/server.py:148-161`
**描述**: `/logs` 端点返回执行日志文件内容，日志中包含工具调用的输入输出。虽然日志路径在 AGENT_RUNTIME_DIR 下，但当认证缺失时（CRITICAL-2），攻击者可以获取所有执行历史。

```python
# server.py:153
lines = EXEC_LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
```

**修复建议**:
- 在返回日志前进行脱敏处理
- 或限制日志端点仅 admin 可访问
- 或默认禁用日志 API

---

### 🔵 LOW-10: SQL 注入 — 动态表名 (CWE-89)

**文件**: `eidos/src/eidos/adapters/sharedbrain.py:166`
**描述**: `SELECT * FROM [{table}]` 使用 f-string 拼接表名，虽然 table 来自 `sqlite_master`，但若攻击者可控制数据库文件内容，仍有注入风险。

```python
cursor.execute(f"SELECT * FROM [{table}]")  # noqa: S608
```

**文件**: `cron-service/src/cron_service/db.py:131`, `kos/src/kos/collab/api.py:140`
**描述**: 使用 f-string 拼接 UPDATE 的 SET 子句。

```python
# cron-service/db.py:131
conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
```

**修复建议**:
- 对 `{table}` 使用参数化查询（SQLite 不支持表名参数化，但可以对表名做白名单验证）
- 对动态 SET 子句使用白名单键名

---

### 🔵 LOW-13: 不安全文件存储 — 缓存路径可预测 (CWE-377)

**文件**: `agora/src/agora/agent_registry.py:43-44`
**描述**: Agent Registry 的缓存文件存储在 `/tmp/agent-registry-cache.json` 和 `/tmp/agent-registry-backup.json`。`/tmp` 在 Unix 系统上是全局可读的，可能导致 agent 信息泄露。

```python
CACHE_FILE = os.environ.get("AGENT_REGISTRY_CACHE", "/tmp/agent-registry-cache.json")
BACKUP_CACHE_FILE = os.environ.get("AGENT_REGISTRY_BACKUP_CACHE", "/tmp/agent-registry-backup.json")
```

**修复建议**:
- 改用 `~/.agora/` 或 `~/.cache/agora/` 等受限目录
- 或设置文件权限为 0600

---

### ℹ️ INFO-14: 硬编码 iLINK 接收者 (CWE-798)

**文件**: `agent-runtime/src/agent_runtime/tools.py:262-264`
**描述**: `send_message` 方法中硬编码了一个微信用户 ID 作为默认接收者。

```python
receiver = os.environ.get("ILINK_RECEIVER", "o9cq800tslBgu_e2s6YBCvkmHc2U@im.wechat")
```

**影响**: 如果 `ILINK_RECEIVER` 环境变量未设置，消息会自动发送到这个硬编码的默认用户。

---

## 安全亮点

以下模块经过审查后安全实现较好：

1. **Agora Governance (`governance.py`)**
   - SHA-256 哈希存储 API key secrets
   - 参数化 SQL 查询
   - 支持过期和吊销
   - Scope-based 权限检查

2. **Agent Registry (`agent_registry.py`)**
   - Ed25519 签名验证
   - 时间窗口防重放攻击（±30s 允许时钟偏差）
   - Per-identity 限额

3. **Minerva Web (`web/app.py` + `middleware.py`)**
   - `_safe_report_path` 路径遍历防护
   - 输入长度限制（InputGuardMiddleware）
   - 速率限制（RateLimitMiddleware）
   - 安全响应头
   - CORS 严格限制到 localhost
   - `sophia_compile` 输入截断到 500 字符

4. **Cron Service Executor (`executor.py`)**
   - 使用命令列表形式（无 `shell=True`）
   - 超时处理 + 进程组 kill
   - 路径解析脚本安全

5. **大多数 SQLite 操作使用参数化查询**（`?` 占位符）

---

## 修复优先级建议

| 优先级 | 问题 | 预估工作量 | 影响面 |
|--------|------|-----------|--------|
| P0 | CRITICAL-1: terminal_run 命令注入 | 2-4小时 | 直接 RCE |
| P0 | CRITICAL-2: Auth 缺失 | 1-2小时 | 完全绕过认证 |
| P1 | HIGH-3: SSRF | 2-4小时 | 内网探测 |
| P1 | HIGH-4/5: 代码注入 | 4-8小时 | 任意代码执行 |
| P2 | MEDIUM-6~9 | 各1-2小时 | 中等风险 |
| P3 | LOW-10~14 | 各0.5-1小时 | 低风险 |

---

## 结论

Kairon 项目的安全设计在核心加密和授权模块（Governance, Agent Registry, Minerva Web）上表现良好，但 **agent-runtime** 包存在两个 **CRITICAL** 级别的漏洞（命令注入 + 认证缺失），这两者组合可实现完全远程代码执行。此外，**kos** 包中的代码注入模式需要重构。

建议优先修复 P0/P1 问题后重新评估安全评分。
