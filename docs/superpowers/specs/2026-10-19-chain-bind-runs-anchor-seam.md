---
schema_version: specification/v1
spec_version: 1.0.0
title: chain_bind 读 runs 面必须经 delivery_anchor 缝解析（否则隔离检出内 complete 假报 missing_bet_binding）
bet_id: BET-Y2Q4-T10-257
status: accepted
lifecycle: contract
last-reviewed: 2026-10-19
owner: governance-team
---

# chain_bind 读 runs 面必须经 delivery_anchor 缝解析

## 1 问题（2026-10-19 实测）

收口腿在隔离 worktree `ws-t10-253-evidence` 里跑 `bin/plan/bet-ledger.py complete BET-Y2Q4-T10-253`，返回：

```
[complete] ❌ vision→retro 链未闭合: missing_bet_binding
```

而 run `20261019T015151Z-bet-execution-8fb82293` **确实存在、确实 `bet_id` 绑定、确实 status active**，
其 5 条 scope lock 也都还在。判据假红。

根因：`bin/plan/chain_bind.py:37` 定义 `RUNS_REL = ".omo/_delivery/agent-workflows/runs"`，`:189` 直接
`runs_dir = workspace / RUNS_REL`。runs 面是**全机共享面**（AGENTS.md §7「治理协调面是全机共享面」），
每个检出的 `.omo/_delivery/agent-workflows/` 由 `ensure_delivery_anchor()`
（`projects/omo/src/omo/workflow/delivery_anchor.py:117`）做成指向 canonical 检出的 symlink。
而**桥是惰性建的**：唯一生产调用点是 `omo/workflow/core.py:457` 的 `_runner_path()`，
只有在**该检出内**跑过 workflow 状态类操作才会建桥。本次的 run 是在主工作区 `start`/`claim` 的，
收口 worktree 从未跑过，因此没有桥 → `workspace / RUNS_REL` 指向不存在的目录 →
`chain_bind` 看见 0 个 run → 报 `missing_bet_binding`。

2026-10-19 实测覆盖面：本机 10 个检出里 5 个已建桥、4 个 `.omo/_delivery/` 存在但无 `agent-workflows`、
1 个是 canonical 真目录。即**「在隔离检出里做台账收口」这条路径结构性不可靠**，且没有任何测试会红。

同日实测的第二面（**不在本轮范围**，见 §5）：`bin/agent-workflow.py:278` 先按 `__file__`
算出 `WORKSPACE = Path(__file__).resolve().parents[1]`，紧接着 `:282` `from omo.workflow import (WORKSPACE, …)`
把它**重新绑定**成 `omo/workflow/core.py:43` 那个同样由 `__file__` 反推的模块级常量。
于是在「检出侧有 retro、但该检出的 `projects/omo` 尚未初始化」的 worktree 里跑
`closeout --status ok`，链判据读的是**库代码所在检出**（本机 = canonical），当场报 `missing_retro`；
实测把该检出的 `projects/omo` 按 gitlink 补齐后同一命令的链判据即通过（`evaluate_closeout` 读数 `ok=True reasons=[]`）。
同一次实测还给出一个否定读数：`OMOSTATION_ROOT=<worktree>` 对 `omo.workflow.WORKSPACE` **零影响**
（探针两次读数均为 canonical）—— 这条常量不读 profile env。

## 2 契约（in-scope）

- **C1** `chain_bind` 不得用 `workspace / RUNS_REL` 直读 runs 面；必须先探检出侧路径，
  缺失时经 `locate_anchor()` + `is_worktree_of()` 缝解析到 canonical 的 runs 面。
- **C2** 缝**不可定位**时（fresh clone、CI 干净检出、非本仓 worktree 的外部 clone、
  以及库代码不可 import 的最小依赖面）逐字节退回当前行为：读 `workspace / RUNS_REL`，
  目录不存在即返回空 ⇒ `missing_bet_binding`。CI 与 fresh clone 的行为不得改变。
- **C3** 不新增 env、不新增根、不改缝本体：只用既有 `OMOSTATION_STATE_ROOT` / `OMOSTATION_ROOT`
  + marker 上溯三条定位链（`locate_anchor()` 原样），不改 `delivery_anchor.py` 的定位语义。
- **C4** 读取侧**不得写检出**：本轮只解析路径，不调用 `ensure_delivery_anchor()`
  （它会建 symlink、可能触发 `_merge_migrate`，那是写面动作，属 `core.py:457` 既有的责任）。
- **C5** 本轮只改 `chain_bind` 的 runs 读面（`iter_run_records()` 及其下游
  `bound_runs_for_bet()` / `evaluate_complete()` / `retro-due`）。
- **C6** 判据须同时给正向（无桥检出读到 canonical 的 run）与反向（同一次扫描里
  「改前 N 处直读 / 改后 0 处」，且缝摘掉 ⇒ 用例红）。

## 3 非目标

- 不改 `delivery_anchor.py`、`omo/workflow/core.py`、`bin/agent-workflow.py` 的任何行为
  （缝本体契约已被 `tests/unit/test_delivery_anchor_contract.py` 钉住）。
- 不动本机 `~/Library/LaunchAgents`、launchd 状态、crontab。
- 不改 §5 列出的其余 runs 面读者（另立 BET，逐条判「该读共享面还是本检出」）。
- 不宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成。

## 4 验收

- **ISC-1** 正向落点判据：新建用例在**真 git worktree fixture**（`git worktree add`，非手搓目录）里，
  该检出无 `.omo/_delivery/agent-workflows`，canonical 侧有带 `bet_id` 的 run ⇒
  `chain_bind.iter_run_records(worktree)` 读出该 run，且 `evaluate_complete()` 不再报 `missing_bet_binding`。
- **ISC-2** 反面对照：同 fixture 下把缝摘掉（locator 不可用）⇒ 读数与改动前逐字节相同（0 个 run、
  `missing_bet_binding`），证明 ISC-1 依赖的是缝而不是 fixture。
- **ISC-3** C2 不回归：`env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT HOME=<空>` 的最小依赖面
  （`uv run --no-project --with pytest --with pyyaml`）下，`chain_bind` 全部既有用例读数与改前一致。
- **ISC-4** 文本判据由同一次扫描产出「改前 ≥1 处 `workspace / RUNS_REL` 直读、改后 0 处」，
  且该判据须在**未修复树**上跑出非零（自证，防检测器空转）。
- **ISC-5** `make gac-local-gate` 绿；`tests/unit/test_delivery_anchor_contract.py` 全绿（缝本体未破坏）。

## 5 盘点的其余 runs 面读者（本轮不改，如实登记）

`bin/gac/check-work-landed.py:32`、`bin/gac/ecosystem-doctor.py:49`、
`bin/gac/requirement-iteration-gate.py:41`、`bin/gac/gate-evidence-receipt.py:108`、
`bin/gac/fix-orphan-locks.py:33-34,80`、`bin/gac/check-governance-ratio.py:51,124`、
`bin/gac/gac-local-gate.py:677,883`、`bin/gac/swarm-activity-dashboard.py:35-37`、
`bin/ssot/auto-pruner.py:89,92`、`bin/ssot/drift-face-detector.py:191,216`、
`bin/panorama/panorama-collect.py:3000,3825`、`bin/panorama/panel-collect.py:48`、
`projects/omo/src/omo/workflow/claims_authority.py:704,799,948`。

其中 `fix-orphan-locks.py` 风险最高：它按 runs 面是否可见决定要不要**归档别人的锁**，
在无桥检出里会把「看不见 run」的锁当孤儿。

另一条独立缺陷（§1 第二面，需单独 BET，且落在 omo 子模块与 bin/ 两个 lane）：
`projects/omo/src/omo/workflow/core.py:43` 的 `WORKSPACE = Path(__file__).resolve().parents[5]`
是 import 期由 `__file__` 反推的模块级常量，既不受 `OMOSTATION_ROOT` / `OMOSTATION_STATE_ROOT`
影响，也被 `bin/agent-workflow.py:282` 的再绑定覆盖掉检出侧自己的解析 ——
即「治理内核的根」与「你在哪个检出里跑」脱钩（AGENTS.md §7「写路径要在调用时刻解析」
与「被检对象的根不得由 `__file__` 反推」两条的第三个实例）。
