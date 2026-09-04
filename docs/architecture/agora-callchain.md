---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-06
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ssot
last_updated: 2026-09-03
---
# I0 织层 — BOS URI 派发调用链

> 本文档白盒梳理 `agora` 作为 I0 织层时，一条 `bos://` URI 从 MCP 入口到后端服务执行的完整路径。
>
> 相关源码：
> - `projects/agora/src/agora/server/tools_bos/` (tools_bos.py 已拆分为子包, shim 保留 `server/tools_bos.py`)
> - `projects/agora/src/agora/mcp/bos_router.py`
> - `projects/agora/src/agora/mcp/resolver/api.py`
> - `projects/agora/src/agora/mcp/resolver/services.py`
> - `projects/agora/src/agora/mcp/resolver/adapter.py`
> - `projects/agora/src/agora/mcp/tools/bos_resolve.py`
> - `projects/agora/src/agora/server/mcp_entry.py` (P2-5 双进程统一, SSE 单一 owner)
>
> **2026-08-06 更新**: P1/P2 深化后调用链新增:
> - **进程模型**: SSE 进程作唯一 backend owner (`AGORA_GATEWAY_OWNER=1` → `_init_proxy` Phase 1.5 调 `mcp_gateway.start_all`), gateway 独立进程已废弃
> - **可观测**: `/health` (backends 从 registry._clients 真实计数) + `/metrics` (Prometheus)
> - **审计**: `AuditSubscriber` hashchain (prev_hash + SHA256) + `verify_chain` → `/health` audit_chain
> - **安全**: `/v1/backends/register` 复用 `require_agora_api_key` 认证 (P0-SEC)
> - **进程内调用**: `request_context.py` 抽象 fastmcp 私有 API, 无 HTTP 上下文放行 (本地受信任)

---

## 1. 核心参与者

| 组件 | 源码位置 | 职责 |
|:--|:--|:--|
| `resolve_bos_uri` MCP tool | `server/tools_bos/registration.py:121` | 统一入口，编排限流/熔断/缓存/路由 |
| `_bos_domain_authorized` | `server/tools_bos/_helpers.py:37` | 域级鉴权（CR-RBAC-01 / CR-DOMAIN-AUTH-01） |
| `bos_rate_limiter` | `server/mcp/bos_middleware.py` | 20 QPS/域 令牌桶限流 |
| `QuotaChecker` | `mcp/bos_quota.py` | per-caller 每日成本配额 (遗留-3) |
| `bos_circuit_breaker` | `server/mcp/bos_middleware.py` | 熔断器状态检查与记录 |
| `bos_cache` | `server/mcp/bos_middleware.py` | TTL 缓存 |
| `BOSRouter` / `bos_router` | `mcp/bos_router.py:27` | Trie 前缀索引，O(k) 最长前缀匹配 |
| `ProxyManager` | `server/mcp.py` + `auth/mcp_gateway.py` | MCP 下游代理管理 (P2-5: SSE 单一 owner) |
| `POC_SERVICES` | `mcp/resolver/services.py:51` | BOS 服务注册表 (见 project-registry.yaml: bos) |
| `resolve_bos_uri` (resolver API) | `mcp/resolver/api.py:96` | 异步解析，处理 internal/stdio transport |
| `StdioAdapter` | `mcp/resolver/adapter.py` | stdio 子进程调用封装 (P1: ProcessPool 复用) |
| `AuditSubscriber` | `server/mcp.py:289` | 审计事件订阅 (P2-2: hashchain) |
| `request_context` | `server/request_context.py` | fastmcp 私有 HTTP context 抽象 (P2-6) |
| `mof_agora_hook` | `projects/ecos/src/ecos/ssot/tools/mof_agora_hook.py` | L0 审计钩子 |

---

## 2. 九步路由链

```mermaid
sequenceDiagram
    participant C as MCP Client
    participant T as resolve_bos_uri<br/>tools_bos/registration.py
    participant A as _bos_domain_authorized
    participant R as bos_rate_limiter
    participant CB as bos_circuit_breaker
    participant CA as bos_cache
    participant BR as BOSRouter<br/>mcp/bos_router.py
    participant PM as ProxyManager
    participant API as resolver/api.py
    participant S as POC_SERVICES
    participant TP as StdioAdapter /
    Internal / HTTP
    participant L0 as mof_agora_hook

    C->>T: resolve_bos_uri(uri, arguments)

    T->>A: 1. 域鉴权 read/write
    A-->>T: ok / denied

    T->>R: 2. 限流 acquire(uri)
    R-->>T: ok / rate limit

    T->>CB: 3. 熔断检查 is_open(uri)
    CB-->>T: closed / open

    T->>CA: 4. 缓存查询 get(uri, args)
    CA-->>T: hit / miss

    alt cache miss
        T->>BR: 5. BOSRouter.resolve(uri)
        BR-->>T: route {adapter, prefix, config}

        alt adapter == poc
            T->>API: 6. resolve_bos_uri(uri, **args)
            API->>S: 7. get_service(uri)
            S-->>API: BosService
            API->>TP: 8. transport 执行
            TP-->>API: result
            API-->>T: result + transport
        else adapter == proxy
            T->>PM: proxy_manager.read_resource(uri)
            PM-->>T: contents
        else adapter == internal
            T->>API: importlib + func_name
            API-->>T: result
        end

        T->>CA: 缓存写入 set(uri, args, result)
        T->>CB: record_success(uri)
        T->>L0: 9. post_audit(uri, 200, duration)
        T->>T: _publish_bos_event(uri, "resolve", "ok")
    end

    T-->>C: {format_version, uri, source, result}
```

---

## 3. 每一步详解

### Step 1 — MCP 入口

```python
# projects/agora/src/agora/server/tools_bos/registration.py:121
@mcp.tool()
@bos_metrics.track("bos://")
async def resolve_bos_uri(uri: str, arguments: dict | str = "{}") -> dict:
```

- `arguments` 支持 dict 或 JSON 字符串；
- 工具挂载在全局 FastMCP 实例上，通过 `register_bos_tools(mcp, bus)` 注册；
- `bos_metrics.track` 自动统计调用延迟与成功率。

### Step 2 — 域鉴权

```python
# projects/agora/src/agora/server/tools_bos/_helpers.py:37
_bos_domain_authorized(uri, operation="read")
```

- **CR-RBAC-01**：`bos://capability/evaluator` 仅 `evaluator` 或 `admin` 角色可访问；
- **CR-DOMAIN-AUTH-01**：检查 URI 的 domain 是否在 `BOSRouter` 注册表中存在；
- 若未配置 `AGORA_API_KEY`，本地开发模式默认放行。

### Step 3 — 限流

```python
# projects/agora/src/agora/server/tools_bos/registration.py:272
if not bos_rate_limiter.acquire(uri):
    return _error(f"Rate limit exceeded for: {uri}")
```

- 默认 **20 QPS/域**；
- 基于令牌桶实现，超出阈值直接拒绝，避免下游被压垮。

### Step 3.5 — 配额 (遗留-3, 2026-08-07)

```python
# projects/agora/src/agora/server/tools_bos/registration.py:145
from agora.mcp.bos_quota import get_quota_checker
caller_id = agora_role_ctx.get() or "anonymous"
quota_ok, quota_info = get_quota_checker().check(caller_id, uri)
if not quota_ok:
    return _error(f"Quota exceeded for caller '{caller_id}': ...")
```

- **per-caller 每日成本上限** (USD), 配置在 `agora-bos-rates.yaml` `quotas:` 段
- caller_id 来自 `agora_role_ctx` (auth 已设), 匿名默认 2/天, agent-* 50/天
- 超限返回 429 语义错误 + audit 记录; 成功后 `get_quota_checker().record(...)` 记账
- 配置随 rates 热加载 (ConfigWatcher 5s)

### Step 3.6 — 统一告警 (P4, 2026-08-07)

- `mcp/agora_alerts.py` `send_alert()` — 统一 EventBus 事件 + 可选 webhook (`AGORA_ALERT_WEBHOOK`/`AGORA_QUOTA_WEBHOOK`, `is_safe_url` 校验) + Prometheus (`agora_alerts_total`)
- 告警源: 配额超限 (`quota:blocked`/`warning`)、熔断打开 (`circuit:open`)、健康降级 (`health:degraded`), 恢复时发 `recovered`
- 防抖: per-key 300s; blocked 状态翻转只发一次, 恢复后重置

### Step 3.7 — 能力目录写闭环 (P3, 2026-08-07)

- `mcp/capability_catalog.py` 补 `add()`/`retire()`/`save()` — 写回 `etc/bos-services.yaml` (保留原条目)
- 修复 `bos_capability_admit`/`bos_capability_retire` 死代码 (此前调 `add`/`save` 不存在 → AttributeError)
- 生命周期: admit (active) → 度量 (B1) → 语义路由 (B2) → retire (deprecated) 写回

### Step 4 — 熔断

```python
# projects/agora/src/agora/server/tools_bos/registration.py:275
if bos_circuit_breaker.is_open(uri):
    return _error(f"Circuit breaker open for: {uri}")
```

- 对连续失败的服务打开熔断；
- 成功调用后 `record_success`，失败后 `record_failure`。

### Step 5 — 缓存

```python
# projects/agora/src/agora/server/tools_bos/registration.py:282
cached = bos_cache.get(uri, args)
if cached:
    bos_circuit_breaker.record_success(uri)
    return _ok({...source: "cache"...})
```

- 命中缓存直接返回，跳过后续步骤；
- TTL 由 `_get_cache_ttl(uri)` 根据 URI 动态计算。

### Step 6 — BOSRouter 前缀匹配

```python
# projects/agora/src/agora/mcp/bos_router.py:169
def resolve(self, uri: str) -> dict[str, Any] | None:
    return self._trie_lookup(uri)
```

- 使用 **Trie** 索引，`O(k)` 复杂度，k = URI 段数；
- 合并了两张表：
  - `POC_SERVICES` 子进程路由（`adapter=poc`）；
  - `ProxyManager` MCP 代理路由（`adapter=proxy`）；
  - `internal` / `http` 路由。

URI 分段规则：

```python
# bos://memory/kos/search → ["bos:", "memory", "kos", "search"]
```

### Step 7 — 服务注册表查找

```python
# projects/agora/src/agora/mcp/resolver/api.py:96
async def resolve_bos_uri(uri: str, *args: Any, **kwargs: Any) -> dict:
    service = get_service(uri)
```

- `get_service` 在 `POC_SERVICES` 列表中精确匹配 URI；
- 支持 legacy URI alias 归一化（`normalize_bos_uri`）。

### Step 8 — Transport 执行

```python
# projects/agora/src/agora/mcp/resolver/api.py:103
if service.transport == "internal":
    mod = importlib.import_module(service.module_path)
    func = getattr(mod, service.func_name)
    raw = func(*args, **kwargs)
else:
    result = invoke_stdio(uri, *args, **kwargs)
```

| transport | 执行方式 | 示例 |
|:--|:--|:--|
| `internal` | 同进程 `importlib` | `bos://governance/omo/audit` |
| `stdio` | `uv run` 子进程 | `bos://memory/kos/search` |
| `mcp_stdio` | MCP Server 子进程 | `bos://l4-kernel/domains` |
| `http` | HTTP 调用 | 预留 |

`invoke_stdio` 最终调用 `StdioAdapter.call(service, ...)`，启动子进程并通过 stdin/stdout 进行 MCP JSON-RPC 通信。

**P1 优化 (ProcessPool)**: `mcp_stdio` transport 的调用经 `get_stdio_adapter()` 默认绑定全局 `ProcessPool`（`resolver/pool.py`），按 URI 复用常驻子进程，避免每次调用 Popen；进程死亡自动 respawn。`_call_mcp_stdio_pooled`（`adapter.py`）在 URI 锁保护下复用 session。

### Step 9 — L0 审计与事件

```python
# projects/agora/src/agora/server/tools_bos/_helpers.py:85
_bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
_publish_bos_event(bus, uri, "resolve", "ok", duration_ms)
```

- `mof_agora_hook.post_audit` 将调用记录写入 L0 审计日志；
- `_publish_bos_event` 发布到 `EventBus`，供 `omo_bos_metrics` 等 consumer 消费；
- 最终写入 `.omo/_knowledge/bos-metrics.jsonl`。

---

## 4. 韧性机制

| 故障场景 | 处理策略 | 代码位置 |
|:--|:--|:--|
| 下游 timeout / EOF | `StdioAdapter` 内自动重试 1 次 | `mcp/resolver/adapter.py` |
| JSON 解析失败 | 返回结构化错误，熔断器记失败 | `server/tools_bos/registration.py:311` |
| 连续失败 | 熔断器打开，后续请求快速失败 | `bos_circuit_breaker` |
| 缓存失效 | 回源调用，成功后重新写入 | `server/tools_bos/registration.py:297` |
| 限流命中 | 立即返回 `429` 语义错误 | `server/tools_bos/registration.py:273` |
| 域未注册 | 鉴权层返回 `Access denied` | `server/tools_bos/_helpers.py:88` |

---

## 5. 相关工具

- `bos_list()` — 列出所有注册服务（`mcp/tools/bos_resolve.py:53`）
- `list_bos_resources()` — 合并 BOSRouter + POC + ProxyManager 全量资源（`server/tools_bos/registration.py:435`）
- `protocol_self_check()` — 自检服务定义完整性（`mcp/resolver/api.py:84`）

### 5.1 能力市场工具链 (2026-08-08, agora 2bb13858)

> P0-P5 能力市场深化后, `bos_capability_lifecycle.py` 挂主 MCP 的能力治理工具:

| 工具 | 作用 | 定价/采购 |
|:--|:--|:--|
| `bos_capability_list(uri_prefix)` | 列出能力 + 生命周期 + **pricing** (P1 发现) | `resolve_pricing` 混合三层 |
| `bos_capability_admit(uri, desc)` | 采购: 身份校验 + **配额检查** + 采购事件 | `get_quota_checker().check` + `capability:admitted` 事件 |
| `bos_capability_retire(uri, reason)` | 退役能力 | lifecycle → retired |
| `bos_billing_statement(caller_id, period)` | 采购账单 (P2) | `ResourceAccountDB.get_calls` |
| `bos_market_overview()` | 市场总览 (P4): 能力数/定价分布/热度/成本 | `resolve_pricing` 聚合 |

> 调用链: HTTP `/v1/tools/call` → `mcp_entry.py:165` → `mcp.call_tool` → `bos_capability_*` → `bos_router` / `ResourceAccountDB` / `agora_alerts`。

