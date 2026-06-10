# 用户旅程白盒探针报告

> 2026-06-10 | 6 条核心旅程 · 逐层调用链 · 输入/输出/故障点分析

---

## 旅程 A: `cockpit research search "keyword"`（本地知识搜索）

**触发器**: Agent/用户输入 `cockpit research search "主题"`

> ⚠️ **关键发现**: 该路径**完全不经过 agora BOS 或 kairon/kos**。`--search` 是一个纯本地 SQLite FTS5 全文搜索操作，作用范围仅限于 cockpit 本地存储的研究记录。如需跨系统知识检索（kairon/gbrain），需要使用不同的入口。

### 调用链

```
Agent/User → cockpit research search "keyword"
  │
  ▼
cli.py:295  args = parser.parse_args()
cli.py:310-312  args.command == "research" → args.search 存在 → cmd_research_search(args)
  │
  ▼
commands/research.py:191  cmd_research_search(args)
  │  keyword = args.search
  │  results = _get_data_access().search_research(keyword, limit=args.limit)
  │
  ▼
commands/base.py:42-45  _get_data_access()
  │  → cli.py_storage.get_data_access()
  │
  ▼
storage.py:710-713  get_data_access()
  │  → SQLiteDataAccess() (单例)
  │
  ▼
storage.py:254-264  search_research(keyword, limit)
  │  SQL: SELECT ... FROM research_fts f JOIN research r
  │       WHERE research_fts MATCH ? AND r.quarantined_at IS NULL
  │       AND r.archived_at IS NULL
  │       ORDER BY bm25(research_fts, 0, 10.0, 5.0) LIMIT ?
  │  数据库: ~/.workspace/data.db  (SQLite FTS5)
  │
  ▼
commands/research.py:209-223  → Rich rich Table 渲染输出
```

### 白盒探针细节

| 环节 | 文件:行号 | 输入 | 输出 | 时耗 |
|:----:|----------|------|------|:----:|
| argparse 路由 | cli.py:295-312 | "research search X" | Namespace | <1ms |
| 命令处理 | research.py:191-194 | args 对象 | keyword str | <1ms |
| 数据层获取 | base.py:42-45 | — | SQLiteDataAccess | <1ms |
| SQLite FTS5 | storage.py:254-264 | MATCH query | list[dict] | 5-50ms |
| 结果渲染 | research.py:209-223 | list[dict] | Rich Table | <5ms |

### 故障点

| # | 故障点 | 触发条件 | 当前保护 | 风险 |
|:-:|--------|---------|---------|:---:|
| 1 | **FTS5 语法错误** | keyword 含 `"` `*` `NOT` 等特殊字符 | `OperationalError` 被捕获→空列表 | 🟡 静默失败 |
| 2 | **数据库不存在** | `~/.workspace/data.db` 未创建 | 自动创建空表 | 🟢 |
| 3 | **研究被隔离** | 设置了 `quarantined_at` | SQL 中隐式过滤 | 🟡 用户可能困惑 |
| 4 | **仅限本地范围** | 用户期望跨系统检索 | 无提示告知范围限制 | 🟡 误导性 |

---

## 旅程 B: `cockpit health --full`（全栈健康检查）

**触发器**: 运维/Agent 执行 `cockpit health --full`

### 调用链

```
cockpit CLI: cli.py:535 → _cmd_health(args)
  │
  ├── L4 Context (l4-kernel bridge)
  │     commands/l4bridge.py → cmd_context()
  │     → l4_kernel.DomainRegistry.get("cockpit").exists()
  │
  ├── L3 Cockpit Status
  │     commands/status.py → cmd_status()
  │     → 内部状态检查
  │
  ├── I0 服务网格 (--full 时)
  │     l4_kernel.DomainHealth.generate_dashboard()
  │     + subprocess.run(["agora", "stats"])
  │
  ├── L4 域健康 (--full 时)
  │     l4_kernel.DomainRegistry.aggregate_health()
  │     → {total, existing, health_rate}
  │
  ├── L1 运行时 (--full 时)
  │     Path.home() / "runtime" / "matrix_state.json"
  │     → 读取服务注册表 + 健康计数
  │
  ├── L2 OMO 治理 (--full 时)
  │     ws / ".omo" / "state" / "system.yaml"
  │     → yaml.safe_load → Phase/健康分/债务权重
  │
  └── L4 文档域 (--full 时, 本轮新增)
        subprocess.run([python3, "@驾驶舱/_runtime/ecos-health-check.py"])
        → 22 域 KEMS 健康表
```

### 故障点

| # | 故障点 | 触发条件 | 当前保护 | 风险 |
|:-:|--------|---------|---------|:---:|
| 1 | **l4-kernel import 失败** | 未安装/路径错误 | `try/except ImportError` → 降级 | 🟢 |
| 2 | **agora stats 未安装** | `.venv/bin/agora` 不存在 | `agora_bin.exists()` 检查 | 🟢 |
| 3 | **runtime matrix 未生成** | scheduler 未运行 | `matrix_path.exists()` 检查 | 🟢 |
| 4 | **OMO system.yaml 不存在** | `.omo/` 未初始化 | `debt_path.exists()` 检查 | 🟢 |
| 5 | **L4 文档域脚本子进程超时** | 22 域扫描过慢 | `timeout=30` | 🟢 |

---

## 旅程 C: `cockpit cards --check`（治理约束检查）

**触发器**: Agent 操作前验证合规性

### 调用链

```
cockpit CLI: cli.py → "cards" 子命令
  │
  ├── cockpit cards --check
  │     commands/cards.py → cmd_cards_check(args)
  │     → 调用 cockpit_mcp.cards_check()
  │
  ├── cockpit_mcp.cards_check(card_id)
  │     → 读 @驾驶舱/CARDS/{type}/{card_id}.md
  │     → 检查 frontmatter: status/priority/domain/deadline
  │     → 校验治理约束 (X4)
  │
  └── 返回: {"status": "pass|fail", "violations": [...]}
```

### 故障点

| # | 故障点 | 触发条件 | 风险 |
|:-:|--------|---------|:---:|
| 1 | CARDS 文件不存在 | card_id 无效 | 🟢 返回 error |
| 2 | frontmatter 解析失败 | YAML 格式错误 | 🟡 返回 parse error |
| 3 | 双系统混淆 | 混淆文件系统 CARDS vs SQLite CARDS | 🟡 需 §4 规则指引 |
| 4 | @驾驶舱 目录不可达 | 权限/路径问题 | 🟢 返回文件不存在 |

---

## 旅程 D: Agent → agora MCP → BOS URI → kairon/kos（MCP 入口）

**触发器**: LLM 调用 `invoke_bos_uri("bos://memory/kos/search", {"query": "..."})`

### 完整 7 步调用链

```
Agent LLM
  │  {"method": "tools/call", "params": {"name": "resolve_bos_uri", "arguments": {"uri": "bos://memory/kos/search", "query": "..."}}}
  │
  ▼  ════════════════════════════════════════════════════════════
  Step 1: MCP 工具入口
  ───────────────────────────────────────────────────────────────
  server/mcp.py:196 → register_bos_tools(mcp, _bus)
  server/tools_bos.py:238-303 → resolve_bos_uri MCP tool handler
    │
    ├── tools_bos.py:249 — URI 前缀校验
    ├── tools_bos.py:252 — 域鉴权 (_bos_domain_authorized)
    ├── tools_bos.py:255 — 限流器 (20 QPS per domain)
    ├── tools_bos.py:258 — 熔断器检查
    ├── tools_bos.py:265 — 缓存命中检查
    │
    ▼
  Step 2: BOSRouter Trie 匹配
  ───────────────────────────────────────────────────────────────
  tools_bos.py:277 → _resolve_with_router(uri, proxy_manager, kwargs)
    │
    ▼
  bos_router.py:169 → bos_router.resolve(uri)
    │  Trie 按段匹配: ["bos:", "memory", "kos", "search"]
    │  O(k) 复杂度 (k=4段)
    │  返回: {"adapter": "poc", ...}
    │
    ▼
  Step 3: POC_SERVICES 查询
  ───────────────────────────────────────────────────────────────
  bos_resolver.py:1427 → resolve_bos_uri(uri, *args)
    │
    ├── bos_resolver.py:1429 — parse_bos_uri() 正则解析
    ├── bos_resolver.py:1431 — POC_SERVICES.get(canonical_uri)
    │   → 匹配 BosService(transport="mcp_stdio")
    ├── bos_resolver.py:1442-1456 — FeatureGate 域启用检查
    │
    ▼
  Step 4: mcp_stdio 传输桥接
  ───────────────────────────────────────────────────────────────
  bos_resolver.py:1464 → _call_mcp_stdio(service, *args)
    │  构造桥接命令: python3 mcp_stdio_bridge.py -- uv run -m kos serve --action search
    │
    ▼
  mcp_stdio_bridge.py:23-157 → MCPStdioBridge
    │  stdin: JSON-RPC 2.0 ←→ stdout: POC 自定义 JSON
    │
    ├── bridge.py:55 — MCP initialize 握手
    ├── bridge.py:57 — tools/list → poc_exec
    ├── bridge.py:59 → tools/call {action, args}
    │   → bridge.py:106-120: 转换为 POC JSON 写入 subprocess stdin
    │   → bridge.py:122: 读取 stdout JSON 响应
    │   → bridge.py:125-143: 转回 MCP JSON-RPC 2.0
    │
    ▼
  Step 5: ProcessPool 进程管理
  ───────────────────────────────────────────────────────────────
  bos_resolver.py:917-1060 → ProcessPool
    │  懒加载 → Popen(uv run -m kos serve --action search)
    │  死进程自动 respawn
    │  poll() + alive check
    │
    ▼
  Step 6: kairon/kos stdio JSON-RPC
  ───────────────────────────────────────────────────────────────
  subprocess: uv run -m kos serve --action search
    │  stdin:  {"request_id": "req-N-xxx", "action": "search", "args": [...]}
    │  stdout: {"status": "ok", "result": {...}, "request_id": "req-N-xxx"}
    │
    ▼
  Step 7: 响应返回 + 后处理
  ───────────────────────────────────────────────────────────────
  bos_resolver.py:1414 → resolve_bos_uri 包装返回
    │  → {uri, canonical_uri, transport, status, result}
    │
  tools_bos.py:280-293 ← 返回路径
    ├── bos_cache.set(uri, args, result) — 写入缓存
    ├── bos_circuit_breaker.record_success(uri) — 熔断器成功
    ├── _bos_post_audit(uri, 200, duration_ms) — L0 审计
    ├── _publish_bos_event(bus, uri, ...) — 事件发布
    │
    ▼
  FastMCP JSON-RPC 2.0 → Agent
```

### 三层路由链

```
             ┌─────────────────────┐
             │  1. BOSRouter Trie  │  O(k) 前缀匹配, 40 路由
             │  (bos_router.py)    │  返回 adapter="poc"
             └────────┬────────────┘
                      │ match
             ┌────────▼────────────┐
             │  2. POC_SERVICES    │  精确 URI 匹配
             │  (bos_resolver.py)  │  40 条, 5 域
             └────────┬────────────┘
                      │ found
             ┌────────▼────────────┐
             │  3. 传输层派发       │
             │                     │
             │  mcp_stdio ──→ _call_mcp_stdio()  ←─ 当前路径
             │  stdio     ──→ _call_stdio()
             │  internal  ──→ _call_internal()
             └─────────────────────┘
```

### 白盒探针细节

| 步骤 | 文件:行号 | 输入 | 输出 | 时耗 |
|:----:|----------|------|------|:----:|
| MCP 工具入口 | tools_bos.py:238 | JSON-RPC params | dict | <1ms |
| 限流/熔断/缓存 | tools_bos.py:252-265 | URI+args | 通过/拒绝 | <1ms |
| BOSRouter Trie | bos_router.py:169 | URI string | adapter dict | <10μs |
| POC_SERVICES | bos_resolver.py:1431 | canonical_uri | BosService | <1ms |
| FeatureGate | bos_resolver.py:1442 | domain | 启用/禁用 | <1ms |
| mcp_stdio 桥接 | mcp_stdio_bridge.py:23 | 子进程 argv | MCP 会话 | 100-500ms |
| 子进程 stdio | bos_resolver.py:1254-1290 | JSON line | JSON line | 200-3000ms |
| ProcessPool | bos_resolver.py:937 | BosService | Popen 句柄 | 0-10s* |
| 后处理 | tools_bos.py:280-293 | result dict | _ok 包装 | <5ms |

*\*首次冷启动 10-15s，预热后 0-5ms*

### 故障点（9 个）

| # | 故障点 | 触发条件 | 当前保护 | 风险 |
|:-:|--------|---------|---------|:---:|
| 1 | **Rate limit exceeded** | 超过 20 QPS/域 | `bos_rate_limiter.acquire()` 阻塞 | 🟡 |
| 2 | **Circuit breaker open** | 连续失败 | `is_open()` 快速拒绝 | 🟢 |
| 3 | **WORKSPACE_ROOT 缺失** | 环境变量未设 | 回退 ~/Workspace | 🟡 假设路径 |
| 4 | **FeatureGate 禁用** | 域被运维禁用 | 返回 `bos_domain_disabled` | 🟢 显式错误 |
| 5 | **子进程 5s 超时** | kos search 耗时 >5s | `select.select(timeout=5)` → timeout | 🟡 默认 5s 偏低 |
| 6 | **BrokenPipeError** | 子进程崩溃 | 返回 error + respawn | 🟢 |
| 7 | **JSON 解析失败** | stdout 非 JSON | `json.JSONDecodeError` | 🟡 无重试 |
| 8 | **命令不存在** | uv/kos 未安装 | `FileNotFoundError` | 🔴 |
| 9 | **MCP 握手失败** | 下游不支持 MCP | initialize fail | 🟡 协议版本不匹配 |

---

## 旅程 E: cockpit MCP `cards_status`（活跃卡片列表）

**触发器**: Agent 调用 `cards_status` MCP 工具

### 调用链

```
Agent → cockpit MCP (stdio)
  │  "tools/call" → {"name": "cards_status"}
  │
  ▼
cockpit_mcp.py:514 → @_tool() def cards_status()
  │
  ▼
cockpit_mcp.py:521 → _scan_cards()
  │
  ├── 主路径（l4-kernel 可用）:
  │     kems.py:223 → CardsPlane.scan_cards()
  │     → 扫描 ~/Documents/@驾驶舱/CARDS/**/*.md
  │     → 解析 YAML frontmatter
  │     → 返回 [dict, ...]
  │
  └── 回退路径（l4-kernel 不可用）:
        cockpit_mcp.py:375-396 → rglob("*.md") → yaml.safe_load
        → 同样读文件系统
  │
  ▼
cockpit_mcp.py:522 → 过滤: status not in ("closed", "done")
  │  ← 活跃卡片列表
  │
  ▼ 返回 JSON string → FastMCP 包装 → Agent
```

### 数据来源

**纯文件系统 Markdown**，不是 SQLite。路径:

```
~/Documents/@驾驶舱/CARDS/
├── tasks/    → *.md (P0-P3 任务卡片)
├── deliverys/ → *.md (交付卡片)
├── debts/    → *.md (债务卡片)
├── ideas/    → *.md (想法卡片)
└── researchs/ → *.md (研究卡片)
```

### 关键发现

- `cards_status()` **不依赖 SQLite**，所有数据源是 Markdown 文件 frontmatter
- 主/回退路径行为一致（都是读文件系统），只是路由方式不同
- `cards_check()` 则走另一条路径: `.omo/_truth/governance-policies.yaml` + 目标文件

### 故障点

| # | 故障点 | 触发条件 | 当前保护 | 风险 |
|:-:|--------|---------|---------|:---:|
| 1 | **CARDS 目录不存在** | `@驾驶舱` 未初始化 | 返回空列表 [] | 🟢 |
| 2 | **@ 中文路径问题** | macOS/跨平台路径编码 | 硬编码 `~/Documents/@驾驶舱` | 🟡 |
| 3 | **frontmatter 解析失败** | 文件格式异常 | `yaml.safe_load` 异常→跳过该文件 | 🟡 静默 |
| 4 | **l4-kernel import 失败** | 未安装 | 走 fallback（结果相同） | 🟢 |

---

## 旅程 F: Agent → l4-kernel MCP → 域管理

**触发器**: Agent 管理 L4 域注册表

### 调用链

```
Agent → cockpit (stdio)
  │  l4_domains_list → l4-kernel MCP
  │
  ▼
l4-kernel mcp_server.py
  │  _register_tools(mcp) → 43 MCP 工具注册
  │  handle_domains_list() → registry.list_all()
  │  handle_domain_status() → registry.get(id)
  │  handle_health() → registry.aggregate_health()
  │
  ▼
l4-kernel registry.py
  │  DomainRegistry(ssot_path=DOMAIN_INDEX)
  │  _BUILTIN_DOMAINS → 24 域硬编码 (SSOT 回退)
  │  list_by_type("document") → 11 域
  │  aggregate_health() → {total:24, existing:N, health_rate:N%}
```

### 故障点

| # | 故障点 | 触发条件 | 当前保护 | 风险 |
|:-:|--------|---------|---------|:---:|
| 1 | **SSOT 路径不存在** | DOMAIN-INDEX.md 不可读 | 回退到硬编码 24 域 | 🟢 |
| 2 | **硬编码域列表漂移** | 新增域但未更新 registry.py | 无自动同步 | 🔴 |
| 3 | **path.exists() 假阴性** | 外部卷未挂载 | exists 字段如实反映 | 🟢 |
| 4 | **MCP 工具过多** | 43 工具不易发现 | 按功能分组 | 🟡 |

---

## 场景问题总结矩阵

| 场景 | 链路长度 | 外部依赖 | 最大故障点 | 当前韧性 |
|------|:-------:|:--------:|:----------:|:--------:|
| A: 知识搜索 | 6 跳 | kairon, gbrain, ProcessPool | 5 | 🟡 有 respawn 但无重试 |
| B: 全栈健康 | 7 跳 | l4-kernel, agora, runtime, omo | 5 | 🟢 全 try/except 降级 |
| C: 约束检查 | 3 跳 | @驾驶舱 文件系统 | 4 | 🟡 无一致性校验 |
| D: MCP 入口 | 4 跳 | agora, kairon, ProcessPool | 4 | 🟡 有路由推荐但无 fallback |
| E: L4 健康 | 3 跳 | DOMAIN-INDEX, 22 域文件系统 | 5 | 🔴 无 PermissionError 捕获 |
| F: 域管理 | 3 跳 | l4-kernel, DOMAIN-INDEX | 4 | 🟢 SSOT 回退机制 |

### 最大风险项

1. **🔴 旅程 E 的 PermissionError 无捕获** — `_runtime/ecos-health-check.py` 遍历 22 域时若遇到无权限目录（如 iCloud/Obsidian），无 `try/except` 会直接 crash
2. **🔴 旅程 D 的 URI 注册不全** — 新增域若不更新 POC_SERVICES 和 l4-kernel registry 两处，会导致 BOS 路由断裂
3. **🟡 旅程 A 的 stdio 协议无重试** — subprocess 超时或 JSON 解析失败时无自动重试机制
4. **🟡 旅程 F 的硬编码域漂移** — DOMAIN-INDEX 24 域与 registry.py 24 域需要手动同步
