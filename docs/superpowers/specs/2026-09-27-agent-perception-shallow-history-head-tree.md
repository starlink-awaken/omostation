---
schema_version: specification/v1
spec_version: 1.0.0
title: 固化两条仓库自身历史/CI 认知到 AGENTS.md（浅历史与 head-tree 评审）
bet_id: BET-Y2Q4-T10-210
status: accepted
lifecycle: contract
last-reviewed: 2026-09-27
---

# 固化两条仓库自身历史/CI 认知到 AGENTS.md

## 1. 问题

`AGENTS.md` §6 是 agent 在交付动作前必读的一段。实测其中一条陈述是错的，另一条已知行为
从未写下，两者都会让 agent 在**证据判断**上得出反向结论：

1. **`AGENTS.md` 原文（修改前位于 `:195`）断言「CI 评的是 merge tree，不含 base 漂移」。** 这只对一半。
   `.github/workflows/governance-check.yml` 有四个 job：

   | job | 行 | checkout ref |
   |---|---|---|
   | `meta-doctor` | `:48/:51` | 默认（PR 事件 = merge commit） |
   | `interface-check` | `:61/:64` | 默认（同上） |
   | `doc-freshness` | `:142/:146` | 默认（同上） |
   | `governance-verify` | `:165/:169` | **`ref: ${{ github.event.pull_request.head.sha }}`（`:176`）+ `fetch-depth: 0`（`:177`）** |

   也就是说，恰好是跑台账 `done`-transition 守卫与 evidence/ledger 校验的那个 job，评的是
   **分支自己的 head tree**。这不是疏漏 —— `:171-175` 的注释写明是刻意为之：GitHub 的合成
   merge ref 会把冲突的 gitlink 解析到 base 一侧，从而让治理检查看到的子模块图与 PR 实际
   交付的不是同一个。但它对 agent 的日常推论有直接代价：**base 漂移会改变这个 job 的判定**，
   而 `:195` 原文那句「CI 评的是 merge tree，不含 base 漂移」恰好把 agent 引向"分支旧没关系"
   的反向结论。

2. **本机主仓恒为浅历史，claim 出的 worktree 子模块深浅不定，且从未写下。** 2026-09-27 实测：

   | 测量 | 值 |
   |---|---|
   | 主仓 `git rev-parse --is-shallow-repository` | `true` |
   | `.git/shallow` 边界 | 1 个 shallow tip：`6ba6bf28e`（2026-08-01 06:30:54 +0800） |
   | 主仓本地可达 commit | 8,326 |
   | canonical `projects/omo` | 非浅，767 commit |
   | 历史 claim worktree `projects/omo` | **浅，各 1 commit**（`HEAD~1` 直接 `unknown revision`）—— 实测 `ws-t10-208-state-snapshot` / `ws-e1-gate-metrics` / `ws-doc-governance-20260926` |
   | 本次 claim worktree `projects/omo` | 非浅，766 commit —— **同一条命令，结果不同** |
   | claim 的默认 init | `git submodule update --init --depth 1`（`bin/gac/gac-worktree.sh:484`、`:504`） |
   | 逃逸口 | `claim --full` 或 `GAC_FULL_SUBMODULE_INIT=1`（`:373`、`:484`）；`SKIP_SUBMODULE_INIT=1` 只做 root worktree（`:473`） |

   后果是**具体的**：gitlink 可达性判据（`git -C projects/omo merge-base --is-ancestor <child>
   origin/main`，本仓交付契约要求的 AC-10 类检查）在只有一个 commit 的检出里必然给不出可信答案 ——
   那里不存在"祖先"关系。跑出 false 不是回归，是测量装置本身没有历史。而 CI 侧
   `governance-verify` 用 `fetch-depth: 0` + `submodules: recursive`（`:177-178`）取**完整历史**，
   所以同一条判据会「本地 false / CI 绿」——这正是最容易让人误判成 CI 假绿的一类分歧。
   本次 worktree 恰好是深检出，说明深浅取决于 claim 路径，**不能靠记忆假设，必须当场测**。

## 2. 交付

两条都只改 `AGENTS.md` §6，不改任何工具、workflow 或 CI 配置：

1. 把 `:195` 那句改成**按 job 区分**的陈述：默认 checkout 的三个 job 评 merge commit，
   `governance-verify` 显式评 `pull_request.head.sha`，因此台账/evidence 类门禁会受 base
   漂移影响；并给出指针（文件 + 行号），不复述 workflow 内容。
2. 新增一条 pitfall：**本机是浅历史**（主仓边界 + claim worktree 子模块 `--depth 1`），
   并给出判据 —— gitlink 可达性验证只能在 canonical 或 `--full` 的检出里做；在浅检出里
   跑出的 false 不得当成回归证据。

## 3. 完成判据

- `AGENTS.md` 中「CI 评的是 merge tree，不含 base 漂移」这句不再存在；替代文字点名
  `governance-verify` 与 `pull_request.head.sha`。
- `AGENTS.md` 含一条写明浅历史的条目，点名 `.git/shallow`、`--depth 1` 与
  `GAC_FULL_SUBMODULE_INIT` / `claim --full`。
- 每条数字都能被当场复算（`git rev-parse --is-shallow-repository`、
  `wc -l < .git/shallow`、`git rev-list --count`、`git -C <wt>/projects/omo rev-list --count`、
  `rg -n "depth 1" bin/gac/gac-worktree.sh`）。
- 除 `AGENTS.md` 与本 spec/台账/retro/receipt 外零文件改动；`make gac-local-gate` 绿。

## 4. 明确不做

- **不 unshallow**：`git fetch --unshallow` 会重写主仓对象库，是机器级写操作，不在本 BET 范围。
- **不改 claim 的默认浅 init**：`--depth 1` 是为绕开 120s claim 超时（`:479` 注释）而刻意选的，
  本 BET 只补认知，不动默认值。
- **不给 governance-check 加 job 或改 ref**：改 CI 评审对象是治理面变更，需另立 BET。
- **不在 AGENTS.md 写死当前 commit 数当长期事实**：数字带测量日期与复算命令，避免下次漂移。
