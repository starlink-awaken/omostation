# 异步、钩子、定时任务、事件与治理体系全面深度下钻

> 范围：omostation 工作区全部 hooks / async tasks / cron jobs / events / governance logic，重点聚焦 bus-foundation 及相关体系。
> 生成时间：2026-06-17
> 版本：v1.1（基于当前 HEAD、文件系统直接读取 + 4 个子代理补充）

---

## 1. 总体架构速览

工作区采用 **5+4+1+1 分层**，所有跨层调用理论上走 **Agora BOS URI**；所有治理状态写入走 **OMO broker / c2g ingress**；所有时间性/事件性能力由 **bus-foundation + runtime cron_service + GitHub Actions cron + 本地 crontab** 四层叠加承载。

```
┌─────────────────────────────────────────────────────────────────────┐
│ 触发面                                                            │
│  · 人类 CLI: cockpit / workspace                                  │
│  · Agent:    agora MCP :7431                                       │
│  · 时间:      crontab / GitHub Actions / bus schedule              │
│  · 代码:      git hooks / pre-commit                              │
├─────────────────────────────────────────────────────────────────────┤
│ I0  织层  ── agora (MCP Hub + BOS URI + EventBus + SSE)           │
│ L1  运行时 ── runtime (cron_service + matrix scheduler + bus)     │
│ L2  引擎面 ── kairon / gbrain / omo / metaos (均有 bus adapter)   │
│ L4  自我层 ── l4-kernel (SignalBus + 24域 registry)               │
├─────────────────────────────────────────────────────────────────────┤
│ 横切面总线 ── bus_foundation (pub/sub/schedule/DLQ/backends)       │
│ 治理内核   ── projects/omo (audit/task/debt/sync/event/alert)     │
│ 战略入口   ── projects/c2g (radar/gc/approval)                    │
└─────────────────────────────────────────────────────────────────────┘
```

**关键约束（来自 AGENTS.md）**
- `code_freeze: true`（当前 system.yaml）
- BOS URI 是跨层调用唯一路径
- `.omo/` / `spaces/` 直接写入被禁止，必须经 OMO broker
- 任何变更必须立即 git commit，否则可能被 `git reset` 静默回滚

---

## 2. Bus Foundation 体系（核心）

### 2.1 定位与演进

`projects/bus-foundation` 是从 agora 拆出的**横切面总线框架**，提供统一的 `publish / subscribe / schedule` API，零外部依赖。Agora 通过 `agora.bus` 向后兼容别名重新导出它，同时保留 agora 专属高级 backend。

| 文件 | 职责 |
|------|------|
| `src/bus_foundation/__init__.py` | Facade：`publish()` / `subscribe()` / `schedule()` / `BusEnvelope` / `EventType` |
| `src/bus_foundation/router.py` | 路由到 backend，失败写 DLQ，不重试 |
| `src/bus_foundation/envelope.py` | 统一信封：`id/time/type/source/schema_version/trace_id/payload` |
| `src/bus_foundation/dlq.py` | 死信队列 |
| `src/bus_foundation/backends/base.py` | backend 协议 |

### 2.2 设计约束（红线）

1. **零 agora 依赖**：`src/bus_foundation/` 中禁止 `from agora ...`
2. **Backend 自身不重试**：重试由底层 transport 或 subscriber 负责
3. **单文件 < 500 行**
4. **`match_pattern` 唯一**：所有 backend 必须委托，禁止重写 `_match`
5. **仅使用 `collections.abc`**（UP035 规则）
6. **公共 API 冻结 6 个月**：破坏性变更需 ADR

### 2.3 Backend 矩阵

| Backend | 位置 | 能力 | 状态 |
|---------|------|------|------|
| `eventbus` | `bus_foundation/backends/eventbus.py` | 进程内 dict pub/sub，`*` / `prefix*` / exact 匹配 | 默认 |
| `croniter` | `bus_foundation/backends/croniter.py` | cron / `every Nm/Nh` 调度线程，30s tick | 默认 |
| `persistent` | `bus_foundation/backends/persistent_bus.py` | SQLite WAL 持久化 pub/sub，10k 事件保留 | 新增 R73 |
| `messagebus` | `bus_foundation/backends/messagebus.py` | 进程内 req/resp 相关 pub/sub | 可选 |
| `asyncio` | `bus_foundation/backends/asyncio.py` | `asyncio.Queue` 异步 consumer | 可选 |
| `sse` | `agora/bus/backends/sse.py` | 复用 `agora.sse.sse_manager` 向浏览器 fanout | agora 专属 |
| `websocket` | `bus_foundation/backends/ws.py` | WebSocket 推送，每个 client 一个 `asyncio.Task` | 可选 |
| `realtime` | `bus_foundation/backends/realtime.py` | 版本递增后同步 dispatch | 可选 |

**并发模型**
- `EventBusBackend`：同步 callback，publish 时同线程 dispatch
- `PersistentBusBackend`：SQLite WAL + 线程锁，publish 持久化后进程内 fanout
- `AsyncioBackend`：`asyncio.Queue` + `loop.create_task(_drain())`
- `WebSocketBackend`：每个 client 一个 `_drain()` task
- `DLQ`：`threading.Lock` 保护的 SQLite

**Backend 选择逻辑**：`publish()` 读取 `envelope.backend`，缺省 `eventbus`；若指定 backend 不可用，写入 DLQ。

### 2.4 项目级 Bus Adapter

| 项目 | Adapter 文件 | 当前用途 |
|------|-------------|----------|
| `omo` | `src/omo/omo_bus_adapter.py` | 订阅 `pipeline:*` / `debt:*` / `node_completed`（与 omo_sse_daemon 治理类型对齐） |
| `runtime` | `src/runtime/runtime_bus_adapter.py` | 将 runtime cron job 桥接到 bus schedule（`register_cron_job(expr, callback)`） |
| `metaos` | `src/metaos/metaos_bus_adapter.py` | demo-only：发布 workflow node 状态事件 `node_{status}`；**未集成 workflow.py**（注释明确说明 circular dep 未解） |

### 2.5 Bus 事件类型（Canonical）

```python
class EventType(str, Enum):
    PIPELINE_COMPLETED = "pipeline:completed"
    PIPELINE_STARTED   = "pipeline:started"
    MESSAGE_RECEIVED   = "message:received"
```

项目实际使用自定义字符串类型：
- `pipeline:*` / `debt:*` / `node_completed` — OMO 治理面
- `node_{status}` — metaos workflow 节点状态
- `message:received` — 通用消息

### 2.6 DLQ 与可靠性

- Router 捕获 backend 不可用 / publish 异常 → DLQ
- Croniter backend 内回调异常仅记录日志，不尝试重试（RETRY-OWNERSHIP.md）
- `runtime/bus_consumer.py` 是独立进程示例：消费 agora `/api/events`，持久化到 SQLite DLQ，重试 3 次后 park

### 2.7 常用验证命令

```bash
cd projects/bus-foundation
uv run pytest tests/ -q
uv run ruff check src/
uv run ruff format src/ --check
```

---

## 3. Runtime 异步 / 定时 / 调度体系

### 3.1 入口与暴露

| 组件 | 位置 | 说明 |
|------|------|------|
| `runtime` CLI | `src/runtime/cli.py` | 人类/Agent CLI（**已 deprecated，人类入口是 cockpit**） |
| `runtime_bus_adapter` | `src/runtime/runtime_bus_adapter.py` | bus schedule 桥接（legacy cron_service 仍独立运行） |
| `matrix scheduler` | `src/runtime/scheduler.py` | 15s tick，launchctl/docker/port 健康检查 |
| `cron_service` | `src/runtime/cron_service/` | 独立子服务：SQLite job store + ThreadPoolExecutor + croniter |
| `executor/message_bus` | `src/runtime/executor/message_bus.py` | Agent 间 req/resp 消息总线 |
| `task_scheduler` | `src/runtime/executor/task_scheduler.py` | executor 内部任务调度 |

### 3.2 cron_service 详解

```
projects/runtime/src/runtime/cron_service/
├── __init__.py
├── server.py          # 服务入口
├── scheduler.py       # croniter 调度引擎
├── db.py              # SQLite job store
├── delivery.py        # job 投递
├── executor.py        # 执行器
├── mcp_server.py      # MCP 暴露
└── scripts/
    └── script-bridge-sync.py
```

**调度表达式支持**
- 标准 cron：`0 10 * * *`
- 自然语言：`every 5m` / `every 30m` / `every 2h`
- 步进 cron：`*/15 7-23 * * *`

**关键约束**：新创建 job 不立即执行，等待下一次调度窗口，避免 bulk import 洪峰。

### 3.3 Matrix Scheduler

- 15 秒扫描一次 `runtime.matrix.list_services()`
- 检查 launchctl label、docker container、TCP 端口
- 维护 `~/runtime/matrix_state.json`
- 同步到 `.omo/state/system_health.yaml`
- 支持 crash-loop 追踪、auto-heal、freshness stale 检测

### 3.4 异步并发模型

- **Executor**：asyncio + ThreadPoolExecutor 混合
- **Agent pool**：`agent_pool.py` / `agent_pool_parallel.py`
- **Swarm**：`executor/swarm.py` / `executor/swarm_protocol.py`
- **Bus**：sync callback + asyncio backend 并存

### 3.5 值得注意的实现细节

- `apscheduler` 仅在依赖中列出，**runtime 未直接调用其 API**；实际调度由 `cron_service` 自研 scheduler 承担。
- **没有使用 Celery / `schedule` 库 / 系统 crontab** 直接承载 runtime 任务。
- Agora 调用有**自动降级**：连续失败 2 次后，5 分钟内直连底层 MCP，绕过 agora proxy。
- `runtime scheduler` 只写 `.omo/state/system_health.yaml`，并通过 `state_schema.py` 防止混入 governance-only keys。
- `bus_consumer.py` 是**独立阻塞进程**，不是 asyncio，负责把 Agora 事件推到 gbrain。
- `kei_sandbox.py` 使用 `sys.addaudithook` 做系统级审计拦截；新增 FS mutation hook 拦截 `os.remove`/`os.unlink`/`os.mkdir`/`os.rmdir`/`os.rename`，其中 `os.rename` 同时校验源路径与目标路径是否均落在 `allow_write` 前缀下。

### 3.6 常用验证命令

```bash
cd projects/runtime
uv run pytest tests/ -q
uv run ruff check src/
uv run ruff format src/ --check
python scripts/contract_gatekeeper.py src/
```

---

## 4. Agora MCP / BOS URI / 事件体系

### 4.1 入口

| 入口 | 端口/方式 | 说明 |
|------|----------|------|
| MCP HTTP | `:7431` | Agent 默认入口（推荐） |
| MCP stdio | - | 已 deprecated，向后兼容 |
| HTTP API | `:7422/:7431/:8080` | Web/API 入口 |
| SSE `/events` | `:7430`（默认） | 事件流 |

### 4.2 BOS URI 解析

- 声明式注册表：`projects/agora/etc/bos-services.yaml`（71 条目，POC 阶段）
- 解析器：`src/agora/mcp/resolver/`（services / bos_registry / pool / adapter / api）
- 硬编码 fallback：`src/agora/mcp/resolver/services.py` 中 `_FALLBACK_SERVICES`
- 支持 transport：`stdio` / `internal` / `http` / `mcp_stdio`

**关键命令**
```bash
agora bos discover   # Pydantic 验证后的注册表
agora bos health     # endpoint + metrics 健康报告
agora bos status     # invoke metrics p50/p95/p99
```

### 4.3 Agora EventBus

- `src/agora/core/event_bus.py`：持久化 JSON + HTTP POST 订阅回调
- at-least-once，重试 3 次
- 模式匹配：exact / prefix / catch-all
- 自动截断：保留最近 500 条事件
- Hooks：支持 `_hooks` 注册（audit/metrics）

### 4.4 实现细节与风险点

- `server/mcp.py` 仍是 **900+ 行的 God Module**，拆分计划见 `docs/god-module-split-plan.md`。
- 环境变量：
  - `AGORA_BOS_REGISTRY=none`：强制使用硬编码 fallback `_FALLBACK_SERVICES`
  - `AGORA_BOS_ONLY=1`：启动时裁剪非 BOS 管理工具
- 所有 BOS 写操作（`mutate_resource`）都会**失效缓存并写审计日志**。
- `resolve_bos_uri` 优先走 `BOSRouter`，失败才回退 `POC_SERVICES`。
- `runtime/bus_consumer.py` 通过遗留 `:7430` 读取事件流，可能与当前 SSE `:7431` 不一致，存在端口漂移风险。

### 4.5 agora.bus 与 bus_foundation 关系

```python
# agora/src/agora/bus/__init__.py
from bus_foundation import (
    BusEnvelope, EventType, publish, schedule, subscribe, DLQ, Router,
)
# agora 专属 backend 保留在 agora.bus.backends.*
```

Agora 对 bus_foundation 是**消费者 + 高级 backend 提供者**，不是替代。

---

## 5. OMO 治理 / 审计 / 任务 / 事件体系

### 5.1 核心模块

| 模块 | 文件 | 能力 |
|------|------|------|
| Audit | `omo_audit.py` | 6 项治理巡检、AppendOnlyLog 审计轨迹 |
| Task | `omo_task.py` | `.omo/tasks/{active,planned,done}` YAML 浏览/创建 |
| Cards | `omo_cards.py` | CARDS 冲突检查 |
| Debt | `omo_debt*.py` | 债务注册、review、dispatch、execution |
| Sync | `omo_sync.py` | 结构化同步日志到 `omo-sync.jsonl` |
| Event | `omo_event.py` | AppendOnlyLog 写事件样板、查询 Agora EventBus |
| Alert | `omo_alert.py` | 告警处理 |
| Logs | `omo_logs.py` | 审计日志分析与 §17 metrics |
| SSE Daemon | `omo_sse_daemon.py` | 长连接监听 agora SSE |
| Daemon | `omo_daemon.py` | 30min tick governance daemon（只读 dry-run） |
| Worker | `scripts/omo/omo_worker.py` | 77KB worker 调度/分派/提升/回收核心 |
| CLI | `cli.py` | 统一入口，分派到各子命令 |

### 5.2 AppendOnlyLog 5 个 Consumer

来自 AGENTS.md：
- `omo_audit`
- `omo_bos_metrics`
- `omo_sync`
- `omo_alert`
- `omo_event`

物理落点：`.omo/_knowledge/*.jsonl`（`omo-events.jsonl`、`omo-sync.jsonl`、审计 JSONL 等）

### 5.3 OMO 对外接口

```bash
omo governance              # 6 项审计，期望 100.0 A+
omo bos status             # BOS invoke metrics
omo bos discover           # 注册表
omo observability log tail # 多文件 tail
omo event emit --type X --source Y --payload '...'
omo cards --check
omo task list
omo worker dispatch|watchdog|admission|rollout|rules
```

### 5.4 常用验证命令

```bash
cd projects/omo

# 测试
uv run pytest tests/ -q

# 治理审计（期望 100.0 A+）
uv run python -m omo.cli governance

# BOS 健康
uv run python -m omo.cli bos health

# 债务刷新
uv run python -m omo.cli debt refresh --now 2026-06-17T00:00:00Z

# schema lint
uv run python -m omo.cli lint schemas

# direct-io gate（非 broker 禁止写 .omo / spaces）
uv run python -m omo.cli lint direct-omo-io
```

### 5.5 治理写入约束

- `omo lint direct-omo-io`：pre-commit 强制拦截非 broker 直接写 `.omo` / `spaces`
- 允许写入者白名单：`projects/omo/src/omo/*`、`projects/c2g/src/c2g/adapters.py`、`projects/c2g/src/c2g/bridge_import.py`
- 其他代码使用 `write_text` / `open(...,"w")` / `unlink` / `mkdir` 到 `.omo` 一律拒绝提交

---

## 6. L4-Kernel / MetaOS 信号与编排

### 6.1 L4 SignalBus

- `projects/l4-kernel/src/l4_kernel/signals.py`
- 发射信号到域的 `signals.md`
- 跨域信号同时写入 `@驾驶舱/_control/signals.md`（带 `fcntl.flock` 文件锁）
- 信号类型：`✅` / `⚠️` / `🔴` / `ℹ️`
- 24 域注册表：`registry.py` 中 `_BUILTIN_DOMAINS`

### 6.2 Capability Registry

- `registry.py` 包含 OPC 9 个 capability（含 7 个 self-correction 新增）
- model-driven bridge 可选依赖

### 6.3 MetaOS 编排

| 文件 | 职责 |
|------|------|
| `src/metaos/core/engine.py` | 工作流引擎 |
| `src/metaos/core/workflow.py` | workflow 执行 |
| `src/metaos/core/router.py` | 路由 |
| `src/metaos/core/gate.py` | 门控 |
| `src/metaos/core/immune.py` | 免疫/安全 |
| `src/metaos/core/cognitive_framework.py` | 认知框架加载（BDSK / Six Hats） |
| `src/metaos/a2a/task_manager.py` | A2A 任务管理 |
| `src/metaos/metaos_bus_adapter.py` | bus 事件发布（demo-only） |

**当前限制**：metaos ↔ agora circular dep 未解决，bus adapter 未真正接入 workflow.py。

---

## 7. Git Hooks & Pre-commit 体系

### 7.1 根仓库 Hooks

| Hook | 位置 | 触发 | 行为 |
|------|------|------|------|
| `pre-commit` | `.husky/pre-commit` | 提交前 | arcnode 约束变更验证（fallback EG 脚本） |
| `pre-commit` | `.pre-commit-config.yaml` | 提交前 | check-yaml + omo logs audit baseline + health SSOT + port hardcode + cross-deps + omo direct-io gate |
| `post-commit` | `.git/hooks/post-commit` | 提交后 | 异步 L0/L4 知识萃取：mof-extract → mof-validate → workflow schema-report → BOS 提醒 |

### 7.2 子项目 Hooks（.githooks/pre-commit）

| 项目 | 能力 |
|------|------|
| `kairon` | ruff check + 非原子写入预警 + 新包测试覆盖检查 |
| `agora` | ruff + 非原子写入 |
| `cockpit` | ruff |
| `ecos` | ruff + MOF 4 工具校验（schema-validate / bridge-sync / derive / state-bridge） |
| `omo` | ruff + 非原子写入 |
| `metaos` | ruff + 非原子写入 |
| `runtime` | YAML / kei.yaml / protocol registry 校验 |
| `gbrain` / `family-hub` / `hermes-console` / `omo-debt` | 存在 pre-commit |

**注意**：`.husky/pre-commit` 与 `.pre-commit-config.yaml` 是两套独立机制，同时生效。

### 7.3 MOF Pre-commit 强制链（ecos）

1. `mof-schema-validate.py --staged --strict`（M1 YAML 改动）
2. `mof-bridge-sync.py --strict`（lifecycle 改动）
3. `mof-derive.py --strict`（7 阶段 + 4 门禁推理）
4. `mof-state-bridge.py --strict`（OMOTask 改动）

失败即阻止提交。

---

## 8. CI/CD Workflows（GitHub Actions）

工作区有 **39 个 workflow 文件**。按性质分类：

### 8.1 定时治理类

| Workflow | 触发 | 核心任务 |
|----------|------|----------|
| `c2g-radar-daily.yml` | 每日 8:00 UTC | `bin/compass_radar.py` → 写 `.omo/state/health.yaml` + `system.yaml`，自动 commit |
| `c2g-gc-weekly.yml` | 每周一 9:00 UTC | c2g gc 清理 28d+ pitch，归档到 `runtime/sandbox/decayed/` |
| `omo-autopilot.yml` | 每日 2:00 UTC | omo-debt analyze → omo gc → omo ledger，创建 PR |
| `audit-rollout-monthly.yml` | 每月 1 号 1:00 UTC | 跨仓 audit-rollout + §17 metrics，自动 commit |
| `governance-check.yml` | push/PR/每周一早 8:00 | 8 个治理检查脚本 + `omo.cli lint direct-omo-io` |
| `debt-audit.yml` | （待确认） | 债务审计 |

### 8.2 项目 CI 类

- `kairon-ci.yml` / `agora-ci.yml` / `cockpit-ci.yml` / `ecos-ci.yml` / `omo-ci` 同类 / `metaos-ci.yml` / `runtime-ci.yml` / `gbrain-ci.yml` / `family-hub-ci.yml` / `observability-ci.yml` / `hermes-console-ci.yml`

### 8.3 强制校验类

- `state-goals-enforce.yml`：system.yaml / current.yaml 一致性
- `task-schema-enforce.yml`：任务 schema
- `cross-deps-enforce.yml`：跨层依赖
- `interfaces-enforce.yml`：接口契约
- `port-registry-enforce.yml`：端口注册
- `config-check.yml` / `constraint-validation.yml` / `meta-model-check.yml`

### 8.4 质量与 lint

- `ruff-check.yml` / `ci-lint.yml` / `ci-python-coverage.yml` / `pytest.yml` / `quality.yml`

---

## 9. 本地 Crontab 定时任务

### 9.1 治理 crontab（`.omo/cron/governance-crontab`）

```cron
0 9  * * *   bash scripts/x1-x4-check.sh            # X1-X4 全维度治理检查
0 10 * * 1   bash scripts/debt-audit.sh             # 债务审计
0 11 1 * *   python3 scripts/generate-governance-dashboard.py  # 治理报告
```

### 9.2 OPC Closeout crontab（`.omo/cron/opc-closeout-crontab`）

| 时间 | 任务 | 关联文件 | 说明 |
|------|------|----------|------|
| 周一 08:00 | radar | `scripts/opc_p5_radar_cron.py` | 技术雷达 |
| 周一 09:00 | weekly_loop | `scripts/opc_p6_weekly_loop_cron.sh` | 周循环 |
| 每天 02:00 | drift_detector | `scripts/opc_p6_drift_detector.py` | 漂移检测 |
| 每天 02:05 | self_evolve | `scripts/opc_p6_self_evolve_cron.sh` | 漂移 → planned task |
| 每天 02:10 | approval_board | `scripts/opc_p6_approval_board.py` | 汇总 planned task |
| 周日 23:00 | release_cycle | `scripts/opc_p7_release_cycle_cron.sh` | 发布周期收口 |
| 周一 02:00 | audit_rollout | `omo.cli audit-rollout` | 5 仓 metrics 聚合 |
| 每天 04:00 | doc_lint | `scripts/opc_p7_doc_lint.py` | stale 证据检查 |
| 每天 03:00 | memtheta_filter | `scripts/opc_p1_memtheta_filter.py` | 记忆过滤 |

**触发源语义**：`INVOCATION_ID=cron` + `OPC_TRIGGER=cron` 为真 cron；否则视为 manual。

### 9.3 Cron 环境变量（`.omo/_control/evolution/config.yaml`）

```yaml
INVOCATION_ID: "cron"
OPC_TRIGGER: "cron"
WORKSPACE: "/Users/xiamingxing/Workspace"
PYTHONPATH: "projects/omo/src"
OPC_MODE: weekly/monthly/pre-release
OPC_GENERATED_AT / OPC_TODAY: 可覆盖时间
```

### 9.4 MOF State Bridge Cron 集成

`scripts/opc_mof_state_bridge_cron.sh`：任何 OPC cron 跑完后必跑 `mof-state-bridge --strict`，输出 `.omo/_delivery/audit-rollout/{date}-mof-state-bridge.json`，`blocking=true` 时标红。

---

## 10. 事件 / 消息 / 信号清单

### 10.1 Bus 事件（bus_foundation / agora.bus）

| 事件类型 | 生产者 | 消费者 | 说明 |
|----------|--------|--------|------|
| `pipeline:completed` | runtime / metaos | omo bus adapter | 流水线完成 |
| `pipeline:started` | runtime / metaos | omo bus adapter | 流水线开始 |
| `debt:*` | omo debt 模块 | omo bus adapter | 债务事件 |
| `node_completed` | metaos workflow | omo bus adapter | 节点完成 |
| `node_{status}` | metaos bus adapter | （demo） | workflow 节点状态 |
| `message:received` | 通用 | 通用 | 通用消息 |

### 10.2 OMO AppendOnlyLog 事件流

| 日志文件 | 生产者 | 消费者 |
|----------|--------|--------|
| `.omo/_knowledge/omo-events.jsonl` | `omo event emit` | audit / dashboard |
| `.omo/_knowledge/omo-sync.jsonl` | `omo_sync.run_sync` | audit / radar |
| `~/runtime/audit/governance-audit.jsonl` | `omo_audit.record` | audit trail |
| `.omo/_knowledge/omo-audit.jsonl` | omo audit | logs audit |

### 10.3 L4 SignalBus 信号

- 写入各域 `signals.md`
- 跨域写入 `@驾驶舱/_control/signals.md`
- 类型：`✅` / `⚠️` / `🔴` / `ℹ️`

### 10.4 Runtime 服务健康事件

- MatrixScheduler 生成健康状态
- 同步到 `.omo/state/system_health.yaml`
- 不健康服务触发 auto-heal

---

## 11. 跨系统调用流示例

### 11.1 一次 cron 触发的治理闭环

```
.crontab/opc-closeout-crontab
    └─> scripts/opc_p5_radar_cron.py (INVOCATION_ID=cron)
            ├─> 读 .omo/tasks/ + .omo/state/*
            ├─> 写 .omo/_control/evolution/radar/*
            └─> scripts/opc_mof_state_bridge_cron.sh
                    └─> projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py --strict
                            ├─> 比对 M1 OMOTask ↔ .omo/tasks/
                            └─> 写 .omo/_delivery/audit-rollout/{date}-mof-state-bridge.json
```

### 11.2 一次 git commit 触发的知识闭环

```
git commit
    ├─> .husky/pre-commit          # arcnode 约束验证
    ├─> .pre-commit-config.yaml    # yaml + omo logs + health + port + cross-deps + direct-io
    └─> .git/hooks/post-commit     # 异步
            ├─> mof-extract.py     # L4 知识萃取
            ├─> mof-validate.py    # L0 校验
            ├─> mof-workflow.py schema-report
            └─> BOS 声明提醒写入 impact log
```

### 11.3 Agent 跨层调用

```
Agent → agora MCP :7431
            └─> resolve_bos_uri("bos://governance/omo/audit")
                    └─> uv run --directory projects/omo python -m omo.cli audit
```

### 11.4 Runtime 调度一个 cron job

```
runtime cron_service
    ├─> SQLite job store (db.py)
    ├─> scheduler.py (croniter + ThreadPoolExecutor)
    ├─> executor.py
    └─> 可选: runtime_bus_adapter.register_cron_job(expr, cb) → bus_foundation.schedule(expr)
```

---

## 12. 脚本与工具清单

### 12.1 根目录 `bin/`

| 工具 | 用途 |
|------|------|
| `compass_radar.py` | c2g radar，写 health.yaml / system.yaml |
| `check_health_ssot.py` | health SSOT 一致性校验 |
| `classify_planned.py` | planned 任务分类 |
| `workspace` | Workspace CLI 入口 |
| `workspace-audit` | 6 维度统一审计 CLI |
| `verify-omo.sh` | 治理验证链 |
| `register-mcp.py` | MCP 服务注册 |
| `scan_hardcoded.sh` | 硬编码路径扫描 |
| `ssot-writeback.py` | SSOT 写回 |

### 12.2 `scripts/` 治理脚本

| 脚本 | 用途 |
|------|------|
| `check-interfaces.py` | 接口契约检查 |
| `check-cross-deps.py` | 跨层依赖检查 |
| `check-ssot-reference-integrity.py` | SSOT 引用完整性 |
| `check-governance-surface-paths.py` | 治理面路径 |
| `check-project-arch-doc-contract.py` | 架构文档契约 |
| `generate-governance-dashboard.py` | 治理仪表盘 |
| `debt-audit.sh` | 债务审计 |
| `x1-audit-check.sh` | X1-X4 治理检查 |
| `opc_p5_radar_cron.py` | OPC P5 雷达 |
| `opc_p6_weekly_loop.py` | OPC P6 周循环 |
| `opc_p6_drift_detector.py` | 漂移检测 |
| `opc_p6_self_evolve.py` | 自演化任务生成 |
| `opc_p7_audit_rollout_daemon.py` | 5 仓 audit rollout |
| `opc_p7_release_cycle.py` | 发布周期 |
| `opc_p7_doc_lint.py` | 文档 lint |
| `opc_section17_metrics.py` | §17 metrics |

---

## 13. 当前缺口与风险

### 13.1 已识别问题

1. **metaos bus adapter 未真正集成**：注释明确 circular dep 未解，workflow.py 仍用 `requests.post` 直连。
2. **bus_foundation 与 agora.bus 边界仍有模糊**：部分代码可能仍 import `agora.bus`，会触发 DeprecationWarning。
3. **runtime_bus_adapter 只是薄 facade**：legacy cron_service 仍独立运行，未完全迁移到 bus schedule。
4. **Agora SSE 端口漂移风险**：`runtime/bus_consumer.py` 使用 `:7430`，而当前 SSE 默认入口是 `:7431`。
5. **Agora `server/mcp.py` 仍是 God Module**：900+ 行，拆分计划尚未落地。
6. **子模块 dirty**：`c2g/cockpit/ecos/omo/scripts` 五个子模块指针未 bump，且 `projects/bus-foundation` 指针也处于 modified 状态。
7. **code_freeze=true**：新增事件/consumer/cron 需走 OMO 审批流程。

### 13.2 建议下一步

1. 将 metaos workflow.py 中硬编码的 `requests.post` 逐步替换为 bus publish + BOS URI 调用。
2. 统一所有 cron 入口：本地 crontab、GitHub Actions cron、runtime cron_service、bus schedule 建一张注册表，避免重复或遗漏。
3. 为 bus-foundation 增加可观测性：事件吞吐量、DLQ 深度、backend 可用性指标接入 agora metrics。
4. 明确 OPC cron wrapper 的退出码语义和失败告警路径（当前部分脚本软失败只写日志）。
5. 统一 Agora SSE 端口消费端，消除 `:7430` / `:7431` 漂移。
6. 推进 `server/mcp.py` God Module 拆分。
7. bump 5 个 dirty 子模块指针并提交根仓库元数据。

---

## 14. 补充：工作区内其他容易被忽视的调度与并发机制

除了上述总线与系统级定时任务外，代码库在**业务层与存储层**还潜藏了几种特殊的并发、调度与锁机制：

### 14.1 AetherForge 算力与配额调度架构 (MeshScheduler)
与时间维度的任务调度不同，AetherForge 实现了针对大模型算力节点（Compute Engine）的**资源调度引擎**：
- **QuotaEngine (配额引擎)**: 结合 codexbar 实时查询与本地预算约束，提供跨预付费、月结、速率限制的统一配额视图（`UnifiedQuota`）。
- **RouterPipeline & MeshScheduler**: 在发起 LLM 请求前，执行可用性三步检测（Key 验证 -> 网络在线探测 -> 配额余量检查），并依据 `cost_first`, `quota_first` 或 `balanced` 等动态策略进行最优 Provider 路由及 Fallback。
- *位置*: `projects/aetherforge/ARCHITECTURE-SCHEDULING.md`

### 14.2 L4-Kernel 多 Agent 并发防冲突控制
虽然 OMO 通过 broker 与 `direct-omo-io` 限制了状态修改面，但对于允许多个 Agent 同时介入的协作场景，底层文件读写安全由 `l4_kernel/concurrency.py` 兜底：
- **文件级互斥锁**: 利用 `fcntl.flock(LOCK_EX | LOCK_NB)` 对各个领域的控制面文件（如 `STATE.md`, `MEMORY.md`, `signals.md`）进行排他锁定。
- **乐观版本锁**: 提供基于文件修改时间（`st_mtime` 作为版本号）的 `write_if_version` 乐观锁操作，防止并行 Agent 写回时发生脏覆盖。
- **防止死锁**: 在批量锁定多个控制面文件时（`lock_domain_control`），严格按字母表排序加锁以规避循环等待。

### 14.3 GBrain 的并发 Worker 与分布式 DB 锁
在 `gbrain` 知识图谱引擎（基于 TypeScript/Bun）侧，有一套完全独立于 Python `bus-foundation` 的并发处理体系：
- **动态阈值 Worker 同步 (`sync-concurrency.ts`)**: 在文件系统与图谱的增量同步过程中，当变更文件数大于自动并发阈值（`AUTO_CONCURRENCY_FILE_THRESHOLD`，如 >100）时，自动拉起多个 Worker（默认 4 个）进行并行提权。
- **TTL 心跳式 DB 锁 (`db-lock.ts`)**: 放弃了 Session 级别的 Pg 锁（PgBouncer 池化会丢状态），采用基于持久化表 `gbrain_cycle_locks` 的行级 Upsert 排他锁。结合 `withRefreshingLock` 在长时间任务（如 30 分钟同步/索引）执行期间定时通过 SELECT 1 心跳给 TTL 续命，若进程 Crash 则 TTL 自然过期，避免死锁（解决 CODEX-2 缺陷）。
- **进程资源回收 (`zombie-reap.ts`)**: 显式注册 `SIGCHLD` handler 以确保衍生子进程执行完后自动释放，防止耗尽底层数据库连接池。

### 14.4 Kronos 知识摄取分发管线
不仅具有事件总线的投递机制，信息在进入知识管线后，还由 `kronos/dispatcher.py` 负责复杂的分发调度：
- 收到文章或快讯后，按照特定的分类规则分发进 Obsidian Vault 的对应域目录，同时根据 content-digest 模板渲染 XML 后同步提交到 WPS，并通过 Python API 注册到 KOS（知识操作系统）。

---

## 15. 附录：关键文件索引

```
# Bus Foundation
projects/bus-foundation/src/bus_foundation/__init__.py
projects/bus-foundation/src/bus_foundation/router.py
projects/bus-foundation/src/bus_foundation/envelope.py
projects/bus-foundation/src/bus_foundation/backends/eventbus.py
projects/bus-foundation/src/bus_foundation/backends/croniter.py
projects/bus-foundation/src/bus_foundation/backends/persistent_bus.py
projects/bus-foundation/src/bus_foundation/backends/ws.py
projects/bus-foundation/src/bus_foundation/backends/asyncio.py

# Agora Bus / Event
projects/agora/src/agora/bus/__init__.py
projects/agora/src/agora/core/event_bus.py
projects/agora/src/agora/bus/backends/sse.py
projects/agora/src/agora/server/mcp.py
projects/agora/src/agora/mcp/resolver/services.py
projects/agora/src/agora/mcp/bos_router.py

# Runtime
projects/runtime/src/runtime/runtime_bus_adapter.py
projects/runtime/src/runtime/scheduler.py
projects/runtime/src/runtime/cron_service/scheduler.py
projects/runtime/src/runtime/bus_consumer.py
projects/runtime/src/runtime/kei_sandbox.py
projects/runtime/src/runtime/executor/message_bus.py

# OMO
projects/omo/src/omo/omo_bus_adapter.py
projects/omo/src/omo/omo_audit.py
projects/omo/src/omo/omo_sync.py
projects/omo/src/omo/omo_event.py
projects/omo/src/omo/omo_daemon.py
projects/omo/src/omo/omo_sse_daemon.py
projects/omo/src/omo/cli.py
scripts/omo/omo_worker.py

# L4 / MetaOS
projects/l4-kernel/src/l4_kernel/signals.py
projects/l4-kernel/src/l4_kernel/registry.py
projects/metaos/src/metaos/metaos_bus_adapter.py
projects/metaos/src/metaos/core/workflow.py

# Hooks / CI / Cron
.husky/pre-commit
.pre-commit-config.yaml
.git/hooks/post-commit
.github/workflows/governance-check.yml
.github/workflows/c2g-radar-daily.yml
.github/workflows/omo-autopilot.yml
.github/workflows/audit-rollout-monthly.yml
.omo/cron/governance-crontab
.omo/cron/opc-closeout-crontab
scripts/install-cron.sh
scripts/opc_mof_state_bridge_cron.sh
.omo/_control/evolution/config.yaml
```

---

*本文档由 AI Agent 基于工作区文件直接分析生成，未修改任何运行时代码或治理状态。*
