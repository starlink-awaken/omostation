# bus-foundation R89–R97 现代化路线图 — 架构与实施方案

> **Spec 状态**: 提案 v1 (2026-07-10)
> **作者**: 架构审计 (X-Plane Audit Agent + human review)
> **目标读者**: bus-foundation 维护者 / omo governance review / agora + omo + metaos consumer owners
> **基线版本**: bus-foundation `91355d67` (R82 pydantic envelope + R87 bench)
> **SSOT 引用**: [`docs/ARCHITECTURE-DETAILED-MAP.md`](../ARCHITECTURE-DETAILED-MAP.md), [`docs/GOVERNANCE-EVOLUTION-ROADMAP.md`](../GOVERNANCE-EVOLUTION-ROADMAP.md), [`docs/VISION-ROADMAP.md`](../VISION-ROADMAP.md)
> **配套 Plan**: [`2026-07-10-bus-foundation-r89-r97.md`](./2026-07-10-bus-foundation-r89-r97.md) (逐 R 实施步骤)

---

## 0. 为什么这份 spec

bus-foundation 是 eCOS v6 的**事件总线核心** (X 横切框架层),被 7 个项目直接 import (omo / agora / metaos / aetherforge-gateway / kairon-kos / c2g / runtime). 任何破坏性变更都会级联到所有 consumer.

过去三轮 (R73-R82) 解决了**功能性正确性**:
- R73: 9 个 backend 全部 work
- R79: 修复 croniter / control_plane 的静默丢事件
- R80: data_plane 终于 honor subscribe pattern
- R82: OmniEnvelope 从手写类迁到 pydantic BaseModel
- R87: 加 pytest-benchmark 性能基线

但**运维三件套**(metrics / retry / DLQ admin)+ **测试深度**(property-based / chaos)仍是空白,生产部署时:
- 看不到任何指标 (Prometheus 友好度 = 0)
- 失败只能写 DLQ 等死,没有应用层 retry / circuit breaker
- DLQ 没有 admin CLI, 排查靠 sqlite CLI
- 任何 envelope 序列化 bug 都要写特定单元测试,没有 property-based 兜底

本 spec 提议 **R89–R97 九轮迭代**,按"指标先行 → 重试 + 熔断 → DLQ 治理 → 测试加固"顺序落地,3 个月内全部合并,后向兼容零破坏.

---

## 1. 系统上下文与现状

### 1.1 bus-foundation 在 eCOS v6 中的位置

```
L4 自我层 (l4-kernel) ─── 信号总线 ──┐
L3 入口层 (cockpit) ─── 路由/MCP ──┤
I0 织层 (agora) ─── 事件路由 + A2A ─┤   ◀── 都消费 bus-foundation
X 横切框架 (model-driven, bus-foundation, c2g, omo-debt, observability, aetherforge, family-hub)
```

来源: [`docs/ARCHITECTURE-DETAILED-MAP.md §1`](../ARCHITECTURE-DETAILED-MAP.md)

**关键定位**:
- 7 个项目直接 import `bus_foundation.*` (omo, agora, metaos, aetherforge, kairon, c2g, runtime)
- 是 workspace **唯一** 的 in-process + 跨进程事件总线,无替代品
- 跟 aetherforge gateway 联动 (OTel trace 上下文传播)
- 跟 agora `server/mcp.py` 强耦合 (MCP server 用 bus_foundation 接收 MCP 消息)

### 1.2 现状 (R82 末态)

| 维度 | 现状 | 短板 |
|------|------|------|
| **Backends** | 9 个: eventbus / asyncio / messagebus / croniter / persistent / data_plane / control_plane / realtime / sse / ws | 各自有 bug 修复历史, 接口不统一 (有的 honor pattern, 有的 not) |
| **Envelope** | pydantic BaseModel (R82) | schema_version 字段声明但**未启用** — 跨版本兼容靠运气 |
| **Router** | 4 层 publish + DLQ 兜底 | **no retry / no circuit breaker**, backend 故障 → 直接 DLQ |
| **DLQ** | SQLite WAL + 50MB 滚动 | **无 admin CLI**, **无 metrics**, **无 redaction** |
| **Observability** | structlog warnings | **无 OTel spans**, **无 metrics endpoint**, **无 trace propagation** |
| **Testing** | 18 test files, 1383 行, 124+ existing tests + 6 micro-benches | **无 property-based** (hypothesis), **无 load tests** (locust), **无 chaos tests** |
| **Backpressure** | asyncio backend 1000 写死 | data_plane ring buffer 满**默默丢**,无 metric 暴露 |
| **Schema** | `schema_version: str` 字段 | **无 registry**, **无兼容性矩阵** |

### 1.3 关键 ADR / 决策历史

| ADR | 决策 | 对本 spec 的约束 |
|-----|------|------------------|
| `RETRY-OWNERSHIP.md` (bus-foundation 内部) | backend adapter **不**重试, retry 是 application layer 的责任 | R90 retry middleware 必须挂在 **router 层**, 不能改 backend |
| R82 pydantic envelope | OmniEnvelope 是 pydantic BaseModel, 1:1 保留 public API | R92 schema registry 必须**追加**字段, 不能改 .topic / .payload 语义 |
| L0 / SSOT / M0 alignment audit (2026-06-29) | base classes in L0, schemas in M0 | R89 metrics counter names 必须登记到 `protocols/metrics-registry.yaml` (新建) |
| P71 baseline recovery (2026-07-02) | 工具未接 (类 B) 必须 fix | R91 DLQ admin CLI 必须用 `bin/` 模式 + agent workflow 治理 |
| P74 workflow solidification | workflow 不能沉默 | 新 workflows (e.g. `bus-foundation-metrics-bump`) 必须 1 周内有 caller |

---

## 2. 设计原则

按 eCOS v6 的 `AGENTS.md §3` + L0/M0 治理精神 + 工程常识,本 spec 遵循:

1. **零破坏性**: 所有 R 都向后兼容,9 个 backend 的 public API 不变
2. **增量启用**: R89 metrics 默认 OFF, 通过 `BUS_METRICS=1` env var 或 `enable_metrics()` 调用启用
3. **SSOT 一致**: 新增 metric names / event types 必须登记到 `protocols/*.yaml`, 不允许 hardcode 在代码注释
4. **Broker 优先**: DLQ admin CLI 跟 `bin/gen-dependency-baseline.py` 一样, 走 omo broker 写 (不直写)
5. **小步快跑**: 9 个 R 独立 PR, 每个 PR 自带 bench + 集成测试, merge 后立即可灰度
6. **测试先行**: R97 在 R89 之前先建 hypothesis 框架, 后续 R 复用
7. **观测先行**: R89 落地前, R90 retry 必须先在 metrics 暴露 "retry_attempted" counter 才能量化效果

---

## 3. 总体架构

### 3.1 当前架构 (R82 末态)

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Application Code                                │
│  omo / agora / metaos / aetherforge / kairon / runtime                 │
└────────────────────┬───────────────────────────────────────────────────┘
                     │ publish(envelope) / subscribe(pattern, cb)
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  bus_foundation 公共 API (__init__.py)                 │
│  publish / subscribe / schedule / facade.{data,event,control}         │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Router (router.py)                            │
│  backend.publish() → 成功: return event_id                              │
│                  → 失败: DLQ.enqueue() + return event_id                │
│  **no retry / no circuit breaker**                                      │
└────┬───────────────────────────────────────────────────┬───────────────┘
     │ publish                                         │ on failure
     ▼                                                 ▼
┌──────────────────────────┐              ┌──────────────────────────────┐
│   9 BusBackends (Protocol)│              │   DLQ (SQLite WAL + GC)      │
│  - eventbus (in-process)  │              │   ~/.runtime/bus_dlq.db      │
│  - asyncio (queue)        │              │   - enqueue / requeue        │
│  - messagebus (legacy)    │              │   - list_all / close         │
│  - croniter (scheduler)   │              │   **no admin CLI / metrics** │
│  - persistent (SQLite)    │              └──────────────────────────────┘
│  - data_plane (ring buf)  │
│  - control_plane (SQLite) │
│  - realtime (versions)    │
│  - sse (HTTP)             │
│  - ws (WebSocket)         │
└──────────────────────────┘
```

### 3.2 目标架构 (R97 末态)

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Application Code                                │
└────────────────────┬───────────────────────────────────────────────────┘
                     │ publish(envelope) / subscribe(pattern, cb)
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  bus_foundation 公共 API                                │
│  + bus.metrics.snapshot()   (R89)                                      │
│  + bus.retry.get_policy()   (R90)                                      │
│  + bus.dlq.ack_from_dlq()   (R91)                                      │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Middleware Pipeline                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  MetricsMiddleware (R89)                                          │  │
│  │    in: BusEnvelope  →  out: BusEnvelope                          │  │
│  │    side-effect: counters/histograms + spans                      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  RetryMiddleware (R90)                                           │  │
│  │    policy: exponential backoff + jitter + max_attempts          │  │
│  │    + CircuitBreaker (open/half_open/closed per backend)         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  DLQMiddleware (R91)                                             │  │
│  │    on_terminal_failure: redact + enqueue + emit metric          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Router (升级)                                  │
│  backend.publish() → 中间件链 → 成功: return                            │
│                   → 失败: 重试 (R90) → DLQ (R91)                       │
└────┬───────────────────────────────────────────────────┬───────────────┘
     │ publish                                         │ on terminal failure
     ▼                                                 ▼
┌──────────────────────────┐              ┌──────────────────────────────┐
│  9 Backends (Protocol)   │              │  DLQ v2 (R91)                │
│  + 每个 backend 内部     │              │  + redaction hook            │
│    暴露 _health_metric() │              │  + health metric             │
│  + circuit_breaker()     │              │  + CLI: bus-dlq {list,ack,   │
│                          │              │             retry,purge}      │
└──────────────────────────┘              └──────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Observability Surface (R89 + R94 cross-project)           │
│  - bus_metrics: prometheus /metrics (port 8745)                        │
│  - bus_traces:  OTel spans with trace_id propagation                   │
│  - bus_logs:    structlog + contextvars                                │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.3 关键边界

| 边界 | 在哪一层 | 暴露什么 |
|------|----------|----------|
| **API boundary** | `bus_foundation/__init__.py` 公共 API | 保持 1:1 兼容, 只追加 |
| **Middleware boundary** | `bus_foundation/middleware/` (新) | 透明, 应用层不感知 |
| **Backend Protocol** | `bus_foundation/backends/base.py` | 保持 4 个方法, 加 `_health_metric()` 默认返回 None |
| **Cross-project boundary** | aetherforge gateway 拉取 `/metrics` | R89 起 aetherforge `gateway` 引入 bus-foundation metrics scrape job |
| **Schema boundary** | `protocols/metrics-registry.yaml` (R89 新建) | 跟 `protocols/port-registry.yaml` 同级 SSOT |

---

## 4. 九轮迭代详细设计

> 每个 R 独立 PR, 自带测试 + bench + 集成 smoke.

### R89 — Metrics & Health Endpoints

**问题**: 现在看不到任何 backend 状态. 生产事故时只能重启 + 翻 DLQ.

**目标**: 加 4 类 metrics + Prometheus 兼容 endpoint, 默认 OFF, 启用 zero overhead cost.

**新增文件**:
- `bus_foundation/metrics/__init__.py` (新) — counter/histogram/gauge 抽象
- `bus_foundation/metrics/registry.py` — 全局 metric registry
- `bus_foundation/metrics/instrumentation.py` — 给 9 个 backend 自动加 instrumentation
- `bus_foundation/metrics/server.py` — aiohttp + prometheus_client 启 HTTP server
- `bus_foundation/middleware/metrics.py` — middleware 实现
- `tests/test_metrics.py` — unit + integration
- `benchmarks/test_metrics_overhead.py` — 验证默认 OFF 时 zero overhead
- `protocols/metrics-registry.yaml` (新 SSOT) — 登记所有 metric names

**修改**:
- `bus_foundation/__init__.py` — 加 `metrics.snapshot()`, `enable_metrics(port=8745)`
- `bus_foundation/router.py` — 接入 MetricsMiddleware

**Metric 清单** (登记到 `metrics-registry.yaml`):

| Name | Type | Labels | 含义 |
|------|------|--------|------|
| `bus_publish_total` | counter | `backend`, `status` (success/fail/dlq) | publish 总数 |
| `bus_publish_latency_seconds` | histogram | `backend` | publish 延迟 |
| `bus_subscribe_active` | gauge | `backend`, `pattern` | 当前活跃订阅数 |
| `bus_dlq_depth` | gauge | `backend` | DLQ 当前条目数 |
| `bus_backend_healthy` | gauge | `backend` | backend 可用性 (1/0) |
| `bus_circuit_breaker_state` | gauge | `backend`, `state` (open/closed/half_open) | 熔断器状态 (R90 启用) |

**启用方式**:
```python
# 默认 OFF, zero overhead
import bus_foundation
# 显式启用
bus_foundation.enable_metrics(port=8745)
# 拉取 snapshot
metrics = bus_foundation.metrics.snapshot()
```

**环境变量**:
- `BUS_METRICS=1` 启动时自动 enable, 监听 `BUS_METRICS_PORT` (default 8745)
- `BUS_METRICS_BACKENDS=eventbus,croniter` 限定启用的 backend instrumentation

**集成测试**:
- `tests/test_metrics_integration.py` — 启动 HTTP server, publish 1000 envelope, 验证 counter / histogram 值
- `benchmarks/test_metrics_overhead.py` — disable vs enable 的 throughput 对比, 验证 overhead < 5%

**退出标准**:
- 所有 9 个 backend 都有 `_health_metric()` 实现
- 6 个 metric 名称登记 `protocols/metrics-registry.yaml`
- `make gac-local-gate` PASS
- `benchmarks/test_metrics_overhead.py` overhead < 5%
- 1 个 PoC 集成: aetherforge `gateway/grafana.json` 加 bus-foundation 面板

### R90 — Retry Middleware & Circuit Breaker

**问题**: backend 临时故障直接 DLQ, 无重试. 应用层被迫自己写 retry 逻辑, 重复造轮子.

**目标**: router 层加 retry middleware + circuit breaker, **per-backend 配置**, 默认 OFF.

**复用**:
- R89 的 metrics, retry_attempted / retry_succeeded / circuit_state 全是 counter/gauge
- 现有 RETRY-OWNERSHIP.md 文档, **不**改 backend 行为

**新增文件**:
- `bus_foundation/retry/__init__.py` (新) — RetryPolicy + RetryMiddleware
- `bus_foundation/retry/policy.py` — exponential backoff + jitter
- `bus_foundation/retry/circuit_breaker.py` — 经典 3 状态机
- `bus_foundation/middleware/retry.py` — middleware wiring
- `tests/test_retry_policy.py` — unit (backoff math, jitter distribution)
- `tests/test_circuit_breaker.py` — state transitions, half-open probing
- `tests/test_retry_integration.py` — 全 9 backend × fail-then-succeed 场景

**修改**:
- `bus_foundation/router.py` — 接入 RetryMiddleware
- `bus_foundation/__init__.py` — 加 `retry.set_policy(backend, policy)`, `retry.get_stats()`

**RetryPolicy 默认值** (per-backend override):
```python
@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: float = 0.1  # seconds
    max_backoff: float = 5.0
    backoff_multiplier: float = 2.0
    jitter: float = 0.1  # ±10%
    retry_on: tuple[type[Exception], ...] = (Exception,)  # 默认全 retry
    # per-backend 例外
    # data_plane: 不重试 (fire-and-forget)
    # croniter:  立即失败 (调度场景, 重试无意义)
```

**CircuitBreaker 默认值**:
```python
@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1
```

**集成测试**:
- mock backend 抛 ConnectionError 5 次 → 第 6 次 circuit open
- 30s 后 → half_open → 探针调用成功 → closed
- retry 在 DLQ 之前, 最多 3 次, 每次 backoff 100ms / 200ms / 400ms

**退出标准**:
- 9 backend × fail-then-succeed × 4 重试配置 (3 default + 1 override) = 36 个场景 PASS
- benchmarks retry overhead 验证
- 新增 metric `bus_retry_attempted_total`, `bus_circuit_state`

### R91 — DLQ Admin CLI + Redaction + Metrics

**问题**: DLQ 出问题只能 `sqlite3 ~/.runtime/bus_dlq.db "SELECT *"`, 排查成本高, 敏感 payload 明文落盘.

**目标**: 加 `bin/bus-dlq` CLI + payload redaction hook + DLQ health metric.

**新增文件**:
- `bin/bus-dlq` (新 shell) — list / ack / retry / purge / stats 子命令
- `bus_foundation/dlq/admin.py` (新) — Python API 包装 DLQ
- `bus_foundation/dlq/redaction.py` (新) — 默认 + 自定义 redaction rules
- `tests/test_dlq_admin.py` — CLI 集成
- `tests/test_dlq_redaction.py` — redaction 规则
- `bin/bus-dlq.1` — man page (help2man 生成)

**修改**:
- `bus_foundation/dlq.py` — 接入 redaction hook + emit DLQ depth metric (复用 R89)
- `pyproject.toml` — 加 `[project.scripts] bus-dlq = "bus_foundation.dlq.admin:main"`

**CLI 设计** (跟 git / docker 风格):
```bash
bus-dlq list [--backend=X] [--status=PENDING|DLQ] [--limit=20] [--json]
bus-dlq stats  # DLQ 深度 / 最老条目 / backend 分布
bus-dlq ack <event_id>...   # 从 DLQ 移除 (确认已外部处理)
bus-dlq retry <event_id>...  # 重新 publish (走 router + R90 retry)
bus-dlq purge [--before=YYYY-MM-DD] [--backend=X]  # 物理删除
bus-dlq watch  # 类似 tail -f, 每 2s 刷新 stats
```

**Redaction 默认规则** (从 `protocols/redaction-patterns.yaml` 读):
- `password` / `secret` / `token` / `api_key` 字段 → 替换为 `***`
- 信用卡 (Luhn) / 邮箱 / IP → 脱敏
- 用户可在 `~/.config/bus-foundation/redaction.yaml` 追加

**退出标准**:
- 5 个子命令全部通过集成测试
- redaction 至少拦截 3 类敏感字段
- `bus-dlq stats` 输出可解析 JSON, 供 cockpit / grafana 拉取
- R89 metrics 里 `bus_dlq_depth` 自动更新

### R92 — Schema Registry & Compatibility Matrix

**问题**: `schema_version` 字段在 envelope 但没人用, 跨版本兼容性靠运气.

**目标**: 加 pydantic-based schema registry, 启动时校验兼容性, **backward compat only**.

**新增文件**:
- `bus_foundation/schema/__init__.py` (新)
- `bus_foundation/schema/registry.py` — 注册 + 查询
- `bus_foundation/schema/compatibility.py` — strict / additive / breaking 三档
- `bus_foundation/schema/codegen.py` — 从 pydantic 生成 JSON Schema
- `tests/test_schema_registry.py` — unit
- `tests/test_schema_migration.py` — 旧版 envelope 兼容测试

**修改**:
- `bus_foundation/envelope.py` — `validate_against_registry(envelope, target_version)`

**Registry 初始化** (在 `__init__.py`):
```python
from bus_foundation.schema import register
register("v1", OmniEnvelopeV1)
register("v2", OmniEnvelopeV2, compatibility="additive")
```

**退出标准**:
- 现有 v1 / v2 兼容性测试 PASS
- `envelope.schema_version = "v999"` → ValidationError 带明确 message
- pydantic JSON schema 可导出 (供外部 consumer 用 TypeScript codegen)

### R93 — Distributed Backends (Redis / NATS) — *可选*

**问题**: 所有 backend 单进程, 跨进程靠 SQLite file 共享, 高并发受限.

**目标**: 接入 Redis (pub/sub + stream) 和 NATS (subject-based) 后端, 走现有 `BusBackend` Protocol.

**新增**:
- `bus_foundation/backends/redis.py` — `RedisBackend`
- `bus_foundation/backends/nats.py` — `NATSBackend`
- `pyproject.toml` — `[project.optional-dependencies] redis = [...]`, `nats = [...]`

**退出标准**: PoC demo, 跨 2 进程 publish/subscribe 验证

**⚠️ 暂不实施** (理由): 工作量大, 偏离运维三件套主轴, 独立项目级别. 建议 0.3.0 release 后单独讨论.

### R94 — OpenTelemetry Integration (cross-project)

**问题**: bus-foundation 是事件总线, 但**不**trace 自己的事件. observability 断层.

**目标**: 每个 publish / subscribe 启 OTel span, trace_id 透传到 subscriber callback.

**新增**:
- `bus_foundation/observability/__init__.py` (新)
- `bus_foundation/observability/traces.py` — OTel wrapper
- `pyproject.toml` — `otel = ["opentelemetry-api>=1.20", "opentelemetry-sdk>=1.20"]`

**集成**:
- aetherforge gateway 拉 bus-foundation spans → 显示在 cockpit trace UI
- 跟 omo 的 task tracing 联动

**退出标准**: trace 跨 publish → subscriber 端到端, aetherforge cockpit 能看到

**⚠️ 建议排 R94 在 R89-R91 之后**, 但**先于 R95+**, 因为 R94 是 R90 retry 调试的前提.

### R95 — WebSocket Protocol Upgrade

**问题**: 现有 WS wire protocol 简单 JSON, 无 compression / heartbeat / reconnection.

**目标**: 加 per-message-deflate + heartbeat + 协议版本协商.

**新增**:
- `bus_foundation/backends/ws_v2.py` — 升级版 backend
- 保留 `ws.py` (v1) 1:1 兼容, 默认 v1, `BUS_WS_VERSION=v2` 切换

**退出标准**: PoC, 浏览器 SDK 兼容

**⚠️ 暂不实施** (理由): ROI 低, 需要 client 端改, 单项目不闭环.

### R96 — Croniter 完整 cron 表达式

**问题**: croniter backend 只支持 `every Nm/Nh`, 不支持标准 5 段 cron 表达式, 无时区.

**目标**: 接 `croniter` PyPI 库, 支持完整语法 + timezone.

**新增**:
- `bus_foundation/backends/croniter.py` 重构, 保留 `every` 语法向后兼容, 加标准 cron

**退出标准**: `cron("0 9 * * 1", tz="Asia/Shanghai")` 触发, 时区准确

**⚠️ 中优先级**: 不阻塞主轴, 但 cron 表达式增强是高频需求

### R97 — Property-Based + Chaos Testing

**问题**: 现有 124+ 单元测试, 但 envelope 序列化 / 并发订阅 / backend 切换等场景没有 property-based 兜底, bug 修复 (R79/R80/R82) 都是 production 爆雷后才修.

**目标**: 加 hypothesis property tests + chaos test 框架.

**新增**:
- `tests/property/test_envelope_properties.py` — `from hypothesis import given, strategies as st` 测 envelope 序列化 round-trip / pydantic 校验
- `tests/chaos/test_backend_chaos.py` — random backend kill / restart / slow network
- `tests/property/test_pattern_match.py` — pattern glob 边界 (R80 那类 bug 提前发现)
- `tests/property/conftest.py` — shared strategies

**示例** (R80 提前发现):
```python
@given(pattern=st.text(min_size=1), event_type=st.text(min_size=1))
def test_pattern_match_idempotent(pattern, event_type):
    """match_pattern 在反复 subscribe/unsubscribe 不应丢失事件"""
    # 如果 R80 那 bug 在, hypothesis 会用 * 之类的 pattern 触发
```

**退出标准**:
- 5+ property-based test, 每个跑 1000+ example
- 1 chaos test 框架, 3+ scenario (kill mid-publish / slow / restart)

---

## 5. 落地节奏

按 user 确认 + 项目标准流程,采用**"设计 spec + plan → 评审 → 逐 R 实施"**模式:

```
Phase A (本周, 1-2 天):
  - [x] 写 spec (本文)
  - [ ] 写 plan (本仓库 docs/2026-07-10-bus-foundation-r89-r97.md)
  - [ ] 提交 PR (docs only), 请 OMO 评审
  - [ ] 同步 agora / omo / metaos / aetherforge 维护者 (consumer 视角)

Phase B (3 个月, 9 个 R):
  R89 (week 1-2)  Metrics & Health Endpoints       ← 起步
  R90 (week 3-4)  Retry Middleware & Circuit Breaker
  R91 (week 5-6)  DLQ Admin CLI + Redaction
  R97 (week 7)    Property-Based + Chaos Testing   ← 跨 R 复用
  R92 (week 8-9)  Schema Registry
  R94 (week 10-11) OpenTelemetry Integration
  R96 (week 12)   Croniter 完整表达式
  (R93 / R95 暂缓, 0.3.0 后评估)

Phase C (week 13):
  - 复盘 + ADR-0150 (如果 spec 评审需要)
  - 跟 omostation/omostation 0.2.x → 0.3.0 release tag 准备
```

每个 R 用 `bin/gac-worktree.sh claim <r89|...>` 起独立 worktree + PR.

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| **破坏现有 7 个 consumer** | 中 | 高 (P0 事故) | 每个 R 都跑 `tests/integration/run-all.sh`, 1 consumer 1 PR review |
| **metric 名称冲突 aetherforge** | 低 | 中 | R89 协议走 `protocols/metrics-registry.yaml` SSOT, 跨项目评审 |
| **R90 retry 导致事件乱序** | 中 | 高 | 默认 `data_plane: no retry`, 应用层 opt-in |
| **R91 DLQ redaction 漏掉字段** | 中 | 高 (PII 泄露) | 默认严格模式, deny-by-default, 用户显式 opt-out |
| **R94 OTel 引入大依赖** | 中 | 中 | `[otel]` extra, 默认不装, 跟 aetherforge gateway 共享 |
| **bus-foundation 0.2.x 没人 commit** | 低 | 中 | OMO 治理 review, 每 R 配 1 个 reviewer |

---

## 7. 不做什么 (Out of Scope)

明确排除,避免 scope creep:

- ❌ **R93 分布式 backend 完整实现** (Redis/NATS 适配器) — 工作量大, 单独 milestone
- ❌ **R95 WS 协议 v2** — 需要 client 端改, 跨项目
- ❌ **Bus-foundation 0.3.0 release tag** — 评审后另起 spec
- ❌ **Bus-foundation 拆分为独立 PyPI 包** — 现在 workspace 内部使用, 不需要
- ❌ **gRPC backend** — 跟 agora grpc pattern_match 重复
- ❌ **全异步化** (asyncio 化所有 backend) — 大量工作, 无明确收益

---

## 8. 成功标准 (Definition of Done)

整个 R89-R97 完成的标志:

- [ ] 9 个 R 全部合并到 bus-foundation `main` 分支
- [ ] 7 个 consumer (omo/agora/metaos/aetherforge/kairon/c2g/runtime) 集成测试 PASS
- [ ] R89-R91 至少 1 个 PoC 部署 (aetherforge gateway 用 bus-foundation metrics 替代自写指标)
- [ ] `benchmarks/test_*.py` 跑完, performance regression < 5%
- [ ] `docs/ARCHITECTURE-DETAILED-MAP.md` §3.3 bus-foundation 部分更新
- [ ] `projects/bus-foundation/CHANGELOG.md` 加 `## [0.3.0]` section
- [ ] OMO 治理审计认可, governance-evolution-roadmap 增加一行

---

## 9. 关联引用

- [bus-foundation 实施 Plan](./2026-07-10-bus-foundation-r89-r97.md) — 逐 R 步骤
- [Workspace 详细架构](../ARCHITECTURE-DETAILED-MAP.md) — bus-foundation 在 eCOS v6 的位置
- [Governance Evolution Roadmap](../GOVERNANCE-EVOLUTION-ROADMAP.md) — 治理迭代节奏
- [eCOS v6 Vision](../VISION-ROADMAP.md) — 蜂群式 AI 超级大脑愿景
- [Bus-foundation 内部 RETRY-OWNERSHIP.md](../../projects/bus-foundation/RETRY-OWNERSHIP.md) — retry 责任边界

---

## 10. 评审签字

| 角色 | 评审点 | 状态 |
|------|--------|------|
| **OMO governance** | 协议注册 / agent workflow 接入 | ⏳ pending |
| **bus-foundation maintainer** | 实现细节 / 后向兼容 | ⏳ pending |
| **agora 维护者** | consumer 集成影响 | ⏳ pending |
| **omo 维护者** | consumer 集成影响 | ⏳ pending |
| **aetherforge 维护者** | R94 跨项目联动 | ⏳ pending |
| **metaos 维护者** | consumer 集成影响 | ⏳ pending |

> **提交 PR 之后, 跑 `make gac-local-gate` + 抄送 5 个 reviewer.**

---

> **下一步**: 写 [`2026-07-10-bus-foundation-r89-r97.md`](./2026-07-10-bus-foundation-r89-r97.md) 实施 plan, 提交 docs PR.
