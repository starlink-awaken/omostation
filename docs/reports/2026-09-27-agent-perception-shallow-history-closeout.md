---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-28
type: report
bet_id: BET-Y2Q4-T10-210
title: BET-Y2Q4-T10-210 固化两条证据装置认知 — closeout receipt
created: '2026-09-27'
run_id: 20260927T225148Z-project-doc-change-0cb8423d
---

# BET-Y2Q4-T10-210 closeout receipt — AGENTS.md 浅历史与 head-tree 评审认知固化

## 交付

| 项 | 值 |
|---|---|
| PR | #4488（`agent/governance-agent/agents-md-history-20260928` → `main`，squash） |
| merge commit | `fcb6eabeac3c3670930251a6d539a405459be013` |
| 交付 root commit | `813324db4` |
| accepted spec | `docs/superpowers/specs/2026-09-27-agent-perception-shallow-history-head-tree.md`（`sha256:03a4b3b15b09a6311d7fe8f09bb9abcd4e9e6131e0ad33d38aa6af99ba40c41f`） |
| retro | `.omo/_knowledge/retros/BET-Y2Q4-T10-210.md` |
| 文件面 | wave-1 = 3 文件（`AGENTS.md` / spec / ledger）；wave-2 = retro + 本 receipt + ledger done |

两条认知写进 `AGENTS.md` §6：

1. **`governance-verify` 评的是分支 head tree**，与另三个 job（`meta-doctor:51` /
   `interface-check:64` / `doc-freshness:146` 走默认 merge-commit checkout）不同 —— 依据
   `.github/workflows/governance-check.yml:176` 的 `ref: ${{ … github.event.pull_request.head.sha … }}`
   与 `:177` 的 `fetch-depth: 0`。给出复算命令 `rg -n "pull_request.head.sha" .github/workflows/`。
2. **本机仓库是浅历史、claim 出的子模块深浅不定** —— `git rev-parse --is-shallow-repository=true`、
   `.git/shallow` 边界 `6ba6bf28e`、`gac-worktree.sh` 默认 `--depth 1`、逃逸口 `claim --full` /
   `GAC_FULL_SUBMODULE_INIT=1`，并写明「gitlink 可达性判据只在 canonical 或 `--full` 检出里有意义」。

## 验证（复算记录）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `rg -n 'CI 评的是 merge tree' AGENTS.md` | 0 命中（错概括已移除） |
| 2 | `rg -n 'pull_request\.head\.sha' AGENTS.md .github/workflows/governance-check.yml` | 两文件均命中（文档与装置同一表达式） |
| 3 | `rg -n 'is-shallow-repository\|depth 1\|GAC_FULL_SUBMODULE_INIT' AGENTS.md` | 命中，条目指向真实逃逸口 |
| 4 | `git diff --name-status origin/main HEAD`（wave-1） | 恰好 `M AGENTS.md` / `M docs/plans/3y-bet-ledger.yaml` / `A <spec>`，无生成态 |
| 5 | `python3 bin/plan/bet-ledger.py lint` | `OK -- 500 bets, 16 tracks, no errors` |
| 6 | `python3 bin/plan/bet-ledger.py retro-due` | rc=0（无待补复盘） |
| 7 | `python3 bin/ssot/doc-governance-check.py --no-new-warnings` | `PASS (4474 files, 165 warnings)` |
| 8 | `python3 bin/gac/ci-check-runner.py --workflow governance-check.yml` | `✅ 12 checks PASS` |
| 9 | `gh pr checks 4488` | 19 项全绿，`mergeStateStatus: CLEAN` / `mergeable: MERGEABLE` |
| 10 | L3 深度安全审查（两次，分别对 commit set `cb46ffef5` 与 `be1080ad0`+`7f17f7950`） | `findings_count: 0` |

## 回滚

`git revert fcb6eabea`（文档 + spec + 台账条目一并退回；本 BET 不改工具、不改 CI、不改运行态，
无数据迁移）。台账的 `META_TOTAL_BETS` 由 `ledger-safe-insert.py` 绝对重算，revert 后计数随之回到 499。

## 过程中的真实代价（详见 retro §Q3）

- 一次 3-job 同根因红：spec frontmatter 缺 `owner`（`bet-closeout-chain` skill 清单漏项）。
- 一次 merge-tree 专属红：`META_TOTAL_BETS_DRIFT declared=499 actual=500`（并发 mint 共用单行计数器）。
- 一次自造更坏状态：整份覆盖台账 → `CONFLICTING` + **该 PR 零检查上报**；改用真 merge 解成同 blob 超集修复。
- 两类本地假红（旧 base 台账引用 / 落后子模块），都是本次第 2 条认知的实例。
