---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-05
type: report
bet_id: BET-Y2Q4-T10-282
title: BET-Y2Q4-T10-282 closeout — spine 写者根缝可达 + 验收尺 PATH 判别力
---

# BET-Y2Q4-T10-282 收口收据

工程腿 = PR #5045 squash `0b67fac45451201a70847de7c2dda0f85885ddbe`；准入腿 = PR #5021 squash
`4f26d3ad2a1d3f116e6acf9d75aca6b3adf2f0ba`，其 retro 经 PR #5027 squash `c26820e3ee8f85dccde3b686891bda1e73fa89ad` 入 main。
本文件是 completion-evidence-matrix/v1 的 diff / rollback / tests / fresh_receipt / live_canary / cleanup 六项载体。

## 交付

| 件 | 内容 |
|---|---|
| `scripts/tools/spine-daily-ingress.py` | `:29` 缝改为 `parents[2] / "bin" / "lib"`；`:30-31` 加「缝不可达即 `SystemExit`」守卫；删掉 `except ImportError` 的检出根字面量兜底，`code_root` / `state_root` 一律取自 `repo_root` 模块 |
| `scripts/tools/launchd-workspace-reality-check.py` | 判据改为「服务自己的目标字符串叶子」，只剔除 `EnvironmentVariables.PATH` 一个键（`:30`/`:41`），不再对整份 plist 做子串包含 |
| `tests/unit/test_b4b_spine_seam_reachability.py` | 5 条：正向落点、源码无字面量、缝变异被守卫当场拒、摘守卫后那份红来自守卫本身、实跑写路径落 state 根 |
| `tests/unit/test_b4b_ruler_path_discriminator.py` | 4 条：PATH 假阳不计 / 真字面量仍计（同一次扫描）、安装位缺席不炸、反证（放宽成整行丢弃则真字面量用例必须红） |
| `41e492fa2`（同 PR 第二 commit） | 用例 4 的兄弟残留修复：载入前摘掉 `sys.path` 里的 `bin/lib` 与 `repo_root` 模块缓存 |

## done_when 逐条对账

| # | 判据 | 实测 |
|---|---|---|
| 1 | `code_root` / `state_root` 的 `__module__` 均为 `repo_root`，源码无检出根字面量 | `test_spine_seam_resolves_to_the_real_repo_root` + `test_spine_source_has_no_checkout_literal` 绿；本轮直接对 `origin/main:scripts/tools/spine-daily-ingress.py` 复扫 `/Users` → 零命中。**订正**：spec §1 第 1 项写「三个 resolver」，实际该脚本只有两个（新旧版本都无 `install_root` 调用），可执行判据 §2-1 的两个 resolver 已全部达成 |
| 2 | 缝改回 `parents[1] / "lib"` 时守卫当场 `SystemExit`；摘掉守卫则该用例红 | `test_seam_depth_mutation_is_caught_by_the_guard` + `test_the_guard_is_what_makes_that_red` 绿，后者断言的是「去掉守卫拿不到 ModuleNotFoundError 契约」，排除了「靠别的报错侥幸变红」 |
| 3 | 声明 `OMOSTATION_STATE_ROOT` 后实跑写路径，产物落 state 根而非 CWD / 检出根 | `test_writer_lands_in_state_root_not_checkout_or_cwd` 绿（正向落点，含检出根历史池前后字节相等的反污染断言）；另跑真实 CLI canary 见下 |
| 4 | 尺读数 2 → 1：`ai.hermes.gateway` 不计，`com.omostation.test-archive-purge-7d` 仍计 | 本轮实测 `--json`：`total_plists=87 / pointing_to_workspace_count=1 / pointing_to_install_count=40 / other_count=46`，`workspace_hits_sample=["com.omostation.test-archive-purge-7d"]`，`workspace_categories.unmanaged_other=1` |
| 5 | PATH 判别写成「整行丢弃」时真字面量用例必须红 | `test_b4b_ruler_path_discriminator.py` 的反证用例绿 |

## 验证

- `uv run --no-project --python 3.12 --with pytest --with pytest-timeout --with pyyaml python -m pytest tests/unit/test_b4b_spine_seam_reachability.py tests/unit/test_b4b_ruler_path_discriminator.py tests/unit/test_b4b_ruler_seam_reachability.py -q` → **13 passed**（base `0b67fac45`，本收口腿复跑）。兄弟尺 T10-281 的 4 条未退化。`tests/unit` 不在 CI 白名单，本地跑是唯一证据。
- 全量 `tests/unit` 批跑（工程腿）：**1270 passed / 1 failed**，唯一失败 `test_b1_ledger_call_time` 与 `origin/main` 同 blob、单跑即红 ⇒ 预存红，另案登记（不在本 BET 范围）。
- 顺序依赖复现口径：那条「摘守卫」用例的红**只在 30 个 `tests/unit/*.py`（匹配 `bin/lib|repo_root`）批量跑**时才暴露；只排 2–3 个兄弟文件跑得绿，因此工程腿初稿写在 PR body 里的「已排除顺序依赖」是不成立的断言，已在 #5045 body 里显式订正。
- CLI canary（真实写入路径，非读源码）：`OMOSTATION_STATE_ROOT=<tmp> spine-daily-ingress.py --original … --sign …` → `status=RECORDED`，产物落 `<tmp>/.omo/state/spine-diff-buffer.jsonl`（该目录原不存在）；`--status --json` 只读复跑正常。临时目录已删除，`~/Library/LaunchAgents` 与检出根 `.omo/state/spine-diff-buffer.jsonl` 未被这次运行改动。
- `python3 scripts/tools/launchd-workspace-reality-check.py --json` → 上表读数，退出码 0，未改动任何 LaunchAgent。

本收口腿复跑（base `0b67fac45`）：

- `make gac-local-gate` 连跑两次同结果 → **67 PASS / 1 FAIL，RC=2**。唯一失败
  `check-evidence-freshness :: generation_failed — import_failed`；归因链见 retro「工程腿」第 3 条的订正
  （冷 worktree 里 `projects/metaos` 只剩 `.git` 指针 → `uv sync` 拒 → 回落到无 `fastmcp` 的来路解释器），
  与本腿三件文档无因果关系 —— 同一脚本在规范检出 PASS（`score=100.0 / age=7d`）。未使用 `--no-verify`。
- 台账 `done` 转换校验：`bet-ledger.py verify BET-Y2Q4-T10-282` → D0 面 7 件 `[OK]` + 本收据当时未跟踪
  （提交后闭合），verify 三条命令按 `--execute` 另跑；`complete` 返回「已是 done, 无需操作」（幂等，未改写文件）；
  `lint` 对本条只报 `未知 track T10-GOVERNANCE` —— T10-280/281/283 同错，属既有 track 注册缺口，非本腿引入。
- 台账 YAML 用「重复键即失败」的严格 loader 复算：本腿第一版把 `diff` 写成两次，被该 loader 当场点名
  `DUPLICATE KEY 'diff' at line 46392`；删并重验后 0 重复键，`bets` 总数 581（准入腿插入时 579，其间 main 新增两条）。

## 回滚

单 commit 可逆：`git revert -n 0b67fac45451201a70847de7c2dda0f85885ddbe`（等价于把上表四件恢复到 `337a64202` 的版本）。回滚会把 spine 写落点重新钉回检出根字面量、并把尺的 workspace 计数放回 PATH 噪声口径 —— 两者都是已实测的缺陷面，回滚只应在缝守卫造成新的现场不可用时使用。

## 订正与残留（读侧须知）

1. **台账 `verify[1].expect`「其余三桶读数不变」按构造不可能成立**。三桶与总数是守恒式：`total = workspace + install + other`。准入腿读数 `85 = 2 + 40 + 43`，本轮读数 `87 = 1 + 40 + 46` —— `install` 确实不变（40），但被改道的那份 plist 落进 `other`，且期间机器上新增 2 份 plist，所以 `other` 43 → 46。判据里可复算的部分是「workspace 桶 2 → 1 且样本恰好是 `test-archive-purge-7d`」，已达成。
2. **B4b 批次 2 仍有 1 条真在范围内的 plist**（`com.omostation.test-archive-purge-7d`，4 处检出根字面量）。本 BET 只修尺的判别力与 spine 的缝，改道那条 plist 属另批，需逐批授权。
3. **spine 历史数据面未迁移**：`Workspace/.omo/state/spine-diff-buffer.jsonl` 仍在检出根，新写入按 profile 落 state 根，两侧并存；6 处读者（含 `projects/cockpit`、`projects/omlxc` 两个子模块）未同批改。这是 spec §3 non_goals 与 §4 熔断的既定边界，不是遗漏。
4. **受治理 run 的 claim 缺口**：本 BET 的 run `20261104T092627Z-project-code-change-356e143c` 处于 active，其 work_packet 只声明了两件脚本；本收口腿三件（retro / 收据 / 台账）尝试补 claim 时被 `project.lock.yaml` 拒——该 lease 由另一 actor（`claude-lead`，BET-Y2Q4-T10-285）持有且未过期（`expires_at: 2026-11-05T11:52:30Z`）。未使用逃生口抢占，也未改动他人锁，故本腿在「有 active governed run、无逐径 claim」状态下交付。
5. **测量装置的两处形状缺陷**（本轮实证，另案登记）：① `gac-worktree.sh claim` 报「分支已存在但 worktree 缺失」时退出码为 0，且拒绝后不留任何可判的失败信号；② `agent-workflow.py:283` 用 `from omo.workflow import WORKSPACE` 覆盖了 `:278` 按 `__file__` 算出的工作根，导致在 linked worktree 里跑的治理 CLI 实际读**规范检出**的台账 —— 规范 main 落后 origin/main 25 个 commit 时，本 BET 的台账条目读不到，claim 报 `BET_NOT_FOUND`。本轮靠把 worktree 内 `projects/omo` 检出补齐（index 被并发守卫清空过，用 `read-tree` + `checkout-index` 本地重建，未动 HEAD）才让 CLI 读到正确台账。
