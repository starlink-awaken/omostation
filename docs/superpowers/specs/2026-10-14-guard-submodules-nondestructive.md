---
schema_version: specification/v1
spec_version: 1.0.0
title: guard-submodules 非破坏性对齐 —— 并发 submodule update 周期不得删除既有检出
bet_id: BET-Y2Q4-T10-252
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-14
---

# guard-submodules 非破坏性对齐（并发 submodule update 检出保护）

> 契约正文只写不变量。数字为撰写时点（2026-10-14T04:0Z）在本机两轮 gitlink
> 交付（ptr-bump / ptr-bump2）中的实测，用于说明前提，不构成判据。

## 0. 本契约的边界（先说清"不做什么"）

- 只改 `bin/gac/gac-worktree.sh` 的 `guard_submodules()`（post-checkout 守卫的
  `--fix` 路径）与对应单测。不动 `submodule-reachability-gate`、
  `check-submodule-rewind`、`submodule-pointer-transaction` 的语义。
- 不动 claim/release 主流程：claimed worktree 的对齐语义保持现状（本地有对象时按
  pin 对齐）。
- 不动 `.omo/_truth/registry/**`、不动 `.omo/_delivery` 的 symlink 语义、不动
  任何真实写目标。
- 不放宽任何既有门禁：守卫仍然是 advisory（恒 exit 0），只是不再有破坏性副作用。

## 1. 不变量（INV）

- **INV-1 不删除**：`guard-submodules --fix` 对任何已存在 `.git` 条目的子模块路径，
  不得删除、清空或替换该 `.git` 条目及其所属目录。
- **INV-2 非破坏性对齐**：已存在且可解析（`git -C <sub> rev-parse --git-dir` 成功）
  的检出，若与 pin 不一致且本地对象库含 pin 提交，用 `git -C <sub> checkout <pin>`
  对齐；不含则跳过并在 advisory 文案中点名。
- **INV-3 空缺才重建**：仅当路径不存在 `.git` 条目时，才允许执行原有的
  `git submodule update --init --no-fetch -- <path>`（保持 T10-161 新建 worktree 的
  对齐能力）。
- **INV-4 remote 污染检查不变**：origin URL 污染检测（T10-161 ②）逐字保留。

## 2. 前提（实测，非判据）

- 2026-10-14 实证：ptr-bump / ptr-bump2 两轮交付中，worktree 内手动布置的子模块
  检出（`.git` 指向 `.git/worktrees/<wt>/modules/**` 或外部克隆）被 post-checkout
  守卫的 `submodule update --init --no-fetch` 当作无效目录反复清空；网络受限时
  重克隆必失败，留下空目录。并发 agent 的 claim/release 周期使该清空成为周期行为，
  打断交付（submodule-guard「未初始化」簿记检查无法稳定通过、remote-hygiene 报
  origin 指向本地路径）。
- 根因：`submodule update --init` 对"已存在但 gitdir 布局非标准"的检出先删后建；
  守卫无法区分"从未初始化"与"外部管理的有效检出"。

## 3. 验收条款（done_when）

- **ISC-1 不删除**：worktree 内手动布置的有效检出（`.git` 指向外部 gitdir、HEAD
  为任意 sha）在 `guard-submodules --fix` 后完好无损（`.git` 条目存在、HEAD 未变、
  工作树文件未变）。反证：删掉"已存在 .git 即跳过破坏性路径"分支 → 用例当场红。
- **ISC-2 非破坏性对齐**：已存在检出且本地含 pin 对象 → `--fix` 后 HEAD == pin，
  `.git` 条目仍在。反证：把 `cat-file -e` 存在性检查删掉 → 缺对象场景用例红。
- **ISC-3 空缺仍重建**：路径无 `.git` 条目且本地有 pin 对象 → `--fix` 后检出到
  pin（T10-161 原语义）。
- **ISC-4 缺对象跳过**：已存在检出但本地无 pin 对象 → 不动检出、advisory 点名、
  守卫 exit 0。
- **ISC-5 回归**：既有 gac-worktree / submodule 相关测试全绿
  （`uv run pytest tests/ -q -k "submodule or guard or worktree"`）。
- **ISC-6 remote 污染检测不变**：构造 origin URL 落入子仓 URL 集合的 fixture →
  仍报 🚨 且不改写。
