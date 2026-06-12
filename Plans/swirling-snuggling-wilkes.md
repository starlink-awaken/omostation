# 异步/事件/调度/PubSub 体系收敛方案

> Plan ID: swirling-snuggling-wilkes
> Date: 2026-06-12
> Author: 老王 (基于 3 份前置调研: 架构现状分析 + 红队攻击报告 + 现有代码复用扫描)
> Status: ⏸️ 等待用户批准

---

## Context — 为什么做这件事

omostation 是 5 层 (I0-L4) + 10 子项目 monorepo, **7-8 套不同的异步/事件/调度/PubSub 机制并存** (asyncio 协程 / cron 定时 / 30min 轮询 / SSE 事件 / 15s 心跳 / PubSub 引擎 / WebSocket / DAG 编排 / 进程内 MessageBus)。**没有任何 Kafka/RabbitMQ**, agora EventBus 是唯一跨进程事件总线, 但与 cron_service、MessageBus、TaskSync、cron daemon、omo_sse_daemon **没有统一接口**。

3 周前会话输出:
1. 架构现状分析 (`.omo/_delivery/async-event-cron-architecture-2026-06-12.md`, 5500 字)
2. 收敛决策 (用户问"需要拆项目吗?" → 老王答"先沉淀再拆", Phase A→B→C)

本 plan 解决的问题: **Phase A 详细执行方案** (R57, 3 周), 用最低破坏性收敛 7 套机制为 1 个统一接口 + 1 个 DLQ + 1 个 schema 策略。

**预期收益**:
- 新代码用 `from agora.bus import publish, subscribe, schedule` 1 行替代 8 套机制的"选哪个"决策
- 事件丢失有 DLQ 兜底 (现状: 失败 callback 只 log warning)
- 跨系统调试有统一 trace_id 协议
- 后续 Phase B (R63+ 拆仓) 有 6 个月沉淀期作为数据支撑

---

## 推荐路径: Phase A → B → C 3 阶段渐进

### 关键校正 (从红队攻击报告中吸收)

| 红队攻击 | 校正动作 |
|----------|---------|
| **#11 God Module 风险** | bus/ 子包从 day 1 拆 5 个文件: `__init__.py` (facade) + `envelope.py` + `router.py` + `dlq.py` + `backends/` 子包; 单文件硬上限 500 行 |
| **#12 MessageBus vs EventBus 边界** | **不强行统一**, 保持 2 个独立 facade: `agora.bus.external` (跨进程: EventBus/SSE/WS/TaskSync) + `agora.bus.internal` (进程内: MessageBus/cron); 共用 envelope+DLQ, 不共用 API |
| **#6 机制数量低估** | 实际需 8 个 backend (asyncio direct / EventBus / SSE / WSServer / TaskSync / MessageBus / cron / croniter), 不是 6 个; Phase A.0 先全量枚举 |
| **#1 重试乘法爆炸** | 定义"重试所有权"规则: **每条事件链路只有 1 层做重试**; 文档写在 `agora/bus/RETRY-OWNERSHIP.md`; 监控 bus-stats 看板显示每层重试次数 |
| **#2 EventLoop 崩溃** | 强制 adapter 内部检测 "有 loop → async_task, 无 loop → run_in_executor, 都没有 → fire-and-forget" 三态分流; 加单测覆盖 |
| **#3 Schema versioning 是 theatre** | 推到 **Phase A.1** (R58 单独做), Phase A.0 只做 envelope Pydantic model + 默认 schema_version=1; 真正 schema 演进 R58+ 单独立项 |
| **#4 SSE 重连风暴** | adapter 内部写死 backoff: 1s, 2s, 4s, 8s, cap 60s, **不可配置**; 写测试覆盖 5 个 consumer 同时重连 |
| **#5 SQLite DLQ 隐藏 SPOF** | 用 `cron_service/db.py` 的 WAL + busy_timeout=5000 模式; 加单文件 50MB 滚动 GC; 落 `~/.runtime/bus_dlq.db` (跟现有一致) |
| **#9 3 周是 fantasy math** | Phase A 拆 2 个子阶段: **A.0 (2 周) 接口 + DLQ + 1 backend (EventBus) + 测试**, **A.1 (2 周) 加 SSE/WS/TaskSync/cron backends + retry policy**; 总计 4 周而非 3 周 |
| **#7/#8/#10/#16 5 条件全是软的** | 写 **硬技术门**: Phase B 触发条件改为 (a) ≥3 个项目**生产**调用 (grep 验证), (b) bus/ 子包有 180 天 git history, (c) agora CLAUDE.md 写明 owner, (d) 至少 1 个 eCOS 之外的 PR/issue |

### 推荐路径: 3 阶段 12+ 月

```
R57 (4 周) — Phase A.0: 接口 + 1 个 backend
R58 (4 周) — Phase A.1: 加 5 个 backend + retry policy + schema 演进
R59-R62 (4 月) — 沉淀期: 不动结构, 推广到 omo/metaos/runtime, 收集数据
R63 (评估点) — Phase B: 拆 bus-foundation 独立仓 (硬条件触发)
R64-R70 (6 月) — Phase B 沉淀期
R70+ — Phase C: 评估 L0 协议层提升
```

---

## Phase A.0 (R57, 2 周) — 骨架 + EventBus backend

### Week 1: 设计 + 骨架

**Day 1-2: 写设计文档**
- `projects/agora/docs/bus-unification-plan.md` (架构图 + 决策表 + 风险表)
- `projects/agora/src/agora/bus/RETRY-OWNERSHIP.md` (重试所有权规则)
- `projects/agora/src/agora/bus/README.md` (公共 API + 选型决策表)

**Day 3-5: 写骨架 (5 文件)**
- `agora/bus/__init__.py` (~50 行, facade)
- `agora/bus/envelope.py` (~150 行, BusEnvelope Pydantic model)
- `agora/bus/router.py` (~200 行, RouteConfig + dispatcher)
- `agora/bus/dlq.py` (~250 行, SQLite DLQ, WAL mode, GC)
- `agora/bus/backends/base.py` (~100 行, BusBackend Protocol + is_available contract)
- `agora/bus/backends/eventbus.py` (~150 行, 包裹 agora EventBus)

**Week 1 验收**: 5 文件全在, 单文件 < 500 行, `from agora.bus import publish, subscribe` 可用 (但只支持 EventBus 1 个 backend)

### Week 2: 集成 + 测试 + 切换

**Day 6-8: 写测试 + 1 个 demo**
- `agora/tests/test_bus_envelope.py` (~80 行, 12 个 case)
- `agora/tests/test_bus_dlq.py` (~120 行, 15 个 case: WAL, busy_timeout, GC, rotate)
- `agora/tests/test_bus_eventbus_backend.py` (~100 行, 10 个 case)
- `agora/tests/test_bus_retry_ownership.py` (~80 行, 5 个 case 验证重试不重数)

**Day 9-10: 1 个 demo 切换**
- 选 1 个**非核心** producer 改 import: `agora/audit_subscriber.py` 从 `from agora.core.event_bus import EventBus` 切到 `from agora.bus import subscribe`
- 不改 API 调用方式, 行为完全一致
- 跑全 agora 1105 个 tests, 必须 100% 通过

**Day 11-14: 收口 + ADR**
- 更新 `agora/CLAUDE.md` 加 §bus 子包说明 (按现有"文件职责"格式)
- 写 `agora/AGENTS.md` 加 bus 章节 (按现有 table-of-files 格式)
- 写 1 个 `docs/ADR-0008-bus-foundation-strategy.md` (把"为什么先沉淀再拆" + "5 硬条件"白纸黑字)

**Week 2 验收**: 1105 个 tests 全过 + 1 个 producer 切换成功 + 文档齐

---

## Phase A.1 (R58, 2 周) — 加 5 个 backend + retry policy + schema

**目标**: bus 覆盖跨进程机制全 6 个 (asyncio direct / EventBus / SSE / WSServer / TaskSync / MessageBus) + 2 个定时机制 (cron daemon / croniter)

### 关键文件
- `agora/bus/backends/asyncio.py` (~80 行, 进程内 await)
- `agora/bus/backends/sse.py` (~150 行, 包裹 agora.sse.SSEManager, backoff 写死)
- `agora/bus/backends/ws.py` (~150 行, 包裹 agora.ws_server)
- `agora/bus/backends/realtime.py` (~100 行, 包裹 agora.realtime.TaskSync, **不重做 version 逻辑, 直接复用**)
- `agora/bus/backends/messagebus.py` (~150 行, 包裹 runtime.executor.message_bus, **保持 request/response 语义**)
- `agora/bus/backends/cron_daemon.py` (~150 行, 包裹 omo_daemon, **默认 deprecated**)
- `agora/bus/backends/croniter.py` (~150 行, 包裹 runtime.cron_service)
- `agora/bus/retry.py` (~80 行, 重试所有权规则实现 + metrics)
- `agora/bus/schemas.py` (~200 行, 8 个 EventType 分类 map, **从 audit_subscriber.py:109-128 复用**)

### 验收
- 1 个新 producer demo: omo/omo_sse_daemon 切到 `from agora.bus import subscribe`
- 1 个新 consumer demo: metaos/workflow.py 切到 `from agora.bus import publish`
- 1 个 cron job demo: 用 `from agora.bus import schedule` 替代手写 cron 触发
- 全仓 tests 仍 100% 通过
- bus 子包单文件**无 1 个超 500 行**

---

## R59-R62 沉淀期 (4 个月)

**目标**: 收集 5 硬条件的数据

| 触发 Phase B 的硬条件 | 测量方法 | 测量频率 |
|----------------------|---------|---------|
| ≥3 个项目生产环境调用 `from agora.bus` | grep + 手动抽样 | 月度 |
| bus/ 子包有 ≥180 天 git history | git log --since | 自动 |
| agora CLAUDE.md 写明 bus owner | 阅读 | 一次性 |
| ≥1 个 eCOS 之外的项目使用 | GitHub issue / PR | 持续 |
| bus 改动频率 ≥ agora 主体 50% | git log 统计 | 月度 |

**不允许的事**:
- ❌ 不允许拆仓 (除非全 5 条件满足)
- ❌ 不允许改 bus 公共 API (Phase A 定型后冻结 6 个月)
- ❌ 不允许删 omo_daemon (deprecated 但保留 6 个月)

**R62 末评估**:
- 全 5 条件满足 → 准备 Phase B
- 4 满足 → 评估哪个缺失, 决定是补还是再等
- ≤3 满足 → **不拆**, 继续沉淀, R63 重评

---

## Phase B (R63+, 触发后) — 拆 bus-foundation 独立仓

**触发条件**: 5 硬条件全满足

### 拆仓动作
- 新建 `projects/bus-foundation/` 仓
- 把 `agora/bus/*` 搬过去
- agora CLAUDE.md 改 import: `from bus_foundation import publish, subscribe, schedule`
- 写独立 `bus-foundation/CLAUDE.md` + `AGENTS.md` + `docs/`
- CI 拆 2 套 (独立版本, 独立 release)

### 验收
- 0 行 agora 仓代码变动 (除 import 切换)
- 跨仓 e2e test 仍 100% 通过
- 独立 owner / owner.md 写明

---

## Phase C (R70+, 触发后) — L0 协议层提升

**触发条件**: 6 个以上**外部**项目 / 组织使用 bus-foundation

### 提升动作
- 搬 `bus-foundation/` 到 `protocols/bus-foundation/` (L0 协议层位置)
- 纳入 I0 织层 governance
- 写完整 governance charter
- agora 退回 "agora gateway" 角色, 事件下沉

**不达标的退路**: R70+ 评估不满足 → 继续 Phase B 沉淀, R78 再评

---

## 备选路径: 激进合并 (不推荐, 仅作对照)

| 维度 | 推荐 (渐进) | 备选 (激进) |
|------|------------|------------|
| Phase A 时长 | 4 周 | 8 周 (一次做完 8 backend) |
| 拆仓时机 | 6+ 月沉淀 | 2 月 (只要有 1 个外部用户) |
| 接口冻结 | A.0 末冻结 6 月 | 不冻结, 持续演化 |
| God module 风险 | 5 文件拆分 | 单 facade 文件 (1700 行) |
| 失败重试边界 | 显式所有权规则 | "自己 try/except" 自由风格 |
| 团队接受度 | 高 (渐进, 不强推) | 低 (4 周全切, 团队抵触) |

**为什么选推荐**: 8 个机制各自有**真实的优化目标** (Pareto frontier), 硬合并会损失这些特性。**保留多样性, 收口复杂度** (老王反复强调的反直觉原则)。

---

## 关键决策点 (用户必须明确, 否则无法推进)

1. **硬条件 5 选 1**: 推荐 "硬技术门" (git history 180 天 + grep 验证生产调用), 备选 "软条件" (5 advisory rules)
2. **重试所有权**: 推荐 "每条链路 1 层", 备选 "bus 全权负责" (可能引入 #1 攻击)
3. **DLQ 落点**: 推荐 `~/.runtime/bus_dlq.db` (跟现有 bus_consumer 一致), 备选 `~/.agora/bus_dlq.db` (按 agora 命名空间)
4. **omo_daemon**: 推荐 R57 deprecated, R62 删, 备选 R57 即删 (破坏性, 不推荐)
5. **Phase B owner**: 推荐 "agora team", 备选 "新设 cross-cutting team" (需要 HR 配合)

---

## 关键复用清单 (从 scout 报告吸收)

| 组件 | 来源 | 动作 |
|------|------|------|
| Registry/handler 模式 | `agora/unified_protocol_adapter.py` | **EXTEND** 结构模板 |
| Drop-in `is_available` 模式 | `agora/redis_message_queue.py` | **REUSE** backend 契约 |
| Event envelope `{id, time, source, type, trace_id, payload}` | `agora/core/event_bus.py:124-131` | **EXTEND** + `schema_version: int = 1` |
| Event-type 分类 map (8 namespace) | `agora/audit_subscriber.py:109-128` | **REUSE** 到 bus/schemas.py |
| DLQ table schema + 状态机 | `runtime/bus_consumer.py:44-52, 99-124` | **REUSE** DLQ backend |
| 指数退避 + jitter | `agora/retry.py` | **REUSE** via `with_retry` |
| SQLite WAL + busy_timeout | `runtime/cron_service/db.py:22-28` | **REUSE** DLQ pragmas |
| Optimistic versioned events | `agora/realtime.py:27-50` | **REFERENCE** (不重做) |
| Organ metadata header | `agora/redis_message_queue.py:1-20` | **REUSE** 每个 backend 文件 |
| Test class grouping + tempfile | `agora/tests/test_event_bus.py` | **REUSE** 测试模式 |
| CLAUDE.md "文件职责" 表格 | `agora/CLAUDE.md` | **REUSE** 文档结构 |
| `runtime/executor/message_bus.py` | (本地重复) | **AVOID**, 标记 R62+ 迁移目标 |

---

## 验收 (R57 末)

### 必跑命令
```bash
# 1. lint
ruff check projects/agora/src/agora/bus/
ruff format --check projects/agora/src/agora/bus/

# 2. 单文件行数硬上限
find projects/agora/src/agora/bus/ -name "*.py" -exec wc -l {} \; | sort -rn | head -5
# 期望: 最大单文件 < 500 行

# 3. tests
cd projects/agora && uv run pytest tests/test_bus_*.py -v
# 期望: 全部通过 (新建 ~50 case)

# 4. 全仓回归
cd projects/agora && uv run pytest -q
# 期望: 1105 个 tests 全过, 0 失败

# 5. 1 个 producer 切换 demo
grep -rn "from agora.bus import" projects/agora/src/agora/audit_subscriber.py
# 期望: 至少 1 行
python -c "from agora.audit_subscriber import AuditSubscriber; print('OK')"
# 期望: OK, 行为不变
```

### 必交产物
- ✅ 5 文件骨架 (`agora/bus/{__init__,envelope,router,dlq}.py` + `backends/{base,eventbus}.py`)
- ✅ 3 个测试文件 (envelope / dlq / eventbus backend)
- ✅ 3 个文档 (`docs/bus-unification-plan.md` + `bus/RETRY-OWNERSHIP.md` + `bus/README.md`)
- ✅ 1 个 producer 切换 (audit_subscriber)
- ✅ `agora/CLAUDE.md` + `agora/AGENTS.md` 更新
- ✅ `docs/ADR-0008-bus-foundation-strategy.md` 写明 5 硬条件
- ✅ 单文件 < 500 行 验证通过
- ✅ 1105 个 tests 全过
- ✅ **.omo/_delivery/phase-a0-completion-2026-06-XX.md** evidence 落盘

### 不允许的产物
- ❌ 不允许新建仓 (Phase A 不拆)
- ❌ 不允许动 omo/metaos/runtime 代码 (R57 之后)
- ❌ 不允许改 agora CLAUDE.md 已有结构 (只加 §bus 章节)
- ❌ 不允许删 omo_daemon (deprecated 但保留)
- ❌ 不允许改公共 API 冻结后变更 (A.0 末冻结 6 月)

---

## 风险与缓解 (按红队 P0 排序)

| 风险 | 来源攻击 | 缓解动作 |
|------|---------|---------|
| bus/ 子包变 god module | #11 | day 1 拆 5 文件; 单文件 < 500 行; PR review 强约束 |
| 重试乘法爆炸 (9 次) | #1 | 写 `RETRY-OWNERSHIP.md`; bus adapter 自身不重试; 监控每层重试次数 |
| EventBus + MessageBus 强合破坏语义 | #12 | 拆 2 facade: `external` + `internal`; 共用 envelope+DLQ, 不共用 API |
| 机制数量低估 50% | #6 | Phase A.0 末全量 grep 验证, 列全 8-12 个机制; A.1 覆盖完整 |
| SSE 重连风暴 | #4 | adapter 内部 backoff 写死, 不可配置; 单测覆盖 5 consumer |
| SQLite DLQ SPOF | #5 | WAL + busy_timeout 5000; 50MB 滚动 GC |
| Schema versioning 是 theatre | #3 | 推到 A.1, A.0 只做 Pydantic model + 默认 v=1 |
| 3 周低估 2x | #9 | 拆 A.0 (2 周, 1 backend) + A.1 (2 周, 5 backend) = 4 周 |
| 5 条件全是软的 | #7/#8/#10 | 改为硬技术门 (git history / grep / owner.md) |
| Phase C L0 promotion 无验证 | #16 | 加可测标准: ≥2 组织使用 / ≥1 学术引用 |

---

## 关键决策回答 (老王直面)

**Q: 需要单独拆项目吗?**
A: **需要, 但不是现在**. R57 先沉淀到 agora 内部, R63+ 评估拆仓, R70+ 评估 L0 提升。3 阶段 12+ 月。

**Q: 最优解?**
A: **统一接口层 (Unified Bus API) + 2 facade (external/internal) + 1 DLQ + 硬技术门驱动的拆仓时机**. 不是"建 1 套新框架替代 8 套", 是"给 8 套老兵发统一军装"。

**Q: 抛开历史包袱?**
A: 抛开也成立. **保留多样性, 收口复杂度** — 8 套机制各占据 Pareto frontier 的不同点, 硬合并会损失这些优化。统一 ≠ 合并。

---

## 状态: ⏸️ 等待用户批准

下一步:
- 用户批准 → 立即开干 Phase A.0 (2 周)
- 用户反对 → 讨论备选或调整范围
- 用户问题 → 任意点 AskUserQuestion
