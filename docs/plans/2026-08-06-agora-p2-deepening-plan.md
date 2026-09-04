---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# agora P2 + 深层落地方案 (2026-08-06)

> 基于 explore 深度调查 6 项问题的实施方案。先方案 → review → 执行。

## 目标
agora 生产就绪度提升：补齐可观测性/完整性/部署验证，修复两个深层架构缺陷。

## 改动范围与实施顺序

### P2-1: /metrics Prometheus exporter (agora, 低-中风险)
**现状**: `prometheus-client` 依赖已声明 (`pyproject.toml:30`) 但零使用；无 `/metrics` 路由；`metrics/collector.py` 是 JSON 存储非 Prometheus。
**改法**:
1. `src/agora/server/mcp_entry.py` `_register_common_routes()` 加 `/metrics` 路由:
   ```python
   from starlette.responses import Response
   async def metrics_endpoint(request):
       from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
       return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
   mcp._additional_http_routes.append(Route("/metrics", endpoint=metrics_endpoint))
   ```
2. `src/agora/mcp/bos_metrics.py` `record()` (L164) 挂 Prometheus 计数器:
   ```python
   from prometheus_client import Counter, Histogram
   BOS_CALLS_TOTAL = Counter("bos_calls_total", "BOS calls by prefix", ["prefix"])
   BOS_CALL_LATENCY = Histogram("bos_call_latency_seconds", "BOS call latency", ["prefix"])
   # record() 内: BOS_CALLS_TOTAL.labels(prefix).inc(); BOS_CALL_LATENCY.labels(prefix).observe(latency_ms/1000)
   ```
3. 清理死引用: `src/agora/tools/monitoring.py:92-134` daemon `/metrics` 拉取 (悬挂引用, 目标不存在) → 改为本地 `prometheus_client.generate_latest()` 或标记删除。
**风险**: 低。路由无副作用; hot path 埋点成本可忽略。

### P2-2: audit hashchain 防篡改 (agora, 中风险)
**现状**: `mcp.py AuditSubscriber` 表 (L301-307) 无 prev_hash; `on_event` (L340-373) 无哈希。
**改法**:
1. `_init_db` (L298): CREATE TABLE 加 `prev_hash TEXT NOT NULL DEFAULT ''` + `hash TEXT NOT NULL DEFAULT ''`; 对旧库 ALTER TABLE 兼容。
2. `on_event` (L340): 写入前 `SELECT hash FROM audit_log ORDER BY rowid DESC LIMIT 1` 取链尾; 计算:
   ```python
   import hashlib
   prev = tail_hash or "GENESIS"
   # canonical 纳入全字段 (id/timestamp/event_type/source/actor/resource/action/trace_id/payload/risk_level/duration_ms)
   canonical = f"{prev}|{event_id}|{ts}|{event_type}|{source}|{classified['actor']}|{classified['resource']}|{classified['action']}|{trace_id}|{payload_str}|{classified['risk_level']}"
   cur_hash = hashlib.sha256(canonical.encode()).hexdigest()
   ```
   INSERT 带 prev_hash=prev, hash=cur_hash。
3. 新增 `verify_chain()`: 从首行遍历重算比对连续性; **`prev_hash IN ('GENESIS','')` 的行视为锚点跳过哈希匹配** (兼容旧数据 + 清理边界)。
4. 与 `entropy_cleanup` (>30 天删除, tools_health.py:247) 协同: 删除会破链 → 清理时**只 UPDATE 边界行 prev_hash='GENESIS'** (同事务), 不重算 hash (verify 按锚点跳过)。
**风险**: 中。写链尾 + 写入须同事务; 测试枚举: 链连续性/篡改检测/清理边界/旧数据容忍。

### P2-3: swarm 面板 agora 健康 (主仓, 低风险)
**现状**: `bin/gac/swarm-activity-dashboard.py` 仅 submodule dirty, 无端口探测。
**改法**:
1. 新增 `_agora_health()`: `urllib` GET `http://localhost:7431/health` (SSE), 解析 `status/proxy.tool_count/backends.alive/audit_24h.total`; 探不通标记 down。2s 超时 + try/except。
2. **端口 7420 从 port-registry 读取而非硬编码** (踩过硬编码路径教训): 从 `protocols/port-registry.yaml` 或已有 config 读取 agora API 端口。
3. `build_report()` (L197) 加 `"agora_health": _agora_health()`; text/rich 渲染加段落。
**风险**: 低。只读探测。

### 深层-5: SSE/gateway 双进程 ProxyManager 统一 (agora, 中风险)
**现状**: `_init_proxy` (mcp.py:530) 走 `mcp_bootstrap.scan_and_launch` 硬编码 `lazy=True` (mcp_bootstrap.py:687) → SSE 进程 backends 连接 0; `pm._health_checker` 恒 None (tools_health.py:111) → /health backends 恒空 (假绿机制根源)。
**改法 (Review 修正: 单一 owner)**:
1. **停 gateway 独立进程** (launchd `com.agora.gateway` plist 删除/停用), SSE 进程作**唯一 eager 启动者**:
   - `mcp.py:_init_proxy` Phase 1 兜底后追加: `await mcp_gateway.start_all()` 复用 dependencies 共享单例 + KNOWN_BACKENDS。
   - `mcp_bootstrap.py:687` `lazy=True` 改为 env 控制: `AGORA_PROXY_EAGER=1` 时 eager (SSE launchd 设置)。
   - **不再引入 owner 锁/双开关** (避免自相矛盾); SSE 唯一 owner 无并发拉起问题。
2. **/health backends 口径修正**: KNOWN_BACKENDS 全为 stdio, `BackendHealthChecker._tick` 视 stdio 为 transient 跳过 heartbeat → `_health_checker` 永远报 0。改为统计 `pm.registry._clients` (已连接 client 数) 作为 `backends.alive`:
   - `tools_health.py:108-113` 改读 `len(getattr(pm.registry, "_clients", {}))`。
   - `health.py BackendHealthChecker.__init__` 仍回填 `pm._health_checker` (兼容现有调用), 但 health 计数以 registry 为准。
**风险**: 中。SSE 启动变慢 (20 backends), 部分拉不起需失败不阻塞 (lifespan try/except 已有)。停 gateway plist 是部署变更, 更新 install-launchd.sh。

### 深层-6: fastmcp 直接调用 tools=0 (agora, 中风险)
**现状**: `tools_auth.py:79` 无 HTTP 上下文时 `raise MCPAuthError(401, "No HTTP request context")`; 依赖 fastmcp 私有 API (`_current_http_request`)。
**改法**:
1. `tools_auth.py require_agora_api_key` fallback 分支 (L68-95): **在 try 外层分支**判断无 HTTP 上下文时放行 (返回 True) + `agora_role_ctx.set("local")`, 不进入 try 抛异常逻辑 (避免连真实异常一起吞)。语义: HTTP 传输层强制鉴权; 进程内直接调用视为受信任本地调用 (能 import agora.server.mcp 者本已持有 API key, 不扩大攻击面)。
2. 抽象 `agora/server/request_context.py`: 封装 `_current_http_request` 读写, `mcp_entry.py` 与 `tools_auth.py` 共用, 降 fastmcp 升级风险。
3. 回归: `tests/unit/test_tools_auth_fail_closed.py` 新增: ①"无 HTTP 上下文直接调用应放行"正向用例; ②"HTTP 错误 token 仍拒绝"负向用例。
**风险**: 中。放行削弱 fail-closed 防御面但仅限本地进程; HTTP 路径鉴权不受影响 (仍注入 request context)。

### P2-4: CI 部署拓扑 smoke (主仓, 中-高风险)
**现状**: `.github/workflows/agora-ci.yml` 仅 test job `--ignore=tests/e2e`; 无部署验证。
**改法 (Review 修正断言)**:
1. `agora-ci.yml` 新增 `deploy-smoke` job:
   - ubuntu runner `uv sync`
   - 后台 `AGORA_AUTH_MODE=permissive AGORA_ADMISSION_MODE=degraded AGORA_BOS_ONLY=1 uv run agora-mcp --sse`
   - 断言: `GET :7431/health` 200 + status 可解析 (**BOS_ONLY 下 health_check 工具会被 _bos_only_cleanup 移除, 但 /health HTTP 路由保留** → 只断言 HTTP 路由, 不断言 health_check 工具)。
   - **不断言 audit_log 新行** (FastMCPAuditMiddleware 只写 structlog 日志、不发事件总线 → 断言不可靠)。
2. 第一版用 `AGORA_BOS_ONLY=1` 降风险 (不拉 KNOWN_BACKENDS 子进程, 只验核心路由)。
3. e2e 测试单独 job 用 `--run-e2e` 标记, 不放开 `--ignore`。
**风险**: 中-高。CI ubuntu 无 kairon workspace 结构, `uv run --package X` 解析失败 → BOS_ONLY 模式规避。

## 依赖关系
- 深层-5 (SSE 进程接 KNOWN_BACKENDS) 依赖 P1 的 ProxyManager 收口 (已合入)。
- P2-2 hashchain 与 P2-3 (audit_24h) 相关 — hashchain 不改查询接口。
- P2-1 的 /metrics 与 P2-3 面板可独立。

## 实施顺序建议
1. **agora 子模块** (P2-1 → P2-2 → 深层-5 → 深层-6): 一个 commit 或分 2 个 commit, 测试 + ruff。
2. **主仓** (P2-3 面板 + P2-4 CI): 主仓 worktree + PR。
3. agora 子模块 push + 主仓 bump 指针, 统一走 PR。

## 验证
- 单元测试: `test_tools_auth_fail_closed.py` + audit hashchain 新测试 + bos_metrics 测试
- `uv run pytest tests/unit/ -q` + `ruff check`
- 重启 SSE 服务: `/health` backends >0, `/metrics` 有输出, `POST /v1/tools/call` 通过
- swarm 面板: `python3 bin/gac/swarm-activity-dashboard.py --json` 显示 agora_health
