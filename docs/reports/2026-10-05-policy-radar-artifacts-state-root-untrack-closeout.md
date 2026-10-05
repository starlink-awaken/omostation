# BET-Y2Q4-T10-230 policy-radar 晨报产物改调用时解析 + 出跟踪 — Closeout 报告

- bet: BET-Y2Q4-T10-230
- date: 2026-10-05
- status: done
- workflow: project-code-change
- run: 20261005T111225Z-project-code-change-487d63ce
- owner: governance-agent

## 交付物

| 交付 | 位置 | 状态 |
|------|------|------|
| 代码 + 摘库 | PR **#4646** → squash 合并 `094906507` | ✅ origin/main |
| Spec | `docs/superpowers/specs/2026-10-05-policy-radar-artifacts-state-root-untrack.md`（digest `ae3d0586…`） | ✅ accepted |
| 台账条目 | `docs/plans/3y-bet-ledger.yaml` `id: BET-Y2Q4-T10-230` | ✅ 末条，len(bets) 525 == declared 525 |
| 用例 | `tests/unit/test_policy_radar_state_root.py`（10 条） | ✅ |
| retro | `.omo/_knowledge/retros/BET-Y2Q4-T10-230.md` | ✅ |
| canary 回执 | `docs/reports/2026-10-05-bet-230-canary.json` | ✅ overall=pass |

改动面 6 个文件（`bin/lib/repo_root.py`、`bin/bc-os/policy_radar.py`、`bin/gac/convergence-pulse.py`、
`.gitignore`、`.omo/state/policy-radar/*` 三件 `git rm --cached`、`docs/plans/3y-bet-ledger.yaml`）
+ 1 spec + 1 新用例。

## 验收判据逐条实测（在合并后的 `094906507` 上复测）

| done_when | 实测 | 结论 |
|---|---|---|
| 判据-1 出跟踪 | `git ls-files .omo/state/policy-radar` 空；`git check-ignore -q .omo/state/policy-radar/cache.json` rc=0（`.gitignore:289`） | ✅ |
| 判据-2 调用时解析 + 正向落点 | 声明 `OMOSTATION_STATE_ROOT=/tmp/t10230-canary` 真实跑 `--generate-morning-brief`：state 根得 `brief-20261005.json` 980B + `brief-20261005.md` 417B + `cache.json` 590B，检出的 `.omo/state/policy-radar/` **跑前跑后都不存在**（`exists_before=false`/`exists_after=false`），该路径 `git status --short` 为空 | ✅ |
| 判据-3 未声明 profile 逐字节历史行为 | 不声明 env 时 `state_dir()` == `code_root()/.omo/state/policy-radar`，且 `policy_radar.py:26` 的显式覆盖位为 `None`；`test_state_dir_matches_historical_layout_without_profile` 绿 | ✅ |
| 判据-4 读者同缝 | `convergence-pulse._brief_dir()` 声明后 → `/tmp/t10230-canary/...`，当日 `brief-20261005.json` `is_file=true`；未声明 → 检出路径 `is_dir=false`（不凭空造目录） | ✅ |
| 判据-5 不登记 projection | 未动 `.omo/_truth/registry/runtime-projections.yaml`；边界由 `test_artifacts_are_untracked_and_the_face_is_ignored` 钉 | ✅ |
| 判据-6 无回归 | `893 passed`（含 `test_projection_reader_resolution` + `test_repo_root_profile`）+ 消费方 `19 passed` + `make gac-local-gate` PASS（69 checks，1 SOFT WARN）+ ruff clean | ✅ |

## 偏差（不粉饰）

1. **PR 描述里写「9 用例」，实际收集 10 条** —— `test_no_import_time_write_plane_constant` 是
   `@pytest.mark.parametrize` 的 writer/reader 两条。数字来自实现前的心算，未以 `pytest --collect-only` 复核。
2. **`bin/plan/chain_bind.py` 不在本面** —— 开工前的清单把它列为 resident 面写者，实测它只处理
   `retros/<bet_id>.md`（`RETRO_REL = ".omo/_knowledge/retros"` + `:127`），与 `retros/resident/` 无关。
   下一个 BET 的范围据此收窄。
3. **登记闭环换成测试钉** —— 直觉做法是把新面写进 `runtime-projections.yaml`；读
   `bin/gac/omo-state-projection-guard.py` 后否决：它要求每条登记的 canonical 路径**存在且可解析**，
   而这一面是日期后缀目录，登记会在 fresh clone/CI 上结构性变红。出跟踪边界改由用例钉（spec I4）。
4. **落点判据拿不到 CI 证据** —— 没有任何 CI workflow 引用 policy-radar/convergence-pulse，
   所以「产物只落 state 根」只能本地实测（spec §4 已写明「CI 绿不构成它的证据」）。
   这是一条**结构性**缺口而非本轮疏漏：B5 每摘一个面都需要同步一个可在 CI 复现的落点断言，否则判据随人肉漂移。

## 残余与遗留（不在本 BET 边界）

- 两个 submodule 侧读者仍硬编码检出路径：`projects/omo/src/omo/pipeline_supervisor.py:129,185`、
  `projects/cockpit/src/cockpit/commands/brief.py:73`。跨仓 gitlink，另开 BET；本机 profile 未声明时行为不变，
  所以不构成当前故障，但**声明 profile 后这两处会读到陈旧副本**（与 AGENTS.md「已提交的 legacy 兜底不是仓库性质」同族）。
- `bin/bc-os/north_star_meter_v2.py:412` 与 `bin/harness:29-30` 等 resident 面读写者属下一个 BET。
- plist/cron 改道与 ledger 权威翻转（B4b 批次 2+）需逐批授权，本 PR 零触碰 —— 这也正是「本轮运行时效应为零」的前提。
- `convergence-pulse.py` 其余 `ROOT /` 常量（governance-history / decisions / swarm-escape /
  `STATE_DIR = ROOT/".omo/state"`）是读面或本已被忽略的面，留在边界外。

## 对 ADR-0456 的推进

这是 B5「生成态摘库」里第一次**写者与读者同轮收口**：前几轮出现过只改写者、读者留在检出路径的形状，
后果不是崩而是**静默假告警**（本例若无 `_brief_dir()`，convergence-pulse 会在真实晨报已生成时判「断更」）。
判据形状因此补一条：每摘一个生成面，必须同时给出该面的**读者清单**，并让每条读者走同一接缝或用例钉住其行为。

`state_dir_write()` / `state_dir_read()` 是 `repo_root` 里第一对**目录面**解析器（此前只有单文件面的
`projection_read()` / `state_file_read()`）。它们与既有解析器共享同一条 profile 探测纪律：
未声明 `OMOSTATION_STATE_ROOT` 时直接返回检出侧，历史布局逐字节不变。
