---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B1 的 omo 侧收口 — omo.resident 写面按 profile 落到 state 根
bet_id: BET-Y2Q4-T10-233
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-06
---

# B1 的 omo 侧收口 — 让 `resident daemon --once` 真的只写 dev state root

## 1 为什么 B1 的 done_when 现在按构造做不到

方案 `nimble-bay-asp.md` line 138 给 B1 的第二条判据是一个**行为**判据，不是 grep：

> `OMOSTATION_PROFILE=dev … resident daemon --once` 只写 dev state root

BET-Y2Q4-T10-232（PR #4651 → `317bc0315`）把 `bin/` 侧 14 处 import 时冻结的 profile 根常量改成
调用时刻解析，但那一条的 `circuit_breaker` 明确把「`projects/omo` 的 `resident/daemon.py` 分叉」列为
非目标。本轮就是那个后继。

实测（2026-10-06，worktree `ws-omo-resident-stateroot`，**import 之前**就声明
`OMOSTATION_STATE_ROOT=<tmp>` 与 `OMO_EVENT_LEDGER_DB=<tmp db>`，再导入模块读它们的模块级常量）：

| 常量 | 实测解析结果 | 跟随声明的 state 根 |
|---|---|---|
| `omo.resident.daemon.DEFAULT_LEDGER` | `<checkout>/runtime/omo/event-ledger.sqlite3` | ❌ |
| `omo.resident.daemon.PID_FILE` | `<checkout>/.omo/_delivery/resident-orchestrator/daemon.pid` | ❌ |
| `omo.resident.daemon.LOG_FILE` | `<checkout>/.omo/_delivery/resident-orchestrator/daemon.log` | ❌ |
| `omo.resident.receipt.RECEIPTS_FILE` | `<checkout>/.omo/_delivery/resident-orchestrator/receipts.jsonl` | ❌ |
| `omo.resident.status.LEDGER` | `<checkout>/runtime/omo/event-ledger.sqlite3` | ❌ |
| `omo.resident.heartbeat.HEARTBEAT_LEDGER` | `<checkout>/.omo/state/resident-heartbeat.jsonl` | ❌ |
| `omo_paths.STATE_ROOT`（对照） | `<tmp>` | ✅ |

即：**同一个包里两套根口径** —— `omo_paths` 认识 profile，`omo.resident` 完全不认识。

## 2 根因比「import 时冻结」低一层

BET-232 那一轮的缺陷形状是「值在 import 时求值」。本轮 AST 全量度量
（`.subtrees/omo/src/omo/resident/*.py`，只看**模块级赋值**且右值含 `WORKSPACE`/`STATE_ROOT`）：

```
15 个模块 / 32 个模块级常量 = 17 WRITE + 14 AMBIG + 2 read
   （WRITE 由调用点分类：write_text/mkdir/unlink/touch/open/connect/replace/rename）
```

但把 32 个常量逐个改成函数**不会改变任何行为**，因为它们的公共锚是：

```python
# projects/omo/src/omo/resident/__init__.py:16
WORKSPACE = Path(__file__).resolve().parents[5]
```

这行既不读 `OMOSTATION_STATE_ROOT`，也不读 `OMOSTATION_ROOT`，更不是 `omo_paths.STATE_ROOT`。
⇒ 真正的缺陷是**这个包没有 state 根概念**。因此本轮的机制在前、翻动在后：

1. `omo_paths` 增加**调用时刻**解析器（每次调用读 env，不在模块级求值）：
   `state_root()` 与 `event_ledger_path()`，与 `bin/lib/repo_root.py` 同契约、同优先级
   （`OMO_EVENT_LEDGER_DB` > `state_root()/runtime/omo/event-ledger.sqlite3`）。
   `STATE_ROOT` 常量本身**不动** —— 实测 120 refs / 16 files 消费它，本轮不制造无关翻动。
2. `omo.resident` 的**写面**（17 WRITE + 分类出的 AMBIG）改挂 `state_root()` /
   `event_ledger_path()`，在**调用时刻**取路径。读面（`bin/gac/*.sh`、`resources.FABRIC_REGISTRY`、
   `status.LEDGER` 之类只读探测）留在 `WORKSPACE`：ADR-0456 的读面契约本就是「跟随当前检出」。

## 3 为什么这不破坏在跑的 resident 服务（关键安全性论证）

`state_root()` 在**未声明** `OMOSTATION_STATE_ROOT` 时等于 `WORKSPACE_ROOT` —— 这正是
`omo_paths` 现有 docstring 承诺的不变量（「未声明 profile 时 STATE_ROOT == WORKSPACE_ROOT，
逐字节复现历史路径」）。launchd 与 crontab 都不声明该 env，所以：

- 现役 43 个 plist / cron 跑起来解析结果与今天**逐字节相同**，PID/LOG/receipt/watermark 不会换位置；
- 只有显式声明 profile 的调用（本轮验收的 dev canary）才会落到 state 根。

⇒ 本轮**不需要**碰 `bin/ssot/install-resident-cron.sh`（那是方案 line 145 划给 B4 的
`launchctl bootstrap` 换路径，且 B4b 批次 2+ 需逐批授权）。这是「机制先于搬家」的一次，
不是搬家。

## 4 不变式

- **I1 等价**：未声明 profile 时，每个被迁移的解析点得到的路径字符串与改前逐字节一致。
- **I2 调用时刻**：env 在 **import 之后**声明也必须生效（BET-232 的同族判据；现有 omo 用例都在
  setenv 之后才构造路径，覆盖不到这个窗口）。
- **I3 单一口径**：同一个相对路径在两个仓里不得一个挂 state 根、一个挂检出 —— 那正是本轮实测到的
  `evidence-smoke` 残留形状（`check-evidence-freshness.py` 用 `__file__` 反推检出，写者已偏到
  state 根，`SPLIT = True`）。判据必须由**检测器点名**，不得由本文措辞断言。
- **I4 自证**：源码扫描按 **resolver** 匹配（`state_root(` / `event_ledger_path(`）而非变量名；
  先用合成违规样本证明检测器点名文件+行+变量名，再断言真实扫描集合为空；并反向断言读面**不被**命中
  （防过宽 detector 靠豁免清单蒙混）。
- **I5 行为验收**：`--once` 的真实运行落点由一次实跑产出，不是改窄用例。

## 5 跨仓消费面（实测计数，决定 I3 检测器的枚举范围）

| 相对路径 | 跨仓引用 | 文件 |
|---|---|---|
| `runtime/omo/event-ledger.sqlite3` | 23 refs / 11 files | root 侧 8 处在 `tests/unit/test_b1_ledger_call_time.py`（BET-232 新增），真实消费者含 `bin/bc-os/north_star_meter_v2.py`、`bin/panorama/panorama-collect.py` |
| `.omo/_knowledge/workflow-mesh/events.jsonl` | 10 refs / 9 files | 写者 `ingest/promote/ledger_trace`，读者 `bin/panorama/*`、`bin/ssot/event-ingest-adapter.py` |
| `.omo/_delivery/observability/events.jsonl` | 10 refs / 10 files | `alert.py` 写，`bin/compass_radar.py`、`bin/gac/gac-local-gate.py`、`bin/ssot/*` 读 |
| `.omo/_knowledge/sediment/` | 9 refs / 6 files | `sediment/promote` 写，`bin/ssot/knowledge-sediment.py` 读 |
| `.omo/state/resident-heartbeat.jsonl` | 7 refs / 5 files | `heartbeat.py` 写，`bin/panorama/panel-collect.py` 读 |
| `.omo/_delivery/resident-orchestrator/` | 4 refs / 1 files | 全部在 `bin/ssot/install-resident-cron.sh`（B4 面，本轮不改道） |
| `.omo/state/resident-monitor.jsonl` | 1 ref | 仅 `monitor.py` 自写自读 |

⚠️ 上表的引用点是**字面路径**命中；「root 侧读者是否已经走 `state_root()`」这一问，本文**不作断言**
—— 一次 6 行窗口启发式的初步探测命中的多数是 docstring 行，读数不可信（AGENTS.md §7「扫源码的门禁
必须自证」）。该事实由 §5 之外的 I3 检测器在真实代码上跑出来后决定：检测器点名哪些跨仓读者，就迁移哪些；
点名不了 split 的，登记为残留而不是写进契约。

## 6 交付面

- `projects/omo/src/omo/omo_paths.py` — 增 `state_root()`、`event_ledger_path()`（调用时刻）。
- `projects/omo/src/omo/resident/{daemon,status,receipt,ledger_trace,ingest,heartbeat,monitor,
  signals,alert,inbox,sediment,promote,decision,execute}.py` — 写面改挂解析器；
  `__init__.py` 增 state 根出口。
- `projects/omo/tests/unit/test_resident_daemon.py:363`、`projects/omo/tests/integration/
  test_resident_roles.py:207` — 两处把 `daemon.DEFAULT_LEDGER` / `DEFAULT_EVENTS_JSONL` 当**属性**读，
  常量改函数会当场打断（BET-232 的同款教训：改名成函数会破坏 monkeypatch/属性缝）。本轮显式适配。
- `projects/omo/tests/unit/test_omo_resident_state_root.py`（新）— I2 正向落点 + I4 自证 + I1 等价。
- `tests/unit/test_resident_write_plane_split.py`（新，root 侧）— I3 读写同根检测器，允许清单钉成集合相等。

## 7 验收（逐条可跑）

- **判据-1**：`OMO_EVENT_LEDGER_DB=<tmp db>` 与 `OMOSTATION_STATE_ROOT=<tmp state>` 在
  **import 之后**声明，不传参调用 `daemon` 的 ledger 解析点、`status.LEDGER`、
  `receipt.RECEIPTS_FILE`、`_watermark_path()`、`PID_FILE`/`LOG_FILE`，实测全部落在声明位置。
- **判据-2**：`OMOSTATION_STATE_ROOT=<tmp> omo resident daemon --once` 真实跑一次，断言
  **检出目录零新增/零 mtime 变化**，且 state 根里出现 PID/log/receipt/watermark（`expect=N got=N` 打印）。
- **判据-3**：`env -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB` 时每个迁移点的路径与改前
  逐字节一致（I1）。
- **判据-4**：I4 自证三段（合成违规点名 → 真实扫描为空 → 读面不被命中）。
- **判据-5**：I3 检测器在两个仓上跑，输出「写者解析根 vs 读者解析根」逐路径对照；允许的不对称钉成
  集合相等并逐条附理由文件。
- **判据-6**：`make gac-local-gate` 无新增硬失败；omo 侧 `pytest tests/unit -q` 相对基线无回归。

## 8 非目标

- 不改任何 resident 业务逻辑、事件语义、checkpoint 算法或 handler 路由。
- 不改 `bin/ssot/install-resident-cron.sh`、launchd plist、crontab（B4b 批次 2+，逐批授权）。
- 不翻 `omo_paths.STATE_ROOT` 常量为函数（120 refs / 16 files，与本判据无关的翻动）。
- 不把 `.omo/_knowledge/**` 生成态摘库（那是 task #112 的独立 BET，且它有自己的写者归属问题）。
- 不宣布 B1 完成：B1 还需要 §5 的跨仓读者结论落地后才能判定。
