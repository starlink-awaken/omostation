---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-27
bet_id: BET-Y2Q4-T10-272
---

# BET-Y2Q4-T10-272 收口 receipt —— E7 让「码走了、写没走」变成一个可读的数

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-272`
规格：`docs/superpowers/specs/2026-10-26-bet-272-e7-write-root-reality-axis.md`
工程腿：PR #4911 → squash `ef5000b5619092473a6336daaaf908b180bcefa0`（4 文件 +598/−11：`bin/mof/gen-service-configs.py` +125、`tests/unit/test_reality_check_state_root_axis.py` +290、spec +103、台账 +91），合并时刻 `2026-10-27T02:39:51Z`
收口腿：分支 `agent/governance-agent/t272-closeout`（base `2ba4b614d`），run `20261027T045847Z-project-code-change-c11a1927`

## 0 归属先说清：本轮不认领工程腿，也不认领别人的清红

| # | 事 | 由谁交付 | 证据 |
|---|----|----------|------|
| 1 | E7 写根轴本体（分类、observe-only、schema 准入、17 条用例） | 工程腿 PR #4911 | squash `ef5000b56`，运行 `git show --stat ef5000b56` |
| 2 | 台账开条矩阵的 5 条 lint ERROR（`PENDING` × 3 + `overall_state: in_progress` + policy 违规） | **并发 lane 的 T10-269 收口腿** PR #4917 | `dc67a0f5f`；`git log -S'status: PENDING' --oneline c2255b477..dc67a0f5f -- docs/plans/3y-bet-ledger.yaml` 只命中这一条 |
| 3 | 本 receipt + retro + 台账 `completion_evidence` / `status: done` | 本轮 | 本 PR |

第 2 行值得留在 receipt 里：`BET-Y2Q4-T10-273` 的收口 receipt §7 当时把这 5 条写成「留给它自己的收口腿」，那句在它自己的 base（`c2255b477`）上是准确的，但今天已被 #4917 关掉。两份文字都不改写 —— 改已合并的 receipt 要重算台账里 6 个摘要位，属另一次交付；据实记录在此即可。

## 1 E7 补的是哪一格

B4b 每批切换的判据是「指向 Workspace 的 plist 由 43 → 0」，而六桶里没有任何一桶读 `EnvironmentVariables`：E1 比 plist 文本与注册表渲染（argv），E6 比入口脚本内容钉的根，两者都是**码面轴**。2026-10-26 本机实测 81 份 plist：执行根=检出 30、执行根=安装位 8，而后者 8 条的 `EnvironmentVariables` 全部仍把写根钉回检出 —— 码在安装位、写在检出。E7 从 `enumerate_launchd_plists` 已有的 `row["blob"]` 解出 env，把声明 `runtime_root` 的 launchd 条目的写根分类为 `profile|checkout|install|undeclared|undetermined`；缺省只观测，条目声明 `require_state_root_partitioned: true` 才升级成 finding。

## 2 交付面（本 PR）

| 文件 | 面 | 性质 |
|------|----|------|
| `docs/reports/2026-10-27-bet-272-e7-write-root-reality-axis-closeout.md` | +本文 | 新增 |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-272.md` | retro | 新增 |
| `docs/plans/3y-bet-ledger.yaml` | `BET-Y2Q4-T10-272` 块：`status: done` / `done_at` / `completion_evidence` / `overall_state` | 仅非投影字段 |

零代码面、零机器面：不动 `bin/**`、不动 `~/Library/LaunchAgents/**`、不 bootout/bootstrap、不动 crontab、不给任何真实条目置 `require_state_root_partitioned`。

## 3 验证读数（每行**自己标注**产出它的 base）

| 判据 | 检测器 base | 读数 |
|------|-------------|------|
| `pytest tests/unit/test_reality_check_state_root_axis.py`（hermetic：`HOME=<空目录>` + `env -u OMOSTATION_ROOT/OMOSTATION_STATE_ROOT/OMO_EVENT_LEDGER_DB`，依赖由 uv 供给） | `2ba4b614d` | `17 passed` |
| 同一批用例在真实 host HOME 下复跑（依赖仍由 uv 供给） | `2ba4b614d` | `17 passed` |
| `--reality-check --json` 的 E7 面 | `2ba4b614d` | `checkout 6 / profile 0 / undetermined 0 / non_ok 6 / blocking 0 / e7_finding False / sum_states 6 = rows 6 / ok False` |
| 同上，先测的一遍 | `dc67a0f5f` | 逐字相同（见下方可比性依据） |
| `--reality-check` 退出码 | `2ba4b614d` | `rc=1`（由 E4/E5/E1 决定，findings 里无 `E7` 前缀） |
| `--check --json` 退出码与 drift | `dc67a0f5f` | `rc=1 / drift_count=1`，唯一 drift 是 `com.omostation.agent-brief-materialize` |
| E4 未分区 label 数 | `dc67a0f5f` | `19` 条（与 spec 基线一致） |
| `bin/plan/bet-ledger.py lint` | `2ba4b614d` | `OK — 570 bets, 16 tracks, no errors` |

**两次 reality-check 读数可比**的依据：`git diff --name-only dc67a0f5f 2ba4b614d` = 3 行，全是文档与台账；`--reality-check` 读的注册表来自 `services_yaml_path()` = `canonical_root()`，该文件在两 base 逐字节相同，`bin/mof/gen-service-configs.py` 也未变。

## 4 done_when 六项对账

| # | 条款 | 结论 | 证据 |
|---|------|------|------|
| 1 | 逐条给 `label/declared_runtime_root/declared_state_root/state`；未安装不得折叠成 `undeclared` | ✅ | 用例 `test_e7_uninstalled_service_is_undetermined_not_ok`、`test_e7_env_absent_is_undeclared_and_still_unpartitioned_for_install`、`test_e7_empty_env_value_is_not_folded_into_absent`、`test_e7_installed_state_root_is_its_own_state` |
| 2 | 真实机器复跑 `checkout 6 / profile 0`，两侧都 0 不接受 | ✅ | §3 第 3 行：`rows 6`、`sum_states 6`，命中非零 ⇒ 检测器接上了 |
| 3 | 缺省 observe-only：`ok`/`rc` 与改道前一致；置 `true` 使 `checkout` 进 findings 且 `rc=1`，正反各一条 | ⚠️ 见 §5 第 1、3 项 | 正反用例 `test_e7_default_observe_only_does_not_move_ok_or_findings` + `test_e7_require_state_root_partitioned_promotes_the_same_hit`（+ `test_e7_promotion_does_not_disturb_e1_to_e6`）；括注「E1 仍 0」当前不成立 |
| 4 | 检测器自证（V1 正向落点）：合成 argv 指安装位/env 钉检出必须点名并分类 `checkout`；env 指 profile 的合法样本必须分类 `profile` 且不命中 | ✅ | `test_e7_detector_is_not_a_no_op`、`test_e7_names_a_service_whose_code_moved_but_writes_did_not`、`test_e7_profile_state_root_counts_as_partitioned` |
| 5 | 全分类穷尽：`e7_states` 之和恒等于行数；人读行直接打印分类 | ✅ | `test_e7_state_breakdown_covers_every_row`；实测 `sum 6 = rows 6` |
| 6 | schema 准入：未声明 `runtime_root` 时报违规、写 `false` 时报违规、写 `true` 且已声明时接受 | ✅ | `test_require_state_root_partitioned_needs_runtime_root` / `..._rejects_false` / `..._accepts_true_with_runtime_root` |

## 5 如实登记（共 6 项：1 项判据括注不成立 + 1 项跨 base 不可证 + 3 项装置面事实 + 1 项归属更正）

1. **done_when-3 的括注「E1 仍 0」在本机当前读数为 1**，不是本轮引入。根因：并发 lane `f4ab53dd0`（PR #4905）把 `com.omostation.agent-brief-materialize` 登进 `services.yaml` 而未在本机装对应 plist；`--check` 把「文件缺席」当 `existing=""` 与渲染结果比 ⇒ 永久 drift。与 E7 无关（findings 里无 `E7` 前缀，`e7_blocking 0`）。处置：不修、不绕、不 `--no-verify`，交由 principal 裁定「装机」或「`generate: false` 退出比较」。
2. **宿主 `python3 -m pytest` 报 `No module named pytest`**（`/opt/homebrew/.../python3.15`）。这是 AGENTS.md §7「装置面补记」说的「装置没搭对，不是回归」：`HOME=<空>` 会同时摘掉 user-site 的 pytest，依赖面必须由最小 venv 供给。改用 uv 后两面同值 17 passed。
3. **「ok/rc 与改道前一致」不能靠跨 base 读数相等来证**：`c2255b477 → 2ba4b614d` 之间 E1 已由 0 变 1，等式两端不同 base 不可比（§7「门禁的尺本身会随 base 变」的数据面版本 —— 这里动的不是尺而是隔壁桶）。承重证据因此是测试面那两条（observe-only 不移动 `ok`/`findings`、promotion 不扰动 E1–E6），不是「两次读数一样」。
4. **本轮两次 rc 读数取自管道尾**：`... | tail -3` 之后的 `$?` 是 `tail` 的退出码。据此一度把 `affected-graph.py --output` 命中已存在文件记成「rc=0 只报文字」；无管道复测真值 **`rc=2`**。这是 §7 zsh 条的同族自伤（`${PIPESTATUS[0]}` 在 zsh 恒空），落笔前必须按无管道形式复算一次。
5. **claim 的项目名两份名单不同源**：`agent-workflow claim` 要求 receipt 含 `workspace-root`，而 `docs/layer-contract.yaml` 的层内项目名单（`L0..X` 共 21 项）里没有这个名字；`--changed-projects governance` 被生成器拒（`unknown project(s)`），`workspace-root` 却被接受。本轮两次 claim 失败后才对齐。事实登记，不改判据、不加豁免。
6. **上一条表格里的「5 条 lint ERROR 属 T10-272」已被 #4917 关闭**（表格第 2 行给命令）。本轮不重跑那次红，也不认领这次清红。

## 6 回滚

本 PR 只加两份文档 + 改 `BET-Y2Q4-T10-272` 块的非投影字段：`git revert --no-edit <本 PR merge-sha>` 即回到 `status: in_progress` + `overall_state: evaluating`，零运行态效应。E7 代码本体的回滚是另一件事：`git revert --no-edit ef5000b56`（会同时摘掉 17 条用例与 spec）。

## 7 遗留与边界

- E7 读到的 6 条 `checkout` 命中（注册表声明面）是 **B4b 批次 2+ 的工作项**，不是门禁债：消它需要 plist `EnvironmentVariables` 改道 + host 面 8 条与注册表 6 条的差额回填。本轮不动。
- 给任何真实条目置 `require_state_root_partitioned: true` 是 principal 的改道裁定；在那之前这道闸是 observe-only 的。
- `agent-brief-materialize` 的 E1 永久 drift、E4 剩余 19 条与 E5 两项的署名裁定、B4b 批次 2+ 逐批授权 —— 各自在册，不由本轮推定。
- **本轮不判定 E7 该不该升级为阻塞，也不宣布 ADR-0456 B1 / B4b / B5 或整个 plan 完成。**
