---
schema_version: specification/v1
spec_version: 1.0.0
title: Agent Brief 物化器的写根方向钉进 B1 名单（根因由 #4913 交付）
bet_id: BET-Y2Q4-T10-273
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-27
---

# BET-Y2Q4-T10-273 — Agent Brief 物化器的写根方向钉进 B1 名单

## 1. 事实链（逐条带测量出处）

### 1.1 缺陷与预存红

`bin/panorama/materialize-agent-brief.py` 曾在 **import 期**把 profile 写根冻成两个模块常量
`OUT_DIR = state_root() / "runtime" / "dashboard"` 与 `AGENT_BRIEF_JSON = OUT_DIR / "agent-brief.json"`
（引入点 `f4ab53dd0` #4905、`8e058a808` #4907）。这是 ADR-0456 B1 契约（BET-Y2Q4-T10-232 固化）禁止的形状：
`OMOSTATION_STATE_ROOT` 在 import 之后声明时写面仍落在旧根，且**没有任何测试会红**——
唯一会红的是按 resolver 匹配、并要求「改后为 0」的那条源码扫描门禁。

检测器 `tests/unit/test_b1_ledger_call_time.py::_frozen_write_targets` 读数（每个读数标注**产出它的那份检测器所在 base**）：

| base | 命中数 | 命中 |
|---|---|---|
| `616c07338` | 2 | `panorama/materialize-agent-brief.py:58:OUT_DIR`、`:59:AGENT_BRIEF_JSON` |
| `214ad1f42` | 2 | 同上 |
| `ef5000b56` | 2 | 同上（#4911 合入后的 main tip） |
| `4858eb530` | **0** | 根因已消除（见 §1.2） |

CI 侧：`governance-verify` 步「ADR-0456 B1 call-time write-plane gate」在 main 自己的 run 40428684471
（base `616c07338`）与 40439736535（base `ef5000b56`）上都是 `2 failed, 42 passed`，两条失败为
`test_no_module_level_profile_root_constant_left_in_bin`（`:283`）与
`test_detector_counts_the_14_prefix_baseline_violations`（`:370`）。
按 ci-red-triage §1 分类为**预存红（主仓同红）**，不是任何在制 PR 引入。

### 1.2 根因由并发 lane 交付

PR #4913（合入为 `4858eb530`，仅改 `bin/panorama/materialize-agent-brief.py`）把两个模块常量删除、
`default_target()` 改为 `return state_root() / "runtime" / "dashboard" / BRIEF_FILENAME`，与本 BET 原计划的
改法在**essential respect 上等价**。因此本轮不再把自己的实现覆盖上去（那是对已定型的上游实现做拼写churn，
不增加任何门禁价值），残余工作收缩为 §2 的覆盖面缺口。

### 1.3 `bin/**` 触发面缺口：本轮记录期间已被上游关闭

**本轮起手时的实测状态**（base `4858eb530`）：`.github/workflows/governance-check.yml` 的 `on.push.paths`
与 `on.pull_request.paths` **不含 `bin/**`**（列的是 `.omo/**`、`docs/**`、若干具名脚本、`CLAUDE.md`、
`LAYER-INDEX.md`），因此 `4858eb530` 那次 push **没有产生任何** `Governance Check` run——当时 `gh run list`
的 main 最新 run 仍是 `ef5000b56` 的 40439736535（`failure`）。也就是说根因修复落地后，「预存红已消除」
当时只有**本地检测器读数**（§1.1 表末行 0），没有 CI 复评。

**随后上游补上了它**：并发 PR #4915（合入为 `1917c669b`，措辞
`fix(ci): governance-check.yml 触发面补 bin/** — 补上 #4913 缺陷潜伏的覆盖缺口`）把 `bin/**` 加进 push/PR
两侧路径，并从 `.omo/_truth/registry/ci-surfaces.yaml` 的 `workflow_triggers` 删掉被它取代的两条具名条目。
判据：`git diff 4858eb530 origin/main -- .github/workflows/governance-check.yml` 只有这三行形状的变化。

**该步在 main 上的第一次复评由 #4915 完成，本轮不据为己有**：main run `40442337806`（`headSha=1917c669b`，
`createdAt=2026-10-27T03:06:54Z`，`event=push`）结论 **`success`**。逐 step 的 API 读数本机取不到
（`gh api .../runs/40442337806/jobs` 连续 `EOF`），因此该结论由两条证据合成：① run 整体 `success`（实测）；
② 该步在 `governance-check.yml:265-268` 是无 `continue-on-error` 的普通 `run:` 步
（`python3 -m pytest tests/unit/test_b1_ledger_call_time.py -q`），失败必然把 job 与 run 一起带红。
⇒ 本 lane 的 PR run 不再是「第一次复评」，而是**带上 `default_target` 两个参数化后**的复评。

## 2. 残余缺口（本轮交付物）

#4913 删掉了冻结常量，但**没有**把 `default_target` 登记进 `STATE_ENTRIES` 与 `LEGACY_SUFFIXES`
（实测 `git show 4858eb530:tests/unit/test_b1_ledger_call_time.py | grep -c materialize-agent-brief` = **0**）。
于是这个文件的写根**方向**无人守：源码扫描只保证「没有 import 期常量」，不保证「落点在 profile 写根」。

反证（同一次变异，两个 base 各跑一次，`-q -p no:randomly`）：

| 变异 | 未登记（`4858eb530`） | 已登记（本 lane head） |
|---|---|---|
| 把 `default_target()` 改成 `Path(__file__).resolve().parents[2] / …`（即退回检出根） | `19 passed`（全绿，源码扫描也仍为 0） | `1 failed, 6 passed`，失败 id 正是 `test_state_write_target_follows_profile_declared_after_import[bin/panorama/materialize-agent-brief.py-default_target]` |

即：**没有这两行登记，把一个已改对的写面重新改回检出根是零成本、零红灯的**。这正是 T10-232 把名单建成
单一来源所要防的形状，所以修法是把 callable 名加进既有名单，而不是新建一条只扫本文件的用例
（手写平行清单是 T10-203 假绿的形状）。

## 3. 契约

1. **登记而非另建**：`default_target` 进入 `STATE_ENTRIES` 与 `LEGACY_SUFFIXES` 这两个既有名单，
   I5（晚声明 profile 生效）与 I3（未声明时逐字节等于 legacy 落点）两层因此自动覆盖本文件。
2. **不改 #4913 已交付的实现形状**：相对段是内联字面量还是模块常量，属拼写选择，两者都保持
   `runtime/dashboard/agent-brief.json` 可 grep；本轮不动它。
3. **写面语义不变**：`default_target()` 仍走 `state_root()`，不退回 `__file__` 反推，也不移到检出根。
4. **observe-only 边界**：不写 `~/Library/LaunchAgents`、不 `bootout/bootstrap/kickstart`、不改 crontab、
   不改 `services.yaml`；本轮只改这份测试名单与治理文档面。

## 4. 非目标

- 不重新实现 #4913 已交付的根因修复。
- 不判定 Agent Brief 物化器该不该活、该不该装（属署名准入面）。
- 不放宽 `test_b1_ledger_call_time.py` 的任何既有判据。
- 不宣布 ADR-0456 B1/B3/B4/B4b/B5 或整个 plan 完成。

## 5. 验证判据（本轮实测读数）

| 判据 | 期望读数 | 实测 |
|---|---|---|
| `_frozen_write_targets(CHECKOUT/"bin", _profile_resolvers())` | `set()` | `0`（base `4858eb530`，改前 2） |
| `tests/unit/test_b1_ledger_call_time.py` 全文件 | 全绿 | `46 passed`（base `4858eb530` + 本 lane） |
| 三条直接相关套件（B1 + panorama brief + materializer） | 全绿 | `76 passed` |
| 变异对照（§2 表右列） | 该参数化 id 当场红 | `1 failed, 6 passed` |
| 反基线（§2 表左列，未登记） | 全绿 ⇒ 证明缺口真实 | `19 passed` |
| `make gac-local-gate` | PASS | `PASS (68 checks executed, 2 SOFT WARN)` |
| `bin/plan/bet-ledger.py lint` 中**本 BET 条目**的 ERROR 行数 | 0 | `0`（整体余 5 条属 `BET-Y2Q4-T10-272`，见 §6） |
| main 上该 gate 的复评（§1.3） | 有 run 且不为该步红 | run `40442337806` @ `1917c669b` = `success`（由 #4915 触发，非本轮） |
| 本 PR 的 `governance-verify` 步「ADR-0456 B1 call-time write-plane gate」 | pass，且 collect 数含新增两个参数化 | 待 CI 读回（合并前不得当作已通过） |

## 6. 如实登记的分歧、模板错误与装置注意事项

- **开条模板本身是 lint 必红的形状**（本轮自伤，已检出并修正）：开条时抄了台账里 `BET-Y2Q4-T10-272` 的
  `status: PENDING` × 3 + `overall_state: in_progress`，而 `bin/plan/bet-ledger.py:437` 的
  `COMPLETION_AXIS_STATUSES` 合法枚举是 engineering ∈ {NOT_STARTED, IN_PROGRESS, VERIFIED}、
  operational ∈ {NOT_PROVEN, DEGRADED, PROVEN}、value ∈ {NOT_PROVEN, REJECTED, ACCEPTED}，
  **不含 `PENDING`**；`:1948-1971` 的派生规则里 (engineering≠VERIFIED 且 operational≠DEGRADED 且
  value≠REJECTED) ⇒ `derived = "evaluating"`，所以开条形的 `overall_state` 必须是 `evaluating` 而不是 `in_progress`。
  正确的开条矩阵 = `overall_state: evaluating` + `IN_PROGRESS / NOT_PROVEN / NOT_PROVEN` + 三面 `evidence: {}`。
  **为什么插条目工具没拦住**：`bin/gac/ledger-safe-insert.py` 只校验 axes **键集**与 `overall_state` 非空，
  **不校验 status 枚举**，因此它按构造放行 lint 必红的开条形。
  **判据**：开条后跑 lint 并**按 BET id 分组数 ERROR 行**
  （`lint | grep '^ERROR' | grep -oE 'BET-[A-Z0-9-]+' | sort | uniq -c`），
  不要 `tail -6`——本轮第一次就是这样把 5 条 error 读成「warnings only」并写进了台账。
- **`BET-Y2Q4-T10-272` 的 5 条 error 是 main 上的既成事实**：由 #4911 合入，早于本轮。
  本轮不替别的 BET 改 evidence 面；它应由 T10-272 自己的收口腿以真实 evidence 覆盖
  （届时 engineering=VERIFIED + operational=PROVEN + value=NOT_PROVEN ⇒ derived `delivery_accepted`）。
- **环境类分歧（不夹带修复）**：本地全量跑该文件另见 `test_measure_value_truth_run_uses_the_db_declared_after_import`
  一类失败（host 侧 sqlite/observer 状态泄漏）。已实测：在**不含本轮任何改动**的检出上同样复现，
  而在 CI run 里它们属 42 passed 之一 ⇒ 「本地 FAIL / CI PASS」的环境类分歧，不由放宽断言处理。
- **最小 `git archive` 对照树不能当 CI 替身**：本轮曾用 `git archive <sha> bin tests/...` 造对照树跑该文件，
  得到 `3 failed`——其中两条是台账/ledger-db 相关用例，因该树**按构造没有** `docs/plans/3y-bet-ledger.yaml`
  等输入而红，与被测改动无关。判据：反基线读数必须在**完整检出**（真实 worktree 或完整 clone）里产出，
  最小 archive 树只可用于纯源码扫描类判据。
- **`grep -E` 在本机会被别名换成 rg**：`grep -E "^OK"` 报 `unknown encoding: ^OK`（rg 的 `-E` 是编码标志）。
  脚本化判据一律用 `/usr/bin/grep -E`（AGENTS.md §7「Python 子进程拿的是另一套二进制」同源）。
