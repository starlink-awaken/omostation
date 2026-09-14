---
name: git-safety-check
description: "git 安全检查 skill：高危 git 操作（reset/push/子模块指针）前置校验与守门"
title: Git Safety Check
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - git reset --hard
  - git push --force
  - branch deletion
  - submodule operations
---

# git-safety-check — Git 高危操作守门

> 将 AGENTS.md §6 Git 高危操作守门规则转为可执行 skill

## 高危操作检查清单

### reset --hard 前三确认

1. 当前分支是否正确？
2. reset 目标是否 = 该分支的 origin 状态？
3. 工作树是否干净？

### 仓库边界确认

修改"看起来是子项目"的代码前:
```bash
ls -d <path>/.git          # 确认是否在子模块内
git -C <path> remote -v    # 确认 remote 归属
```

### 子模块 commit 三步走

1. `cd projects/<sub> && git add && git commit`
2. `git push` (子模块内)
3. `cd 主仓 && git add projects/<sub> && git commit && push`

### 禁止操作

- `sed -i` 做添加/删除条目 → 用 Python read→check→modify→write
- 直接 commit 到 main → 走 worktree + PR
- `git pull --rebase` 前未检查 → 可能丢弃本地改动

## 逃生口

唯一逃生口: `SWARM_ESCAPE_ID=<id>`

## 相关

- AGENTS.md §3 — Git & Submodule Discipline
- `.agents/skills/git-discipline/` — 并行 git 纪律
- `.githooks/pre-commit` — 自动化守门
