---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: cross-repo-probe-runtime-metaos-2026-06-10.md
deprecated-since: 2026-06-23

---

# Cross-Repo Probe: runtime / metaos — 2026-06-10

> **状态**: 探查报告 (Round 19 P1 落地)
> **动机**: §11.6 P2 跨仓推广剩余 1 债 (runtime / metaos 探查)
> **结论**: 2 仓**均未用 JSONL 模式** — 正是 Rollout Guide 推广目标
> **属性**: 历史跨仓探查记录 / reference only。本文记录当时探查样本，不是当前 runtime/metaos 能力面、当前 MCP/CLI 数量或当前落地状态 SSOT。

---

## §0 探查范围

| 仓 | 路径 | 类型 | 状态 |
|----|------|------|------|
| **runtime** | `projects/runtime/` | Python (uv + 多个 service) | 大仓, build/lib 已成熟 |
| **metaos** | `projects/metaos/` | Python (uv + pytest) | L2 编排引擎, 11 MCP tools, 12 CLI |

---

## §1 探查方法

```bash
# 1. 找 .jsonl 引用
rg -l "\.jsonl" projects/runtime/src/ projects/metaos/src/

# 2. 找 JSONL 写入点 (json.dumps + open + append)
rg -l "json\.dumps.*append" projects/runtime/ projects/metaos/

# 3. 看 INTERFACE / protocols 契约
cat projects/metaos/INTERFACE.yaml
ls projects/runtime/protocols/
```

---

## §2 探查结果

### §2.1 runtime 仓 (L1 运行时)

**结构**:
- `build/lib/runtime/` — 12+ 模块 (`__init__`, `__main__`, `bus_consumer`, `cli`, `i0`, `kei`, `mcp_server`, `protocol`, `scheduler`, `state_schema`, `stdio_rpc`, `taskobject_adapter`, `runtime_serve`)
- `cron_service/` — 独立 service (scheduler / executor / delivery / mcp_server)
- `executor/` — agent 执行池 (agent_executor, agent_hub, agent_pool, agent_runner, agent_skills, ...)

**JSONL 现状**: ❌ 0 引用 — `rg "\.jsonl"` 无结果
**Logging 现状**: structlog (Python stdlib 三方库, 非 append-only JSONL)
**写入点特征**: 散在 `bus_consumer` / `scheduler` / `executor` 多个模块的 `logger.info()` 调用

**适用 AppendOnlyLog 模式的点**:
- `cron_service/scheduler.py` — 定时任务执行记录 (目前 structlog)
- `executor/agent_runner.py` — agent 运行记录 (含 duration, parent task, actor)
- `executor/checkpoint.py` — agent 状态 checkpoint (适合 trail record)

### §2.2 metaos 仓 (L2 编排引擎)

**结构** (10+ 模块):
- `metaos.py` / `metaos_main.py` — 入口
- `l2_controller.py` — L2 决策门控
- `deadlock_detector.py` — 死锁检测
- `dashboard.py` — 仪表盘
- `mcp_server.py` — MCP server (11 tools)
- `onboard.py` / `run.py` — 启动 / 运行
- `core/workflow_parser.py` — 工作流解析

**JSONL 现状**: ❌ 0 引用 — `rg "\.jsonl"` 无结果
**Logging 现状**: structlog (同 runtime)
**写入点特征**: `metaos_main.py` + `l2_controller.py` + `dashboard.py` 多处 `logger.info/warn`

**适用 AppendOnlyLog 模式的点**:
- `l2_controller.py` — 决策门控记录 (gate / review 事件) — 适合 omo_audit 风格
- `core/workflow_parser.py` — 工作流解析轨迹 — 适合 omo_trail 风格
- `dashboard.py` — 仪表盘状态快照 — 适合 omo_history 风格

---

## §3 推广建议 (按 §3 跨语言推广路径)

### §3.1 优先级矩阵

| 仓 | 模块 | 改造优先级 | 价值 | 风险 |
|----|------|----------|------|------|
| metaos | `l2_controller.py` | **P0** | 决策门控是治理核心, 写时锁守住 X1 审计 | 中 (需协调 L2 接口) |
| metaos | `core/workflow_parser.py` | P1 | 解析轨迹是 trail 风格天然场景 | 低 |
| runtime | `executor/agent_runner.py` | P1 | agent 跑 = trail record 完美映射 | 低 |
| runtime | `cron_service/scheduler.py` | P2 | 调度记录是 audit 风格 | 中 |
| runtime | `executor/checkpoint.py` | P2 | checkpoint 是 trail 风格 | 低 |

### §3.2 接入 5 步 (按 Rollout Guide §1)

1. **copy `omo_io.AppendOnlyLog`** → `runtime/src/runtime/io.py` (10 行)
2. **定义 Pydantic schema** → `runtime/src/runtime/io_schemas.py` (per consumer)
3. **接入 consumer** → 改 `executor/agent_runner.py` 用 `record_step(...)` (3 行)
4. **加 audit CLI** → `runtime/src/runtime/cli.py` 加 `runtime audit` (50 行)
5. **CI 集成** → `.github/workflows/ci-lint.yml` 加 `runtime-audit` job (20 行)

### §3.3 跨语言推广路线 (Round 20+ 候选)

- **Python 仓** (runtime / metaos / kairon): 直接 copy 模式, Pydantic schema, 5 步接入
- **TypeScript 仓** (gbrain): zod 替换 Pydantic, gbrain 已有 audit-week-file.ts 抽象
- **Go 仓** (暂无, 但 kairon 仓可能是 Go): go-playground/validator
- **Rust 仓** (暂无): serde + validator derive

---

## §4 风险评估 (YAGNI 边界)

按 Rollout Guide §5 "不适用场景"：
- **runtime 大仓** — 改造影响面广, 建议**先小范围试点** (e.g. 只在 `executor/agent_runner.py` 走 trail record)
- **metaos L2 引擎** — L2 改动需 L0 协议同步 (INTERFACE.yaml 改), 走 mof-scan 卡口
- **submodule 边界** — CLAUDE.md 说"submodule 单独 lint, 跨仓 commit 风险高", 改造需各仓 owner 配合

**短期建议 (本报告范围内)**:
- 0 行代码改动 (探查报告 + 推广建议, 不动 submodule)
- 文档驱动 — runtime / metaos 各 owner 按 Rollout Guide 自取
- Round 20+ 候选: metaos `l2_controller.py` 试点 (需 metaos owner 配合)

---

## §5 度量 (探查本身)

- 探查耗时: ~5 min (rg 5 搜 + INTERFACE/protocols 读)
- 探查产出: 0 行代码改动, 1 份报告 (~150 lines), 0 风险
- 价值: 让 §11.6 P2 跨仓推广的"runtime / metaos 探查"债从"未知"变"已知", 可分阶段推进

---

## §6 后续 (Round 20+ 候选)

- [ ] **A. metaos l2_controller 试点** (优先级最高, 需 metaos owner 配合) — Rollout Guide §1 5 步接入
- [ ] **B. runtime executor/agent_runner 试点** — trail record 接入, 评估 agent 跑数据价值
- [ ] **C. cross-repo 同步 baseline** — 跨仓 `omo audit` 报告汇聚到 `workspace/.omo/_delivery/audit-rollout/`
- [ ] **D. kairon 探查** (前面 kairon 是 meta-stub, 实际跨仓推广目标可能不在)

---

## §7 §11 SSOT 关系

- **§11 X1 审计契约**: 推广到 runtime/metaos 后, 跨仓审计从 omo 1 仓扩到 N 仓
- **§11 X2 保鲜**: 各仓 baseline-init 时点统一 (建议: 每月 1 号, GitHub Action cron)
- **§11 X3 价值**: 模式复用 → 治理覆盖度从 omo 内部 → 整个 omostation 生态
- **§11 X4 一致**: 1 套 `AppendOnlyLog` 物理 + 1 套 Pydantic/zod schema 思路, 跨语言
