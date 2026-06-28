# CLAUDE.md — OMO v5 治理内核

> eCOS v6 L2 引擎面 · 治理中枢 · Phase/Task/Debt/Audit 全生命周期管理
>
> 工作区总览与跨层约束请优先阅读 [`../AGENTS.md`](../AGENTS.md)。

---

## 项目身份

`projects/omo` 是 OMO OS 的**执行内核**，区别于工作区根目录下的 `.omo/` 实例数据层。

- **.omo/**：state plane，承载治理状态、任务、债务、审计证据（不要在此直接写代码）
- **projects/omo/**：kernel plane，实现 schema、audit、sync、promotion、task policy 等执行逻辑
- **projects/c2g/**：唯一战略入口 (ingress plane)，只能向 `.omo/tasks/planned/` 和 `.omo/goals/current.yaml` 物化

权威治理面定义：`.omo/standards/omo-governance-surfaces.md`
权威注册表：`.omo/_truth/registry/omo-governance-surfaces.yaml`

---

## 核心职责

1. **Phase / Task / Debt 生命周期** — `omo_worker_*`、`omo_debt_*`、`omo_audit_*`
2. **治理审计与门禁** — `omo_governance_surfaces.py`、`omo_audit*.py`
3. **任务策略红线** — `omo_task_policy.py` + `omo_lint.py`
4. **BOS 服务注册与度量** — `omo_bos_*`
5. **AppendOnlyLog 基础设施** — `omo_io.py`（7 consumers 共享同一物理层）
6. **model-driven 桥接** — `model_driven_bridge.py`（不直接 import model_driven，factory 模式解耦）

---

## 核心模块

> 173 个源文件。以下为核心模块分组:

```
src/omo/
├── cli.py                    # CLI 入口 (39 子命令, 含 deprecated bridge/strategy)
├── mcp_server.py             # MCP Server (19 tools)
├── omo_io.py                 # AppendOnlyLog + 原子写 + fcntl 跨进程锁
├── omo_paths.py              # 统一路径管理
├── _shared/                  # advisory_lock, append_only_log, timestamp_model
├── categories/               # audit, bos, debt, governance, worker (分类聚合)
├── omo_debt_*.py             # 债务管理 (17 模块: registry/lifecycle/dispatch/execution/metrics/reporting/approval/campaign/weight/io)
├── omo_audit*.py             # 审计 + 同步 + 去重 + rollout (4 模块)
├── omo_bos_*.py              # BOS 服务 (6 模块: core/dispatcher/metrics/schema/seeds/bos)
├── omo_self_healing*.py      # 自愈引擎 (2 模块: engine + fixes)
├── omo_worker_*.py           # Worker 调度 (6 模块: core/cmd_task/cmd_worker/dispatch/promotion/status)
├── omo_governance*.py        # 治理叠加与面校验 (19 模块: overlay/surfaces/state_plane/ingress/mutation/task_policy等)
├── omo_ingress*.py           # 入口写入 (7 模块: debt/doc/goal/registry/task_archive/task_contract/task_lifecycle/task_promotion/trail)
├── omo_lint*.py              # 静态校验 (5 模块: lint/doc/mutation_ledger/schemas/surfaces/yaml_bypass)
├── model_driven_bridge.py    # model-driven 桥接 (factory 模式, 不硬依赖)
├── omo_agora_pool.py         # Agora 连接池
├── omo_bus_adapter.py        # bus-foundation 适配器
├── omo_cockpit_bridge.py     # cockpit 桥接
├── omo_event.py / omo_alert.py # 事件与告警
├── omo_state.py / omo_health.py # 状态与健康
├── omo_promotion_*.py        # 晋升流程 (5 模块)
├── omo_evolution_loop.py / omo_weekly_loop.py # 演化循环
└── omo_sse_daemon.py         # SSE daemon
```

---

## CLI 子命令 (39)

| 分类 | 子命令 |
|------|--------|
| 治理 | `governance` (audit/history/propose/approve/apply/list/surfaces/ingress-*) |
| 任务 | `task` `worker`/`wt` `evidence` `trail` |
| 债务 | `debt` `gc` |
| BOS | `bos` |
| 审计 | `audit-rollout` `logs` `lint` `lint-metrics` |
| 状态 | `state` `health` `readiness` `inspect` `dashboard` |
| 事件 | `event` `alert` `observability` |
| 入口 | `cards` `goal` `knowledge` `delivery` `standard` `cost` |
| 自愈 | `healing` (status/fix-run/fix-list/rules/config/history) |
| 系统 | `serve` `daemon` `sse-daemon` `i0` `x-axis`/`xaxis` |
| Phase | `phase14` `phase15` `phase16` `metacognition` `capability`/`registry`/`scenario`/`pkg` `ledger` |
| Deprecated | `bridge` (→workspace compass bet) `strategy` (→workspace compass radar/gc) |

---

## MCP 工具 (19)

| 工具 | 功能 |
|------|------|
| `validate_task` | 任务 schema 校验 |
| `omo_bridge` | markdown spec → OMO task 导入 |
| `omo_worker_dispatch` / `omo_worker_reclaim` | Worker 调度/回收 |
| `omo_yield_task` | 任务让出 |
| `omo_gc` | 垃圾回收 |
| `omo_debt_list` / `omo_debt_summary` | 债务列表/摘要 |
| `omo_metacognition` | 元认知检查 |
| `cards_status` / `cards_search` / `cards_check` / `cards_create` / `cards_update` | CARDS 管理 |
| `acquire_lock` / `release_lock` / `check_lock` / `list_locks` | Advisory Lock (防并发 agent 抢占) |
| `check_gac_rule` | GaC 规则检查 |

---

## Agent 操作约束

### 1. 不要直接修改 `.omo/`

`.omo/` 是 state plane。所有状态变更必须通过 `omo-cli`、MCP 工具或 `projects/c2g/` 入口。

### 2. 推荐入口

```bash
# 治理审计 (目标 100.0 A+)
uv run python -m omo.cli governance audit --output json

# 治理面巡检
uv run python -m omo.cli governance surfaces --workspace-root ../../.. --json

# 非 broker 直接写拦截
uv run python -m omo.cli lint direct-omo-io

# ingress registry 一致性
uv run python -m omo.cli lint ingress-registry --workspace-root ../../..

# task policy 红线 (self-evolution-approval / human-approval-ref)
uv run python -m omo.cli lint task-policy self-evolution-approval --workspace-root ../../..
```

### 3. C2G 物化流程

- 战略意图先在 `projects/c2g/` 沙箱中沉淀为 Pitch
- Pitch 头部需包含 frontmatter：
  ```markdown
  > **Upstream**: MS-XXX
  > **Appetite:** N days
  ```
- 通过 `c2g bet <pitch.md>` 转换为 Bet 并生成 Planned Task
- 不要手动创建 `.omo/tasks/planned/*.yaml`

### 4. model-driven 桥接

- `model_driven_bridge.py` 使用 factory 模式，不直接 import model_driven
- M3 标准定义以 `projects/model-driven/src/model_driven/mof/m3_extended.py` 为准
- 任何新增阶段/门禁必须同步：model-driven 源 + M2 schema + M1 节点 + 校验工具
- 详见根 `AGENTS.md` §Model-Driven Bridge

---

## 跨项目依赖

| 方向 | 项目 | 依赖方式 |
|------|------|----------|
| omo → model-driven | `projects/model-driven` | pyproject.toml editable path, factory 模式解耦 |
| omo → agora | `projects/agora` | pyproject.toml editable path, 连接池 |
| omo → bus-foundation | `projects/bus-foundation` | pyproject.toml path, bus adapter |
| omo → aetherforge-gateway | `projects/aetherforge/packages/gateway` | pyproject.toml path |
| ecos → omo | 单向 | `mof-state-bridge.py` import `omo.omo_ingress` + `omo.omo_io` |

> ecos 的 `mof-state-bridge.py` 依赖 omo 做 `.omo/tasks/` ↔ M1 OMOTask 双向同步。omo 不反向依赖 ecos。

---

## 快速命令

```bash
cd projects/omo

# 全量测试
uv run pytest tests/ -q

# 治理审计
uv run python -m omo.cli governance audit

# lint
uv run ruff check src/
uv run ruff format src/
```

---

## GOTCHAS

1. **不要在此生成 `.omo/` 运行时数据** — 本仓库只放执行内核
2. **AppendOnlyLog 是 SSOT** — 7 consumers 共享同一物理 JSONL，新增 consumer 只需 import + SCHEMA_REGISTRY 登记
3. **task policy 可扩展** — `omo_task_policy.py` 用注册表承载新红线，不要把规则散落到单独脚本
4. **OMO CLI 是内部程序接口** — 人类用户请使用 `cockpit`
5. **治理审计必须 100.0 A+** — 任何非 A+ 需要注册 OMO Debt 并修复
6. **omo_bos.py 域映射** — Legacy 3-segment `bos://omo/debt` 自动映射到 `bos://governance/debt`
