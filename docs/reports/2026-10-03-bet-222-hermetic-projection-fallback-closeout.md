---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-04
type: report
bet_id: BET-Y2Q4-T10-222
title: BET-Y2Q4-T10-222 closeout — 两条"只有这台机器/只有这几天才绿"的投影用例改为两面可指认
---

# BET-Y2Q4-T10-222 closeout — ADR-0456 B5 残留：投影用例去 host/时钟依赖

契约：`docs/superpowers/specs/2026-10-03-bet-222-hermetic-projection-fallback.md`
台账：`docs/plans/3y-bet-ledger.yaml` 条目 `BET-Y2Q4-T10-222`
交付：PR #4617 → squash 合并 `e43d6bc9d`（父 `0a63b4969`，基线 `cbbfbcc44`）
run：`20261003T140422Z-project-code-change-8219cbeb`（四条 path 全 claim，`--affected-hash` 用
`.artifacts/affected-graph-t10-222.json`，`receipt_hash=79c09ea5…`）

## 1. 交付内容

| 文件 | 改动 |
|---|---|
| `tests/unit/test_repo_root_profile.py` | 新增 `_fake_checkout()` + `_probe(state_root, checkout=…)`；重写兜底用例（物化 legacy 侧 + 正向落点断言）；新增 `test_projection_without_legacy_reports_missing_canonical` |
| `tests/unit/test_projection_reader_resolution.py` | 新增 `_fresh_ts()`；三处 fixture 写点的绝对 `generated_at` 改为相对 now |
| `docs/plans/3y-bet-ledger.yaml` | 插入 `BET-Y2Q4-T10-222`（516 → 517 bets，`total_bets` 同步） |
| `docs/superpowers/specs/2026-10-03-bet-222-hermetic-projection-fallback.md` | 本 BET 契约（含 §4 逐文件分类表、§5 范围外红的分类） |

## 2. Engineering evidence — verify 1–7 实测读数

基线 `cbbfbcc44`，隔离 worktree `/Users/xiamingxing/ws-t10-222-hermetic-fallback`，2026-10-03/04 UTC。

| # | 命令 | 读数 |
|---|---|---|
| 1 | `python3 -m pytest tests/unit/test_repo_root_profile.py -q` | `861 passed in 3.95s`（修复前 `1 failed, 859 passed`） |
| 2 | 单跑 `…::test_projection_falls_back_to_committed_legacy_path` | `1 passed in 0.44s` |
| 3 | 变异对照：把 `    legacy.write_text(` 换成 `    pass` 后单跑该用例，再 `git checkout --` | `MUTATION_EXIT 1`、`restored=0` |
| 4 | `python3 -m pytest tests/unit/test_projection_reader_resolution.py -q` | `18 passed in 0.26s`（邻居读数不变） |
| 5 | `grep -rn "write_text.*generated_at:[ ]20" tests/unit --include="*.py"` | `CLEAN` |
| 6 | `git diff --name-only origin/main...HEAD \| grep -E '^(projects/\|\.gitignore$\|\.github/\|\.omo/_truth/)'` | empty |
| 7 | `uv run --with pyyaml python3 bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked` | `PASS (4544 files, 146 warnings)` |

补充：两文件合跑 `879 passed`；`ruff check` = `All checks passed!`；新增/修改用例内 `/Users/` 与
`xiamingxing` 字面量 0 处（期望路径全部由 `tmp_path` 派生）。

CI（PR #4617）：`bet-done-transition pass`、`gac-gate pass 2m3s`、`governance-verify pass 1m45s`、
`interface-check pass 3m0s`、`evidence-gate pass`、`meta-doctor pass` 等 16 项 pass、0 fail、0 pending，
`mergeStateStatus=CLEAN`。合并后按 blob 逐字节核对四个交付文件，`4cab4cca6` 与 `origin/main` 一致
（squash 语义下用内容等价而非 ancestry 判据）。

## 3. Operational evidence

**live canary（运行现场核对，不是"应该能跑"）**：兜底用例现在跑在一个 `tmp_path` 下的假检出上，
那个假检出自带 `projects/omo/src/omo/{__init__.py,omo_paths.py}` 与
`.omo/_truth/registry/runtime-projections.yaml`，源字节用 `shutil.copyfile` 从本仓真文件复制。
判据是"单跑该用例（`-q` 只带一个 node id）也绿"（读数 2）—— 若实现仍依赖 host，单跑必红，
因为它没有别的用例替它先创建目录。

**fresh receipt**：本文件即 receipt；判据 3 的变异对照在提交**之后**重跑一次（`git checkout --` 的
还原目标是 `4cab4cca6` 的 blob，不是改动前的旧内容），所以"负向对照会红"这件事是在交付物本身上量的。

**replay**：`.omo/_knowledge/retros/BET-Y2Q4-T10-222.md`（四问结构，含两条判据自身红过的过程）。

**cleanup**：worktree `ws-t10-222-hermetic-fallback` 与分支 `agent/governance-agent/t10-222-hermetic-fallback`
由 `gac-worktree.sh merge` 释放；`.artifacts/`（affected-graph receipt 与 PR 正文草稿）在 `.gitignore:11`
内，不进仓；变异对照的 mutated 源文件已还原（`restored=0`）。合并收尾遗留一项非本轮造成的：
本地 `Workspace/main` 载有并发 agent 的 2 个提交（`86ed7dbed`、`a98185244`）且落后 2，脚本按规则
不 reset —— 修复入口 `bash bin/gac/sync-main.sh`，需人工确认无在制改动。

## 4. 范围外：全量枚举余下的红（不迁就、不顺手改）

`python3 -m pytest tests/unit -q --tb=no -p no:randomly` = **16 failed, 1848 passed in 839.25s**。
本 BET 处置 2 条，可指认的 14 个用例名分属三类不同机制，各立任务：

| 机制 | 用例 | 任务 |
|---|---|---|
| 装置性：本 claim `SKIP_SUBMODULE_INIT=1`，`git submodule status` 显示 `projects/agora` 未 init | `test_live_server_value_readiness.py` 3 + `test_panorama_pending_authorizations.py` 5（`No module named 'collectors'`）+ `test_phase8_unified_ecosystem.py::test_env_resolver_workspace_paths` 1（sys.path 缺 `projects/agora/src`） | 判据换地方测（canonical 或 `claim --full`），AGENTS.md §6 已固化该坑，无需改代码 |
| 基线红：`.omo/cron/registry.yaml` 里 panorama 两个 job `status: proposed`（`origin/main` 逐字节同状态），用例断言 `active`；改动源自 `bcf7572ef`（#4592 更正 launchd 授权语义） | `test_panorama_runtime_scheduler.py` 2 | 任务 #108 —— 要的是 launchd 现实核对，把断言改成 `proposed` 等于放弃那条契约 |
| 顺序依赖：单跑该文件 `6 passed`，全量跑红 | `test_reporting_reads_ledger.py` 2 | 任务 #109 —— 独立定位污染源（候选：`OMOSTATION_STATE_ROOT` / `OMO_EVENT_LEDGER_DB` / `sys.path` / `chdir`） |

`16` 与 `14` 的差额是后台输出文件只留了尾部（截断），不是漏计。另：这三类只有在 `tests/unit` 进 CI
白名单后才会被持续看见，而加不加白名单属另一轮决策（T10-221 判据 3 已记录 CI 现在看不见 `tests/unit`）。

## 5. Value

治理/测试面收益，不以价值指标计量（`value_indicator_policy: false`）：BET 的直接收益是
`tests/unit` 里"绝对时间戳 × 相对窗口"这一类不可复现红从 3 处降到 0 处，以及"测兜底先物化"
从口头约定变成同仓两份可复制形状。是否转化为持续收益，取决于任务 #107（把时钟炸弹这一类补进
AGENTS.md §7 的 hermetic 条目）与 #108/#109 的落地，本轮不声称。

## 6. Rollback

单提交回滚：`git revert e43d6bc9d`（squash 后主仓只有一个 commit）。逐文件等价核对命令：

```
git rev-parse 4cab4cca6:tests/unit/test_repo_root_profile.py
git rev-parse origin/main:tests/unit/test_repo_root_profile.py   # 两者应相同
```

回滚后果：兜底用例回到"只在跑过写者的检出里绿"，心跳用例回到 2026-10-02 起必红；台账条目
`BET-Y2Q4-T10-222` 与 spec 一并撤下（spec 的 `content_digest` 只被该条目引用，无其他消费者）。
