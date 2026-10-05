---
schema_version: specification/v1
spec_version: 1.0.0
title: B1 残留收口 — bin/ 写面常量的调用时刻解析
bet_id: BET-Y2Q4-T10-231
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-05
---

# B1 残留收口 — bin/ 写面常量的调用时刻解析

## 为什么 B1 还没有完成

方案 `nimble-bay-asp.md` line 138 给 B1 的判据是一行字面 grep：

```
grep -rE "DEFAULT_(EVENT_)?LEDGER\s*=" bin/   →   0 命中
```

2026-10-05 实测：**未满足**。命中的是 8 个模块级赋值，且它们不是硬编码字面量，而是
`= event_ledger_path()` —— 在 **import 时求值一次并冻结**。同一族的还有 6 个由
`state_root()` / `runtime_state_root()` 派生的常量。合计 **14 个常量、32 个使用点**
（全部在函数体内；12 个定义文件实测**零跨模块 importer**，唯一读者是
`tests/test_evidence_smoke_paths.py` 的属性断言，本轮一并适配）。

| # | 常量 | 位置 | 使用点 |
|---|---|---|---|
| 1 | `DEFAULT_LEDGER` | `bin/bc-os/north_star_meter_v2.py:66` | `:361` `:401` 默认参数, `:459` argparse |
| 2 | `DEFAULT_EVENT_LEDGER` | `bin/bc-os/north_star_meter_v3.py:190` | `:151` 函数体内回退, `:290` 默认参数, `:793` argparse |
| 3 | `DEFAULT_EVENT_LEDGER` | `bin/bc-os/weekly-value-report.py:38` | `:144` 默认参数, `:178` argparse |
| 4 | `DEFAULT_LEDGER` | `bin/gac/compound-attribution-report.py:49` | `:218` 默认参数, `:285` argparse |
| 5 | `DEFAULT_LEDGER` | `bin/ssot/resident-orchestrator-daemon.py:30` | `:340` argparse |
| 6 | `DEFAULT_LEDGER` | `bin/ssot/episode-source-aggregator.py:38` | `:434` main 内回退 |
| 7 | `DEFAULT_DB` | `bin/gac/check-episode-pipeline.py:54` | `:64` `_resolve_db()` |
| 8 | `LEDGER` | `bin/ssot/system-health-check.py:30` | `:86` `:92` `_check_ledger()` |
| 9 | `OUTPUT_DIR` | `bin/gac/evidence-smoke.py:110` | `:804` `:805` `:870` |
| 10 | `SNAP_DIR` | `bin/gac/task-inventory.py:39` | `:175` `:177` |
| 11 | `DRIFTS` | `bin/gac/task-inventory.py:40` | `:179` `:180` |
| 12 | `SYSTEM_YAML` | `bin/mof/generate-brief.py:22` | `:388` `:390` |
| 13 | `STATE_ROOT` | `bin/gac/omo-state-write-guard.py:29` | `:30`（传递进 `SYSTEM_YAML`） |
| 14 | `SYSTEM_YAML` | `bin/gac/omo-state-write-guard.py:30` | `:41` `:44` `:166` `:181` `:250` `:251` `:259` |

注：方案 line 84 写的是 `bin/gac/system-health-check.py:27`，实测该脚本在
**`bin/ssot/system-health-check.py:30`**（目录不同、行号不同）。本 spec 按实测路径记账。

## 根因：上一轮的判据本身是假绿

这条残留能活 9 天，不是漏改，是**验收判据按构造不可能报警**。
`BET-Y2Q4-T10-203` 的 verify-3（台账 `:35988`）是：

```
grep -rEn "^(DEFAULT_(EVENT_)?LEDGER|LEDGER|DEFAULT_DB) *=" bin/ | grep -c "event-ledger" || true
expect: 0 — no bin/ script computes the event-ledger default itself any more
```

T10-203 把字面量换成 `event_ledger_path()` 之后，第一段命中的行里含的是
**下划线** `event_ledger_path`，第二段过滤的是**连字符** `event-ledger` ⇒ 第二段恒 0，
`|| true` 又把退出码吃掉。也就是说：该判据在它自己交付的那一刻起就**结构性失效**，
之后无论 bin/ 里攒出多少个冻结常量都是绿的。retro `BET-Y2Q4-T10-203.md:33` 把这个 0
当真值抄了一遍。

这正是 AGENTS.md §7「扫源码的门禁必须自证」那条的形状：*空绿不等于通过*。
因此本轮的交付物除了 14 处调用时刻化，必须包含一条**能红的**门禁（I4）。

**度量方法（本轮基线，2026-10-05）**：不靠变量名枚举，而是对 `bin/**/*.py` 做 AST 不动点扫描 ——
收集所有**模块级赋值**，标记其值直接调用根 resolver 者为冻结，再把**传递依赖**（值里引用了已冻结名的赋值）
一并纳入，迭代到不动点。读数 **34 处**：其中 **14 处**依赖 profile 根（`event_ledger_path()` / `state_root()`）、
**17 处**依赖 code 根（`code_root()` / `canonical_root()`）、其余 3 处经传递归入 code 面。
**判别式是「是否依赖 profile 根」，不是「读还是写」** —— code 面按 ADR-0456 本就该跟随当前检出，
冻结它不构成缺陷；profile 面随 profile 移动，冻结在 import 时刻即错，无论读写。

## 缺陷形状与后果

模块级常量在 import 时求值。`repo_root` 的解析序是
`OMO_EVENT_LEDGER_DB → state_root()/runtime/omo/event-ledger.sqlite3`，
`state_root()` 又读 `OMOSTATION_STATE_ROOT`。所以任何在 **import 之后**才声明 profile 的
调用方（常驻 daemon、被库式复用的 `measure_*()`、用 env seam 的测试）读到的都是声明**之前**
的根。具体后果：

1. dev profile 下这 8 个入口照旧打开**生产台账** —— B1 声称消除的正是这个。
2. 5 处（`#1:361`、`#1:401`、`#2:290`、`#3:144`、`#4:218`）进一步成为**函数默认参数**，
   Python 在 `def` 执行时求值 ⇒ 冻结发生在两次之上，调用方即使运行时改了 env 也无效。
3. **没有任何测试会红**：现有的 profile 用例
   （`tests/test_evidence_smoke_paths.py`、`tests/unit/test_repo_root_profile.py`）
   一律 `monkeypatch.setenv(...)` **之后**才 `exec_module`，即"先声明后 import"，
   恰好绕开了冻结窗口。实测 `db_path=` / `--db-path` / `--ledger` 在全部现有用例里都被
   显式传值 ⇒ 默认值从来没被 profile 测试覆盖过。

## 不变式（本轮要钉住的）

- **I1 时机**：14 个 profile 根常量不再于模块级求值；写面路径在**调用时刻**经 `repo_root` 解析。
- **I2 显式优先**：调用方显式传 `db_path` / `--db-path` / `--ledger` 时，解析器**不被调用**
  （计数断言），逐字节等于传进来的值。
- **I3 未声明等价**：`env -u OMOSTATION_STATE_ROOT -u OMOSTATION_PROFILE -u OMOSTATION_ROOT
  -u OMO_EVENT_LEDGER_DB` 时，每个入口解析到的路径字符串与改前**逐字节一致**（今天的运行态无效应）。
- **I4 门禁能红（三条断言齐备，缺一即为本轮要修的错）**：
  ① **自证** —— 注入合成违规样本（直接形状 `X = state_root()/"a"` 与传递形状 `Y = X/"b"` 各一），
  断言检测器点名文件+行+变量名；② **反查过宽** —— 断言 17 处 code 面**不被**命中，
  否则「靠豁免清单蒙绿」的过宽 detector 也能通过 ①；③ **断言实测集合为空**，且本轮基线读数为 14。
  判据匹配 **resolver 调用**而非变量名 —— 改名不再是逃逸路径；且 resolver 名单**不得手写**，
  须由 `bin/lib/repo_root.py` 的公开 API 派生（防「把 resolver 改名 ⇒ 门禁静默变绿」这条新逃逸面）。
  扫描域 `bin/**/*.py`，排除 `bin/lib/repo_root.py` 自身。
- **I5 正向落点**：在模块**已 import 之后**才声明 `OMO_EVENT_LEDGER_DB=<tmp db>`，
  不传参数调用入口，实测打开的是 `<tmp db>`（这是冻结常量按构造做不到的事，也是 I3
  的反面证明）。至少覆盖 `#1 measure_value_truth`、`#9 _output_dir`、`#10/#11 task-inventory`、
  `#12 generate-brief`、`#13 omo-state-write-guard STATE_ROOT`。
- **I6 code 面不动**：17 处 `code_root()` / `canonical_root()` 派生绑定（含 `evidence-smoke` 的
  `WORKSPACE` / `GOV_LOG` / `EVENTS_LOG`、`task-inventory` 的 `REGISTRY`、`generate-docs-index` 的
  `ROOT` 一族）保持检出侧 —— 有在案的检出侧读者，只翻写者会让读者读旧数据
  （现有用例已把这条钉成「一个移 + 一个不移」的成对断言，保留）。
- **I7 判据可红**：`AGENTS.md` §7「扫源码的门禁必须自证」条目下新增一条子形状：
  管道式判据的每一段匹配词都必须能在被检对象实际文本上命中一次，且 `| grep -c` 后不接
  `|| true`。该条以本轮 T10-203 的 `event-ledger` / `event_ledger_path` 失配为实证。

## 非目标（实测后登记，不是没想到）

- **不改**任何度量逻辑、SQL、报告内容 —— 只改默认值**求值的时刻**。
- **不动** `projects/omo/src/omo/resident/daemon.py:29`
  `DEFAULT_LEDGER = WORKSPACE / "runtime" / "omo" / "event-ledger.sqlite3"`
  （字面量分叉，`:274` `:504` 使用，`projects/omo/tests/unit/test_resident_daemon.py:363` 与
  `tests/integration/test_resident_roles.py:207` 断言它）。同类缺陷、不同仓，需
  root+omo 双仓交付 ⇒ 立独立 BET，不混进本轮。
- **不动** 17 处 code 面模块级绑定（`evidence-smoke.py:48/49/57/111/112`、
  `install-watch-agent.py:24/27`、`omo-state-write-guard.py:28/31`、`probe-heartbeat-monitor.py:17`、
  `task-inventory.py:35/36`、`generate-brief.py:15/23`、`generate-docs-index.py:36-40`）——
  code 面跟随当前检出是 ADR-0456 的规定，不是缺陷。
  ⚠️ 例外已计入必改面：`install-watch-agent.py:27 LOGS_DIR` 虽是 code 面，但它写 plist/log 属
  B4b 批次 2+ 的改道面，需逐批授权，本轮**不动并在此登记**。
- **不动** `bin/panorama/panorama-collect.py:87 EVENT_LEDGER`：它按
  `OMO_EVENT_LEDGER_DB → ROOT/runtime/omo/…` 自己解析，而那个 `ROOT` 由
  `PANORAMA_ROOT` / `ZHIXING_DASHBOARD_CODE_ROOT` 驱动（方案决策 5 的外部 dashboard 契约），
  换成 `repo_root` 解析会改变托管根的语义。它第一优先级已读 `OMO_EVENT_LEDGER_DB`，
  残余风险只在「只声明 `OMOSTATION_STATE_ROOT`」时指向检出侧。
- **不动** `bin/gac/kos-seed-import.py:26 DEFAULT_DB = WORKSPACE / "kos/kos-index.sqlite"`
  （非事件台账，`/kos/` 已 gitignore，`.gitignore:156`）。
- **不动** `resident-orchestrator-daemon.py:31 DEFAULT_EVENTS_JSONL` / `:32 PID_FILE`
  （协调面，另有读者清单）。
- **不改** `bin/lib/repo_root.py` 的解析序或 env 优先级。
- **不引入** `OMO_ALLOW_GIT_WRITE`，**不改** launchd/cron（B4b 批次 2+，逐批授权）。
- **不回写** T10-203 已 `done` 的 verify 判据（历史记录不改）；假绿的教训写进本轮 retro，
  并按 §7 纪律做感知固化。

## 感知固化（同一条 PR 里做，不再攒成第二个 BET）

§7 现有条目「扫源码的门禁必须自证，且允许清单要钉成集合相等」(#4606) 覆盖的是
*检测器没命中* 的假绿。本轮补的是它的第二个面：**判据的第二段过滤词与被检对象不同源**。
`grep -rEn "^(DEFAULT_(EVENT_)?LEDGER|LEDGER|DEFAULT_DB) *=" bin/ | grep -c "event-ledger"`
第一段与第二段由不同人写下、互相不认识：第一段产出的行含 `event_ledger_path`（下划线），
第二段找 `event-ledger`（连字符）⇒ 计数恒 0，`|| true` 再吃掉退出码。判据在它自己交付的那一刻
起就失效，并被 retro 当作真值抄写。纪律：**管道里每一段的匹配词都必须能在被检对象的实际文本上
命中一次**（用合成违规样本跑全管道，不是只跑第一段）；`| grep -c` 之后**不许**接 `|| true`。

## 交付形态

一个 root 仓 PR，按 change-lane 分 commit：

| 面 | 文件 |
|---|---|
| 写面代码（12 个） | `bin/bc-os/north_star_meter_v2.py` `north_star_meter_v3.py` `weekly-value-report.py`、`bin/gac/compound-attribution-report.py` `check-episode-pipeline.py` `evidence-smoke.py` `omo-state-write-guard.py` `task-inventory.py`、`bin/mof/generate-brief.py`、`bin/ssot/episode-source-aggregator.py` `resident-orchestrator-daemon.py` `system-health-check.py` |
| 新门禁 | `tests/unit/test_b1_ledger_call_time.py`（I1–I6 可执行化，42 个用例） |
| CI 接线 | `.github/workflows/governance-check.yml` 的 `governance-verify` job 新增一步显式点名该文件 |
| 适配既有断言（4 个） | `tests/test_evidence_smoke_paths.py`、`tests/test_generate_brief_workspace_output.py`、`tests/unit/gac/test_omo_state_write_guard.py`、`tests/unit/mof/test_generate_brief_no_host_paths.py` |
| 感知固化 | `AGENTS.md` §7 三条（I7 + 判别式 + setattr 缝） |
| 台账与本 spec | `docs/plans/3y-bet-ledger.yaml`、本文件 |

## 交付期实测（写这份 spec 时还不知道的四件事）

1. **把常量改成函数会打断测试侧的 `setattr` 缝** —— 既有用例用
   `monkeypatch.setattr(module, "SYSTEM_YAML", tmp)` 换路径，改名成
   `_system_yaml()` 后这些缝当场 `AttributeError`。实测需适配 **4** 个文件（不是方案里估的 1 个）。
   附带一条自己造的 bug：`omo-state-write-guard.py` 内残留一处
   `SYSTEM_YAML.read_text(...)`，在改名后成为 `NameError`，**且没有任何用例覆盖到那一行**
   （命中它需要真正走到 ghost-declaration 分支）。系统性找法：AST 比较「模块级被赋过值的大写名」
   与「函数体内 Load 的大写名」的差集，再对 `origin/main` 逐项复核排除误报。
2. **落点判据必须断「被打开的路径」本身，不能断消息文案** —— 0 字节文件是**合法的空的
   SQLite 库**，`system-health-check._check_ledger()` 对它返回 `(True, "ledger ok")`。
   因此该用例改为 monkeypatch `LedgerBroker.connect` 记录实际打开的路径并断言它等于
   import 之后才声明的那个 `<tmp db>`。第一次跑出的是 `(False, "event-ledger.sqlite3 missing")`，
   据此改窄断言就又是「为了绿而改小」。
3. **`evidence-smoke.py` 的 `run_smoke()` 不在本轮落点覆盖内** —— 它的 `OUTPUT_DIR` 走
   `_output_dir()` 已调用时刻化并被用例覆盖，但整条 smoke 流程还需 `projects/agora` 可 import；
   全新 worktree 里该子模块未初始化 ⇒ 走 partial 分支。这是环境限制，不是本轮缺口，
   故 I5 的落点断言只覆盖已可独立调用的入口。
4. **别名让「按变量名匹配」的老判据静默漏 4 处** —— 这些脚本写的是
   `from repo_root import state_root as runtime_state_root`，所以按 `state_root(` 文本匹配
   只命中一部分。本轮门禁因此按 **resolver 调用**匹配，且 resolver 名单由**行为**派生：
   对 `repo_root.__all__` 里每个零参可调用对象在 sentinel env 下试调用，保留「Path 返回值随
   profile 改变」的名字。⚠️ 但 `__all__` **不等于**脚本实际 import 的别名集合，所以名单只用来
   **判别哪些 resolver 属 profile 面**，不做名字白名单 —— 后者正是可被改名绕过的那一面。
5. **门禁可见性有两层，缺一层就又是「没人跑的绿」** —— `tests/unit/**` 既不在
   `.github/workflows/governance-check.yml` 的显式 pytest 文件白名单里，也不在
   `bin/ssot/verify-omo.sh`（只跑 `projects/omo` 与 `.omo/tests`）里 ⇒ 单靠本地跑通
   不构成 CI 证据。本轮把它显式接进 `governance-verify`（该 job 评
   `github.event.pull_request.head.sha`，即分支自己的树），并实测该文件在只装
   `pyyaml pydantic pytest` 的最小 venv 里 42 passed（复刻 CI 依赖面，防 `ModuleNotFoundError`）。
   另：该 workflow 的 `on` 含 `schedule: 0 */6 * * *` ⇒ 即使后续 PR 只改 `bin/**`
   （不在 `on.paths` 里），门禁仍每 6 小时在 main 上跑一次。

## 合并前读数（逐条对应 done_when）

| 判据 | 读数 |
|---|---|
| 判据-1 字面 grep | 本分支 `bin/` **0** 命中；`origin/main` 同时刻 **6** 命中（四个判据里唯一带反基线的：证明这条 grep 不是恒 0 的装饰） |
| 判据-1 AST 扫描 | 模块级根依赖绑定 `34 → 20`，剩余 20 处全部 code 面（`code_root()`/`canonical_root()`） |
| 判据-2 正向落点 | `test_check_ledger_run_opens_the_db_declared_after_import` 等 5 个落点用例；`git checkout origin/main -- bin`（门禁文件保持 HEAD 版）后跑本门禁文件 ⇒ **35 failed / 7 passed**；`git checkout HEAD -- bin` 还原后 **42 passed**，工作树逐字节回到 HEAD（`git status` clean）。按构造能红是在**同一环境、同一门禁文件**上测的，不是历史读数 |
| 判据-3 等价 | `LEGACY_SUFFIXES` 13 条逐字节断言全过；verify-1 三文件合计 **914 passed** |
| 判据-4 自证/反查/基线 | 合成违规点名文件+行+变量名；17 处 code 面反向不被命中；`test_detector_counts_the_14_prefix_baseline_violations` 用 `git show origin/main:` 抄出的 13 条直接 + 1 条传递赋值 = **14** 断言基线，同函数在真实树上断言 **∅** |
| 判据-5 显式优先 | 计数断言：显式传参时解析器调用次数为 0 |
| 判据-6 读面不动 | 既有「一个移 + 一个不移」成对断言继续通过 |
| verify-3 回归集 | `-k "north_star or … or generate_brief"`：**20 passed**，无新增红 |
| 零回归总判据 | 以 `git apply -R`（sha256 逐字节复核后恢复）构造同环境基线对比 `bin`+`tests` 全量：基线与 HEAD 的失败集合**相同**（24 failed / 5 errors 全部归因于未初始化的 `projects/agora` 与缺失的 `runtime/omo/`）⇒「我的 diff 造成的新增红：无」 |

