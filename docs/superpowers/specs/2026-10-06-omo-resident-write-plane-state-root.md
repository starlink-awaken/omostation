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

## 5 跨仓消费面（I3 检测器实测结论，2026-10-06）

§5 的原始问题（「root 侧读者是否已经走 `state_root()`」）现在由检测器回答，不再靠措辞：
`tests/unit/test_resident_write_plane_split.py` 把 omo 侧**写者解析根**与 root 侧**读者解析根**
逐路径对照，允许清单钉成集合相等（判据-5）。

### 5.1 实测读数

| 量 | 读数 |
|---|---|
| omo 侧落到 state 根的路径族 | **18** |
| 其中有 `bin/` 活消费者的族 | **15**（其余 3 族自写自读：`sediment-archive`、`state/resident-heartbeat.jsonl`、`state/resident-monitor.jsonl`） |
| (族, 读者文件, 类) 对照项 | **33 条精确同根 + 17 条祖先同根 = 50** |
| 涉及的 `bin/` 文件 | **32 个**，分布在 **10 个目录** |
| 读者类分布 | `CHECKOUT 41 / CALLER 6 / DERIVED 3 / STATE 0` |

⇒ **决定性事实：`bin/` 里没有一个读者解析到 state 根**（`STATE-class reader pairs = 0`）。
声明 profile 后，omo 写者搬到 state 根、`bin/` 读者仍逐字读检出 —— 读写**不同根**，
且这不是漏改，而是 `bin/` 的 32 个文件本身没有一处走 `state_root()`。

### 5.2 因此 I3 本轮判定为「未达成，已钉住」

- 闭合 I3 需要改 `bin/` 那 32 个读者，而台账 `circuit_breaker` 写的正是这种情况：
  「§5 实测表…以致需要改 `bin/` 读者才能不产生 split —— 那说明本轮范围判断错，**停下登记而不是扩大 PR**」。
- 所以检测器把 50 条对照项钉成**登记在册的现状**（`SPLIT_EXACT` / `SPLIT_ANCESTOR` 两张表 +
  集合相等断言），而不是宣布读写同根。**B1 的 done_when 不得据本轮宣布完成**（§8）。
- 读者类里 `CALLER`（6 条）是根由调用方传入的，证据逐条钉在 `CALLER_EVIDENCE`
  （如 `bin/gac/fix-frontmatter.py` 的 `--batch ROOT`，它**不**锚检出，是运算符供给的根）；
  `DERIVED`（3 条）全部指向 `bin/_archive/**`。

### 5.3 本轮范围外、但检测器点到的残留（登记，不静默扩面）

| 残留 | 位置 |
|---|---|
| 第 3、4 处 ledger 口径 | `omo/event_ledger/surface.py:41`、`omo/sovereignty/enforcement.py:120` |
| `default_db_path()` 宿主自身 | `omo/resident/task_queue.py:834`、`:977`（22 面之外，三个调用方已在 `write_path()` 重锚） |
| 仍挂检出的 resident 内联写者 | `connectors_poll.py`、`sema_crystallizer.py`、`task_queue.py`，以及 `swarm_custodian.py` —— 后者的根**不是** `__file__` 而是 cwd：`find_workspace_root()`（`resident/swarm_custodian.py:20-26`）从 `Path.cwd()` 往上找 `.gitmodules`/`docs/project-registry.yaml` 标记，命中即返回**检出**，然后写 `runtime/omo/architecture_graph.sqlite3`（`:35`）。cron 因为 `cd ${WORKSPACE}` 才碰巧正确；profile 对它完全不可见 |
| 台账优先级的第二处实现 | `resident/status.py:44` 直接 `os.environ.get(LEDGER_DB_ENV)` 探测后再决定走 `event_ledger_path()` 还是 `write_path(LEDGER)` —— 语义与解析器一致，但它是优先级链的第二份副本。保留原因写在它的 docstring 里：12 处用例把 `status.LEDGER` 当属性缝用，该测试文件在本 BET 的 22 面之外 |
| 协调面**永久例外**（判据-4） | `resident/execute.py` —— `.omo/_delivery/agent-workflows/**` 两侧都留 CHECKOUT |
| cron 显式传参 | `bin/ssot/install-resident-cron.sh:49`、`:53` 的 `--ledger ${WORKSPACE}/runtime/...`（B4 面） |
| ledger 覆盖优先级不对称 | 相对路径时 `bin/lib/repo_root.py::event_ledger_path` 返回 `Path(env).expanduser()`（实测 `:98`，**不** `.absolute()`），`omo_paths::event_ledger_path` 返回 `.expanduser().absolute()`（实测 `:64`）—— 钉为 `LEDGER_OVERRIDE_ASYMMETRY` |

### 5.4 对 §2/§6 早期措辞的实测更正

- 「修 2 个钉死路径的测试」偏小：omo 侧把常量当**属性**读、改成函数会打断的 `setattr`/属性缝实测 **89 处**，
  本轮只显式适配了台账列出的那 2 个用例，其余由「常量保留、读点经 `write_path()`」这一形状绕开
  （这正是 §2 结论「机制在写点、不在常量」的执行理由）。
- 「10 个路径族」（台账 `circuit_breaker` 措辞）实测为 **18 族 / 15 族有跨仓读者 / 50 条对照项**。
- 方案 line 138 给 B1 的第三项「`OMO_PRINCIPAL_ID` 接入」在 **omo 侧是空项**：实测
  `projects/omo/src/omo/**` 对 `OMO_PRINCIPAL_ID` **0 命中**，包内一律把 `principal_id` 当**参数**传递
  （264 处 `principal_id` 命中里没有一处读 env）；`resident/**` 只有 2 处 env 读
  （`status.py:44` 的 `OMO_EVENT_LEDGER_DB`、`swarm_custodian.py:22` 的 `WORKSPACE_ROOT`）。
  收敛早已在 root 侧完成（`bin/ssot/_principal_id.py`，30 处引用），且台账
  `docs/plans/3y-bet-ledger.yaml:40564` 明写「Do not re-do OMO_PRINCIPAL_ID convergence」。
  ⇒ B1 的这一项按「无对象」判定，不为凑范围而翻 omo。
- 方案 line 138 给 B1 的第二条 grep 判据实测：`DEFAULT_(EVENT_)?LEDGER\s*=` 在 `bin/` 与
  `projects/omo/src/` 双双 **0 命中**（本轮删掉 `daemon.DEFAULT_LEDGER` 后成立）。



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
- **判据-6**：`make gac-local-gate` 无新增硬失败；omo 侧 `pytest tests -q` 相对基线无回归（实测见 §9）。

## 8 非目标

- 不改任何 resident 业务逻辑、事件语义、checkpoint 算法或 handler 路由。
- 不改 `bin/ssot/install-resident-cron.sh`、launchd plist、crontab（B4b 批次 2+，逐批授权）。
- 不翻 `omo_paths.STATE_ROOT` 常量为函数（120 refs / 16 files，与本判据无关的翻动）。
- 不把 `.omo/_knowledge/**` 生成态摘库（那是 task #112 的独立 BET，且它有自己的写者归属问题）。
- 不改 `bin/` 的 32 个读者（§5.1）—— 那需要单独一轮，且台账 `circuit_breaker` 明令「停下登记而不是扩大 PR」。
- **不宣布 B1 完成**：§5 的跨仓读者结论本轮已落地，落点是「读写同根**未**达成 ——
  `bin/` 侧 0 个读者走 state 根」。B1 的写面机制两仓齐备、行为判据实测达成（§9.1），
  但 I3 的闭合依赖读者迁移，属于下一轮范围判定，不在本文里被措辞抹平。

## 9 实跑记录（2026-10-06，worktree `ws-omo-resident-stateroot`）

### 9.1 判据-2 dev canary：`expect=29 got=29`

一次性驱动脚本 `/tmp/t233/canary-write-plane.py`（**不落 `bin/`** —— 台账 `circuit_breaker`
禁止本轮扩 `bin/` 面），转写 `/tmp/t233/canary-run-1.txt`。被监视面 = 两个检出的
`.omo/**` + `runtime/**` 全量 (size, mtime_ns) 集合 + `git status --porcelain`，
外加机器级共享面 `~/Workspace`（实测 15 854 条目，`added=0 changed=0`）。

| 相 | 命令 | 结果 |
|---|---|---|
| **A（判据字面）** | `OMOSTATION_STATE_ROOT=<tmp> python -m omo.resident.daemon --once --topic-filter __canary_no_subscriber__` | `rc=0`，tick 报告 `processed=1`；检出两树**零新增/零删除/mtime 集合不变/porcelain 不变**；state 根出现 watermark、`daemon.log`(6 行)、`receipts.jsonl`(2 条 attempted+ok)、`runtime/omo/event-ledger.sqlite3` |
| **B（补相）** | 同上但 `--interval 0.4`，运行中快照后 `SIGTERM` | `daemon.pid` **在运行中出现**且内容是一个在跑的进程；log 含 `resident_orchestrator_started` / `tick_done` / `resident_orchestrator_stopped`；退出后 pid 清理；检出面照旧零变化 |

两条**诚实边界**（判据措辞比可观察事实强，不改窄判据，如实登记）：

1. **pid**：`--once` 分支在返回前 `pid_file.unlink(missing_ok=True)`（`daemon.py:482`），
   所以「state 根里出现 pid」在 `--once` 单次运行里**按构造只能在运行中观察到**，
   落盘即清理是设计行为 —— 相 B 用循环模式把这一条看住了，可断言的是「pid 落在声明的 state 根」。
2. **log/receipt**：`--once` 本身不调 `_log()` 也不调 `_receipt()`（两者只在 handler 路由与循环分支触发），
   所以判据里这两项**需要一个真的被路由的事件**。相 A 因此在 **state 根的** `events.jsonl`
   里预置一条 `event_type=__canary_no_subscriber__` 的合成事件（routes YAML 无此规则 →
   落到 `_handler_placeholder`、`safe=True`，不执行任何业务 handler，也不需 `--yes`）。

### 9.2 判据-6 基线对照：10 项失败与本轮 diff 无交集

`pytest tests -q`（`.subtrees/omo`，未声明 profile）实测 **10 failed / 2976 passed / 216 skipped**。
10 项全在 `tests/integration/test_bos_40_uri_smoke.py` 与 `test_bos_domain_chain.py`，
失败原因是路径推导，不是断言内容：

```
FileNotFoundError: .../ws-omo-resident-stateroot/.subtrees/.omo/_knowledge/bos-registry.json
```

这两个文件用 `Path(__file__).resolve().parents[3]` 反推工作区根（`test_bos_domain_chain.py:17-18`、
`test_bos_40_uri_smoke.py:32`）。在 `projects/omo` 布局下 `parents[3]` 命中工作区根，
在 PASW 的 `.subtrees/omo` 布局下命中 `<wt>/.subtrees` —— **差一层，与 diff 无关**。
可核验的三条：① `git diff --name-only` 不含这两个文件；② 同一份文件在
`projects/omo`（改前基线检出）单跑这 11 个用例 → **11 passed**；③ 本轮没有改
`WORKSPACE_ROOT` 的推导（§2 明确保留）。⇒ 判据-6 的「相对基线无回归」按此成立；
它同时是 AGENTS.md §7「用例/检查器里被检对象的根不得由 `__file__` 反推」的又一实例，
登记为残留而非本轮修复（这两个文件在 22 个 `write_surfaces` 之外）。
