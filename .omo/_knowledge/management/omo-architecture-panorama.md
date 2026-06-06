# OMO 体系全景架构分析 (v1.0)

> 2026-06-06 | 68 个源文件 / 14,481 行代码 / 70 个测试 / 15 CLI 入口
> 状态: Phase 29-32 实施完成

---

## 一、总体架构

```
┌────────────────────────────────────────────────────────────┐
│                用户接口层 (CLI)                               │
│  omo / omo-debt / omo-mcp / cards                          │
│  15 个入口 → 68 个源文件 → 14,481 行 Python 3.13+         │
└────────────────────────┬───────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌─────────────────┐ ┌─────────┐ ┌──────────────┐
│   控制面 CLI     │ │ 事实面  │ │   基础设施    │
│                 │ │ CLI     │ │              │
│ omo goal        │ │ omo     │ │ omo state    │
│ omo cards       │ │ standard│ │ omo i0       │
│ omo capability  │ │ omo     │ │ omo ledger   │
│ omo metacog     │ │ debt(15)│ │ omo bridge   │
│ omo phase14-16  │ │ registry│ │ omo gc       │
└────────┬────────┘ └───┬─────┘ └──────┬───────┘
         │              │              │
         ▼              ▼              ▼
   ┌──────────────────────────────────────┐
   │         .omo/ 数据层                   │
   │                                        │
   │  _control/  _truth/  _knowledge/       │
   │  _delivery/ debt/    state/            │
   │  goals/     standards/  workers/       │
   │  evidence/  tasks/                     │
   └──────────────────────────────────────┘
```

---

## 二、CLI 命令全景 (37 个子命令)

### omo 入口 (15 个平面命令)

| 命令 | 模块 | 读取 | 写入 | 说明 |
|------|------|------|------|------|
| **goal** | omo_goal.py | list, status | create, progress | Phase 目标管理 |
| **state** | omo_state.py | show, health | refresh | 系统状态 + 运行时桥接 |
| **knowledge** | omo_knowledge.py | list | add | 知识面文档管理 |
| **delivery** | omo_delivery.py | list | archive | 交付物管理 |
| **standard** | omo_standard.py | list | add | 标准文件管理 |
| **i0** | omo_i0.py | status, routes | — | Agora 集成织层查询 |
| **capability** | omo_capability.py | list/query | register | 能力注册表 |
| **metacognition** | omo_metacognition.py | query | analyze | 元认知分析 |
| **phase14/15/16** | omo_phase*.py | status | execute | Phase 执行引擎 |
| **ledger** | omo_ledger.py | query | record | 治理账本 |
| **bridge** | omo_bridge.py | status | sync | 跨系统桥接 |
| **cards** | omo_cards.py | list | add/update | CARDS 追踪 |
| **gc** | omo_gc.py | status | clean | 垃圾回收 |
| **worker** (默认) | omo_worker.py | list/status | dispatch | Worker 调度 (59 funcs) |

### omo-debt (15 个子命令)

```
register → schedule → refresh → dispatch → approve → campaign
→ report → report-history → report-diff → report-trend
→ reclassify → escalate → revalidate → close → reopen
```
(全链路闭环)

### omo-mcp (FastMCP 服务器, 7 个工具)

```
run_worker / list_workers / get_worker_status
cancel_worker / evaluate / run_tasks / governance_ping
```

---

## 三、.omo/ 数据层结构

### 四平面

| 平面 | 目录 | 文件数 | CLI 覆盖 |
|------|------|--------|---------|
| **控制面** | `_control/` | ~10 | goal, cards, phase* |
| **事实面** | `_truth/` | ~8 | standard, capability |
| **知识面** | `_knowledge/` | ~30+ | knowledge list/add |
| **交付面** | `_delivery/` | ~80+ | delivery list/archive |

### 功能模块

| 模块 | 文件数 | CLI 覆盖 | 说明 |
|------|--------|---------|------|
| **debt** | 10 个子目录, 73 items | ✅ 15 子命令 (全链路) | 最成熟 |
| **state** | 3 文件 | ✅ show/health/refresh | 系统状态 SSOT |
| **goals** | 1 current + history | ✅ list/create/progress | Phase 目标 |
| **standards** | 23 文件 | ✅ list/add | 架构标准 |
| **tasks** | active/planned/done | ❌ 无专门 CLI | 任务管理 |
| **workers** | 5 子目录 | ⚠️ omo worker (部分) | Worker 注册表 |
| **evidence** | 2 子目录 | ❌ 无 CLI | 证据链 |
| **PROJECTS.yaml** | 1 | ❌ 无 CLI | 项目清单 |

### CLI 覆盖度

```
读取覆盖:  9/10 模块  (90%) — task 无读取
写入覆盖:  6/10 模块  (60%) — task/evidence/PROJECTS.yaml 无写入
```

---

## 四、代码架构

### 模块依赖

```
cli.py (路由分发)
  │
  ├── omo_goal.py          → omo_io.py (YAML 原子写入)
  ├── omo_state.py         → yaml, subprocess (runtime Matrix)
  ├── omo_knowledge.py     → pathlib (文件读写)
  ├── omo_delivery.py      → pathlib (文件移动)
  ├── omo_standard.py      → pathlib (文件创建)
  ├── omo_i0.py            → urllib (Agora HTTP 查询)
  ├── omo_debt.py          → 14 个子模块 (debt_*)
  ├── omo_worker.py        → 调度引擎
  ├── omo_governance.py    → 治理覆盖
  ├── omo_capability.py    → 能力注册表
  ├── omo_cards.py         → CARDS 追踪
  ├── omo_phase*.py        → Phase 执行
  ├── omo_ledger.py        → 账本
  ├── omo_bridge.py        → 桥接
  └── omo_gc.py            → GC

共享基础设施:
  omo_io.py       — YAML 原子读写
  omo_shared.py   — 通用工具
  omo_redaction.py — 敏感信息脱敏
  omo_metrics.py  — 指标收集
  omo_rules.py    — 规则引擎
  omo_discovery.py — 服务发现
```

### 各模块代码量

```
omo_worker.py         2,142 行  (最大 — 调度引擎)
omo_debt.py           1,048 行  (+ 14 子模块 = 3,132 行)
omo_governance.py     1,200+ 行 (含 overlay 子模块)
omo_phase*.py         3,026 行  (3 个 Phase)
omo_promotion*.py     934 行    (8 个子模块)
omo_capability.py     600+ 行
omo_goal.py           105 行    (新)
omo_state.py          103 行    (新)
omo_knowledge.py      80 行     (新)
omo_delivery.py       75 行     (新)
omo_standard.py       71 行     (新)
omo_i0.py             75 行     (新)
cli.py                72 行     (路由)
```

---

## 五、5+3+1 映射

| 架构层 | OMO 覆盖 | 依赖的外部系统 |
|--------|---------|---------------|
| **L0 协议编织** | `omo_standard` standards/ | projects/runtime/protocols/ |
| **L1 运行时矩阵** | `omo_state refresh` → health.yaml | projects/runtime (Matrix CLI) |
| **L2 OMO 治理面** | **全部 OMO CLI** — goal/debt/state/... | .omo/ 目录自身 |
| **L2 kairon 引擎面** | — (omo 不直接管理 kairon) | kairon 包 |
| **L2 gbrain 记忆面** | — (omo 不直接管理 gbrain) | gbrain API |
| **L3 入口桥接** | `omo i0` 查询 Agora | Agora (端口 7430) |
| **L4 自我层** | `cards` 命令 | ~/Documents/驾驶舱/CARDS/ |
| **I0 集成织层** | `omo i0 status/routes` | Agora HTTP API |
| **X1 治理安全** | `omo_debt`, 标准文件 | KEI sandbox |
| **X2 抗熵** | `omo state refresh` | scheduler.py freshness |
| **X3 价值栈** | ❌ 未实现 | 无 |
| **P0 产品** | ❌ 未实现 (hermes-console) | 前端构建工具 |

---

## 六、测试健康

```
测试文件:   70 个
测试需要:   --run-real-omo 标记 (31 个模块)

测试分布:
  test_omo_debt*.py                   — 债务全链路
  test_omo_automation.py    4,028 行  — 自动化
  test_worker_lifecycle.py  1,392 行  — Worker 生命周期
  test_omo_governance*.py             — 治理
  (新模块: goal/state/knowledge 等无测试)
```

**新模块测试缺口**: omo_goal/state/knowledge/delivery/standard/i0 — 6 个新模块零测试。

---

## 七、集成关系

```
OMO CLI  ↔  I0 (Agora:7430)  ↔  kairon/agora
         ↔  L1 (projects/runtime)  ↔  Matrix/KEI
         ↔  L4 (~/Documents/CARDS/)  ↔  驾驶舱
         ↔  L3 (projects/hermes-console)  ↔  MCP 协议
         ↔  .omo/ (自身数据层)  ↔  治理文件
```

### 连接方式

| 外部系统 | 连接协议 | OMO 模块 |
|---------|---------|---------|
| Agora | HTTP (localhost:7430) | omo_i0.py |
| Runtime Matrix | subprocess (runtime CLI) | omo_state.py |
| L4 CARDS | 文件读写 | omo_cards.py |
| KEI Sandbox | 文件读写 (kei_audit.jsonl) | 无 (通过 runtime CLI) |

---

## 八、缺口与风险

### 功能缺口

| 缺口 | 影响 | 优先级 |
|------|------|--------|
| 新 6 CLI 模块无测试 | 功能退化风险 | 高 |
| task 无 CLI 命令 | 任务管理全靠手动 YAML | 中 |
| evidence 无 CLI | 证据链全靠手动 | 低 |
| X3 价值栈零实现 | 无成本追踪 | 低 |
| hermes-console 构建失败 | 产品面停摆 | 高 |
| omo 测试需要 --run-real-omo | 非 CI 友好 | 中 |

### 架构风险

| 风险 | 说明 |
|------|------|
| **单模块膨胀** | omo_worker.py (2,142行) + omo_debt.py + 14子模块 (3,132行) — 需要关注 |
| **无自动化回归** | 70 个测试但 31 个需要 --run-real-omo |
| **连接脆弱** | omo_i0 和 omo_state 依赖外部服务 (Agora/runtime) 在线 |
| **新老模块脱节** | 新 6 模块 (goal/state/knowledge/delivery/standard/i0) 与老 14 模块 (debt/worker) 使用不同的 arg 解析方式 |
