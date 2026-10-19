---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-19
type: closeout-receipt
bet_id: BET-Y2Q4-T10-257
title: BET-Y2Q4-T10-257 收口 receipt — chain_bind 的 runs 读面改经 delivery_anchor 缝解析
---

# BET-Y2Q4-T10-257 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-257`（合并 SHA 记在
`completion_evidence.axes.engineering.merged_reachable_commit`）
规格：`docs/superpowers/specs/2026-10-19-chain-bind-runs-anchor-seam.md` **spec_version 1.1.0**，
`content_digest sha256:18ef9a0eeae25919198bbe1302efa2f65f9a6c47b377c1ca7cb43eb15ebfe5c8`
交付：PR **#4817**，分支 `agent/governance-agent/t10-257-chainbind-seam`，
commit `caa00807d`（第一版：import 型缝）+ `1822f2c89`（第二版：按路径加载，spec 同步到 v1.1.0）
Run：`20261019T073024Z-bet-execution-6b3946ef`（workflow `bet-execution`，7 条路径全 claim）
性质：ADR-0456 读面缝的一条缺陷修复。**不宣布 B1/B3/B4/B5 或整个 plan 完成。**

## 1 缺陷与判据

`bin/plan/chain_bind.py` 用 `workspace / RUNS_REL` 直读 runs 面，而那个目录**只在检出自已跑过
workflow 状态类操作时**才存在（`ensure_delivery_anchor()` 建 symlink，唯一生产调用点
`omo/workflow/core.py:457 _runner_path()`）。无桥检出读到 0 个 run ⇒
`bet-ledger.py complete` 对一个真实存在且已绑定 `bet_id` 的 run 假报 `missing_bet_binding`。

立项读数（2026-10-19）：本机带 `MARKER` 的 **9 个检出里 3 个无桥**
（`ws-lifeos-magpie-foundation`、`ws-resident-phase11-multimodal`、`ws-task-c64652`）。

## 2 实测读数（三台装置）

| 装置 | 命令形状 | 读数 |
|---|---|---|
| 生产调用（bare `python3`，`omo` **不在** `sys.path`） | `python3 bin/plan/bet-ledger.py complete <BET>` 同解释器 | 3 个无桥检出 **改前 0 个 run → 改后 331 个**，全部解析到 `/Users/xiamingxing/Workspace/.omo/_delivery/agent-workflows/runs`；`import omo.workflow.delivery_anchor` 当场 `ModuleNotFoundError` |
| CI 装置（`cd projects/omo` + 项目 venv，`omo` 可 import） | `uv run --with pytest-timeout pytest ../../tests/unit/test_chain_bind_runs_anchor_seam.py -q` | **8 passed** |
| hermetic 装置（`HOME=<空>` + `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB`，依赖由最小 venv 供给） | `uv run --no-project --with pytest --with pytest-timeout --with pyyaml python -m pytest` 四文件 | 新文件 **8 passed**；四文件合跑 **36 passed**；`ruff check` All checks passed（rc 0） |

**变异对照（防装置凑绿）**：把 `bin/plan/chain_bind.py` 换成 `git show HEAD:` 的改前版本 ⇒
`1 failed / 7 passed`，红的恰是 ISC-7 正向用例；换回后文件 sha256 前缀 `d1c56ee2e7c6`、
按路径加载分支在场。

**第二面（v1.1.0 的由来）**：第一版缝写成 `from omo.workflow.delivery_anchor import …`，
六条用例全绿，但出问题的调用里 `omo` 不可 import ⇒ 异常被降级分支吃掉、读数仍是 0，
**改动接了但没接上**。修复=按文件路径加载缝本体那一份 `delivery_anchor.py`（候选：跑代码的检出 →
被查询的检出），不在 `chain_bind` 复制定位语义；C2 退回条件相应从「不可 import」收窄为
「那份文件也不可达」。

## 3 done_when 逐条对账

- **ISC-1** ✅ `test_no_bridge_worktree_reads_canonical_runs`（真 `git worktree add` fixture，无桥 ⇒ 读出 run、`evaluate_complete().ok is True`）。
- **ISC-2** ✅ `test_seam_removed_gives_the_pre_change_reading`（同 fixture 摘缝 ⇒ `[]` + `missing_bet_binding`）。
- **ISC-3** ✅ C2 不回归：`test_worktree_of_an_unrelated_declared_root_is_not_followed`、
  `test_clean_checkout_without_anchor_reads_its_own_plane` + hermetic 36 passed；CI 干净检出全绿。
- **ISC-4** ✅ `test_scan_counts_direct_reads_before_and_after`：同一次 AST 扫描产出「改前 1 处 / 改后 0 处」，
  并在合成违规行命中 `[1]`（检测器自证）。
- **ISC-5** ✅ 该文件点名进 `.github/workflows/governance-check.yml` `interface-check` 白名单（`:189`），
  CI 干净检出下全绿。
- **ISC-6** ✅ 缝本体契约 `tests/unit/test_delivery_anchor_contract.py` 全绿（`delivery_anchor.py` 零改动）；
  `make gac-local-gate` 判据按台账措辞为「硬失败集合等于基线（零新增）」，本机既有硬失败与本轮无关。
- **ISC-7** ✅ 生产解释器形状上的正/反一对（见 §2 第一行与变异对照）。

## 4 边界遵守

未改 `projects/omo/src/omo/workflow/delivery_anchor.py`、`omo/workflow/core.py`、`bin/agent-workflow.py`；
读侧不调 `ensure_delivery_anchor()`（`test_reader_never_creates_the_bridge` + AST 判据 `_writes_checkout_plane == []`）；
不新增 env、不新增根；本机 `~/Library/LaunchAgents`、launchd、crontab 一行未动；
spec §5 登记的其余 13 处 runs 面读者本轮**未改**（`fix-orphan-locks.py` 风险最高，另立 BET）。

## 5 后续（不在本轮）

1. 其余 runs 面读者逐条判「该读共享面还是本检出」（spec §5 名单）。
2. `omo/workflow/core.py:43` 的 `WORKSPACE` import 期常量 + `bin/agent-workflow.py:282` 的再绑定
   （spec §1 第二面，跨 omo 子模块与 `bin/` 两条 lane）。
3. 桥的惰性建立本身：`_runner_path()` 是唯一建桥点，读取侧本轮刻意不写检出（C4），
   因此「新检出从未跑过 workflow 就看不到 run」这一形状仍在，需另一条写面 BET 处理。
