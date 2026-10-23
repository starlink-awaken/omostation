---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-23
bet_id: BET-Y2Q4-T10-266
---

# BET-Y2Q4-T10-266 收口 receipt — reality-check E6：入口脚本**内核**钉住的根

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-266`
规格：`docs/superpowers/specs/2026-10-23-resident-entrypoint-kernel-root.md`（spec_version 1.0.0，
digest `sha256:ee6992bd73c7cf17c3121c555df44b24875490165b4fe45800b1e1cf5cd2d7b6`；
合并后在 `efe80fe92` 上 `shasum -a 256` 复算，与台账 `accepted_specifications[0].content_digest` 逐字一致）
交付：**工程腿** PR #4874 squash 为 `efe80fe9259ba74eead8ce6cf71b09c734bca621`
（GitHub `mergedAt 2026-10-23T03:42:06Z`，全部检查 SUCCESS，`mergeStateStatus CLEAN`）

## 1 这一轮改了什么（一句话）

`--reality-check` 增加一条 **E6** 观测轴：对每条声明 `runtime_root` 的 launchd 服务，沿本机 plist 的
`ProgramArguments` 找到落在 `service_root(svc)` 之下的**入口脚本**，读该脚本**内容**，判定其中是否钉住了
**另一个根**的字面量；缺省 observe-only（不进 `findings`、不改 `ok`/rc），条目声明
`require_kernel_root_match: true` 才把 `state != ok` 升级成 finding。
**本轮不改任何 wrapper 内容、不改 plist、不动 launchd、不给任何新条目 `runtime_root`。**

## 2 机器上的真实读数（done_when-2 的 receipt）

合并后从 `efe80fe92` 重跑一次（`--reality-check --json`，rc=1）：

| 项 | 读数 |
|---|---|
| `e1_drift` | **0**（`e1_status ok`） |
| `e6_non_ok` | **6** |
| `e6_blocking` | **0** |
| `ok` | `False` —— 与本轮无关，见 §4 |

逐条（`declared_root` 全部 `install`，`state` 全部 `pinned_other_root`，`pinned_root` 全部 `checkout`）：

```
com.l4.resident.decision      pin_count=2
com.l4.resident.execute       pin_count=2
com.l4.resident.event-ingest  pin_count=1
com.l4.resident.signals       pin_count=2
com.l4.resident.inbox         pin_count=2
com.l4.resident.promote       pin_count=2
```

⇒ **命中非零就是本轮的交付物**：入口 argv 在安装位、执行的 Python 码面在检出，从此有一个读数。
零命中才说明检测器没接上（AGENTS.md §7③ 空绿反证）。

## 3 rc/ok 不变是由对照证明的，不是由措辞断言的

同一份注册表、同一个 LaunchAgents 目录，把 `origin/main` 的生成器与本分支的生成器各跑一次
（两侧都显式传 `--registry`，因为 `main()` 的 `local_root = Path(__file__).resolve().parents[2]`
决定 `--reality-check` 从脚本所在树取注册表 —— 不显式传就是拿两棵不同的树互比）：

| | baseline（origin/main） | new（本分支） |
|---|---|---|
| `findings` | — | **逐字节相同** |
| `ok` | `False` | `False` |
| rc | `1` | `1` |
| 字段差 | — | 仅新增 4 个 `e6_*` 键，其余零差 |

## 4 本轮没有让任何红变成绿，也没有新增红

`ok=False` 与 rc=1 是**改道前既有**的：E4 有 20 条未分区 label、E5 有 1 条缺失
（`com.l4.omo.sync`）+ 1 条残留（`com.cockpit.dashboard`）。这些不是本轮 lane 造成的，
逐条准入评审在 BET-Y2Q4-T10-259 的清单里，属 principal 决定面。
本轮的判据是 `e6_blocking=0` —— E6 一条也没有进 `findings`。

## 5 测试与反证（done_when-1/3/4/5）

`tests/unit/test_reality_check_kernel_root_pin.py` —— 18 条用例，全 hermetic
（两棵树与 LaunchAgents 都在 tmp 下，`enumerate_launchd_plists` 被注入，不读真机、不调 `plutil`、不起子进程）：

```
uv run --no-project --with pytest --with pytest-timeout --with pytest-randomly --with pyyaml \
  python -m pytest tests/unit/test_reality_check_kernel_root_pin.py \
  tests/unit/test_gen_service_runtime_root.py -q -p no:randomly
→ 27 passed（T266 18 + T265 9 未回归）
env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB HOME=<空> \
  UV_CACHE_DIR=<空> … 同四条文件 → 27 passed（hermetic 面）
```

> ⚠️ `--with pytest-timeout` 不是可选：rootdir 仍是本检出，`pyproject` 的 `addopts` 注入
> `--timeout=300 --timeout-method=signal`，最小 venv 缺这个包就当场 `unrecognized arguments`。

变异对照**按改法分别记读数**（2026-10-23 实测，与台账 `done_when` 第 5 条逐字一致；
「一次变异只红一组」不等于其余断言都承重被验过，所以每一组单独记）：

| 改法 | 实测 | 承重的断言 |
|---|---|---|
| 摘掉 pin 计数 | **5 条红** | 字面量比对是 E6 的本体 |
| 阻塞不看开关（让命中无条件进 findings） | **1 条红** | observe-only 那条用例 |
| 不追加 finding | **1 条红** | strict 升级那条用例 |
| 阻塞只认 `pinned_other_root` | **1 条红** | `undetermined` 在 strict 下的升级 |
| 摘掉 `require_kernel_root_match` 校验段 | **2 条 reject 用例红，accept 用例仍绿** | 它不承重 —— 合法条目本来就不产生 violation |

`--check --json` 在合并后的 `efe80fe92` 上复跑：`ok=True`、`drift_count=0`（rc=0）—— 本轮没碰渲染面。

## 6 已知限制 —— 修复的第二半不在本轮

安装位此刻不具备承接码面的条件，三条实测：根 clone 冻结在 B4a 的 `1b5f02cb3`、
落后 `origin/main` **438** commits、本仓无任何 cron/launchd 条目会推进它（`crontab -l` 全量扫不到
`~/.local/opt/omostation`）；`projects/omo` 在 `a9d0165` 而检出侧 `980b9cb`；`projects/omo/.venv` 不存在。

⇒ 把 wrapper 改成自解析（`BASH_SOURCE` 推根）当刻的效果，是把这 6 条常驻服务从「检出的最新码」
切到「安装位 438 个 commit 之前的码」。那是生产行为变更，且推进安装位属机器级写面，
逐批授权归 principal（AGENTS.md §7「运行根选择器」条 + BET-Y2Q4-T10-265 的授权范围都不含「追平安装位」）。
本轮交付的是**可见性**；任务 #143 继续持有修复半，`require_kernel_root_match` 留作它的准入开关。

## 7 done_when 对照

| # | done_when（台账原文摘要） | 证据 |
|---|---|---|
| 1 | `e6_kernel_pin` 面逐条 `label/declared_root/script/state`，`state ∈ ok\|pinned_other_root\|undetermined`，认不出不得算通过 | §2 六行读数（每条含 `script` = 安装位路径）+ `test_e6_unidentifiable_entrypoint_is_undetermined_never_ok` 三形参数化 |
| 2 | 真机复跑 6 条全 `pinned_other_root`，命中为 0 即检测器没接上 | §2 `e6_non_ok=6`（合并后在 `efe80fe92` 重跑） |
| 3 | 缺省 observe-only 的 `ok`/rc 与改道前一致（E1 仍 0）；`require_kernel_root_match: true` 下 `pinned_other_root` 与 `undetermined` 各进 findings 且 rc=1，两 state 各一正一反共 4 条用例 | §3 对照 + §5 表中两组变异 |
| 4 | 检测器自证：注入命中的合成 wrapper 必须点名，只含声明根的合法 wrapper 必须不命中 | `test_e6_detector_is_not_a_no_op`（同 argv 只改脚本内容 ⇒ state 翻转）+ `..._mentioning_only_declared_root_is_ok` |
| 5 | 变异对照按改法分别记读数 | §5 表五行 |

## 8 台账 `completion_evidence` 四个轴键指向的实测

| 键 | 指向本 receipt 的哪一次实测 |
|---|---|
| `live_canary` | §2 —— 合并后在 `efe80fe92` 上跑的 `--reality-check --json`：`e1_drift=0`、`e6_non_ok=6`、`e6_blocking=0` |
| `fresh_receipt` | §5 末段 —— 同棵树 `--check --json`：`ok=True`、`drift_count=0`（rc=0） |
| `cleanup` | 本轮零机器写面：没动 plist / launchd / `services.yaml` / wrapper 内容；工作树交付物只有 spec、生成器、测试、retro、receipt、台账；`runtime/affected/t266.json`（claim 用的 affected-graph receipt）在 commit 前删除且从未 staged |
| `replay` | `.omo/_knowledge/retros/BET-Y2Q4-T10-266.md` —— 四问结构，含「现有四把尺为何结构看不见本缺陷」的对照表 |
