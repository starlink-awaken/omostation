---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-11
type: closeout-receipt
bet_id: BET-Y2Q4-T10-239
title: BET-Y2Q4-T10-239 closeout receipt — omo src/ 仓根字面量折进 code_root()/state_root() 单一缝
---

# BET-Y2Q4-T10-239 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-239`
契约：`docs/superpowers/specs/2026-10-10-omo-src-code-root-convergence.md`（spec_version 1.0.0，digest `sha256:034de8cb…`）
机器可读读数：`docs/reports/2026-10-11-bet-239-closeout-canary.json`
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-239.md`
交付：omo PR #210 + 根仓 PR #4718 → `a682300faa02dd5f0c38f2506210a1eafb150974`（squash，2026-10-11T06:03:00Z）

## 1 交付

| 面 | 位置 |
|---|---|
| omo 侧新缝入口（`code_root()` 与 `state_root()` 对称，`__file__` 反推、不读 `OMOSTATION_ROOT`） | `projects/omo/src/omo/omo_paths.py` |
| 32 处仓根字面量按 spec §3 逐站点定性折进缝 / 既有 helper | `projects/omo/src/omo/**`（18 文件） |
| 检测器三件（字面量扫描、两根对拍、落点正面断言） | `projects/omo/tests/unit/test_omo_src_root_literal_scan.py`、`test_omo_code_root_parity.py`、`test_omo_root_plane_landing.py` |
| 测试 env 迁移（注入本轮被迁站点的 5 处 + 1 处 setattr 缝） | `projects/omo/tests/**` |
| 根侧接线（CI 显式点名三件检测器，否则「CI 绿」不构成它们的证据） | `bin/ssot/verify-omo.sh` `[4/5]` 文件表、`.github/workflows/governance-check.yml` 新 step |
| 交付锚点跨边界契约用例 | `tests/unit/test_delivery_anchor_contract.py` |
| 台账条目 + 感知固化 | `docs/plans/3y-bet-ledger.yaml`、`AGENTS.md` §7 |

gitlink：`projects/omo` = `e8c7aa0ed002b7217ee9d0f4061a2aeea00923fd`。

## 2 判据读数

- **字面量收敛（同一次扫描产两侧）**：尺 `git grep -En 'Path\.home\(\)[[:space:]]*/[[:space:]]*"Workspace"' <ref> -- 'src/**'`，计数用 `/usr/bin/grep -c .`。改前 `d8ca1a2` = **32 站点 / 18 文件**，改后 `e8c7aa0ed` = **0**。测量在深历史检出 `projects/omo`（`shallow=false`，776 commits）做 —— 收尾 worktree 的 omo 实测 `shallow=true`，历史类判据在那里读数无意义。
- **假缝归零**：`os.environ.get("WORKSPACE_ROOT", str(Path.home()…` 形态在本 worktree 的 `projects/omo/src` 计数 **0**（`/usr/bin/grep`，2026-10-11T06:19:48Z）。
- **检测器 canary（两把 profile 面）**：`uv run --project . pytest <三件> -q` = **35 passed**（默认面，06:19:29Z）与 **35 passed**（ambient `OMOSTATION_STATE_ROOT=/tmp/t10239-ambient-state`，06:19:48Z）。本轮早前两次同装置读数也是 35（`/tmp/t10239_canary2.out`、`/tmp/t10239_canary3.out`）。
- **CI 侧「我的用例真跑了」**：`[4/5]` 在 PR #4718 的 governance-verify job 打出 **147 passed, 9 skipped**；本地同表（十件）147、去掉本轮三件的七件表 112 ⇒ 差分恰为 **35**。点阵交叉核对：CI 72+72+12 = 156 项 = 147 + 9。该步骤命令是 `bash bin/ssot/verify-omo.sh`，文件名在脚本内部不入日志，且 `-q` 不打印用例名 ⇒ 差分是唯一正面证据（记录在 canary JSON）。
- **相关命名门禁**：spec-binding lint 71、B1 call-time 44、B5 materializer 26、B5 consumer wiring 12、delivery-anchor 11，全部 passed；interface-check 352 passed / 9 skipped。
- **未声明 profile 时的等价性（ISC-4）**：`code_root()` 与历史 `WORKSPACE_ROOT` 默认值同解，43 个 plist 与 crontab 一行未改 —— 本轮只交机制，不搬运行态。

## 3 WorkPacket 两轮顺序（本轮新固化）

`scope.write_surfaces` 由台账在 `start` 时投影，并在**每次 claim 时从活台账重导并比 packet hash**（`bin/plan/bet-ledger.py:2333-2337`）。因此「声明 closeout 面」和「写那三面」不能共用一个 run：改完台账再 claim，当场就是 `WORK_PACKET_SOURCE_DRIFT`。

| 轮 | run | claim | packet hash |
|---|---|---|---|
| 1 | `20261011T061611Z-…-7c093da1` | 仅 `docs/plans/3y-bet-ledger.yaml` | `sha256:ce7a1ef8…`（30 面） |
| 2 | `20261011T061856Z-…-a746ab2f` | retro + 两份 receipt + 台账 | `sha256:65a2f77b…`（33 面） |

两轮不同 hash 且第二轮的 33 面含三件新声明，就是「台账增补进了投影」的正面证据。`completion_evidence` / `status` / `done_at` 不在投影里，所以在第一轮之后仍可写。

## 4 rollback

- 交付面是纯增量缝化：回滚 = revert PR #4718 的那一个 squash commit（`a682300fa`）并把 `projects/omo` gitlink 退回 `d8ca1a2`；`bin/**` 与 `bin/lib/repo_root.py` 解析序未碰，回滚不牵动 B1/B5 其他门。
- 未声明 profile 时对今天的运行态无效应（ISC-4），所以回滚不改变任何现役进程的路径解析。
- 收尾轮（本 receipt + retro + canary + 台账 `status: done`）可单独 revert，不影响交付面。

## 5 清理与安全

- 合并走脚本自己的 GitHub 侧调用 `gh pr merge 4718 --repo starlink-awaken/omostation --squash --delete-branch`（`gac-worktree.sh:1143`），**不**跑 `merge` 子命令：`:1098` 的脏树守卫会被并发会话持有的 kairon gitlink 挡住，`:1151` 会在共享主工作区执行 `git checkout main`（那儿脏且在别人的分支上）。全程主工作区只读，未替并发会话切分支或 stash。
- 无 `--no-verify`、无 admin merge、无空提交、无 `--force`；暂存一律显式列路径（`git add docs/plans/3y-bet-ledger.yaml` 等），生成态（`.omo/_knowledge/omo-events.jsonl`、物化的 `.omo/state/system.yaml`、`runtime/affected/**`）一律不入库。
- push 前按用户授权跑 L3 深度安全审查；提交集变化后重新征询，不在未授权时推送。

## 6 遗留（登记，不用改窄判据换绿）

| 项 | 为什么不本轮修 |
|---|---|
| `service-config-drift` 1 条偏差 | 修复要 `gen-service-configs.py --write` + LaunchAgent 重载 = 机器级需授权动作；该检查 `gac-local-gate.py:204` 标了 `ci_skip` ⇒ 不阻断 CI |
| `check-work-landed` 45s cap 未登记 | 负载下 54.0s / 60.1s 两次超 `gac-local-gate.py:251` 的 cap；登记债属 `gate-known-debt.yaml` 的独立一轮 |
| 孤儿 `refs/remotes/upstream/main` | 它让 `submodule-pointer-transaction.sh` 对所有 agent 结构性 bail；删别人的 ref 需授权 |
| spec §7 八项读面残留（含 `_MANAGER` 别名复位缺陷） | 与本缝无因果，另立 BET |
