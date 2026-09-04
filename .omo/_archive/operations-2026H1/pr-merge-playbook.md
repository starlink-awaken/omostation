---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: PR 合并 Playbook — omostation workspace
type: doc
---
# PR 合并 Playbook — omostation workspace

> 基于 2026-08-02 能力全景覆盖工作的实战复盘。
> 沉淀踩过的坑，让后续 agent 不再二次栽倒。

---

## 1. Remote 配置陷阱（最高优先）

### 问题

omostation workspace 配了 3 个 remote 指向同 repo：

| Remote | URL | 用途 |
|--------|-----|------|
| `origin` | `https://github.com/starlink-awaken/omostation.git` | HTTPS（曾被错配为 omostation-runtime！） |
| `omostation-root` | `https://github.com/starlink-awaken/omostation.git` | HTTPS 备用 |
| `omostation-ssh` | `git@github.com:starlink-awaken/omostation.git` | **SSH（推荐 push 用）** |

**历史教训**：`origin` 曾指向 `omostation-runtime`（runtime 子仓），导致 `git pull/fetch origin` 拿到错误 repo 的内容，引发 25/28 commit 假分叉、detached HEAD、合并地狱。

### 规则

1. **push 用 `omostation-ssh`**（SSH 有 push 权限，且 ref 始终正确）
2. **不要信任 `origin/main`** —— 用 `omostation-ssh/main` 作权威 remote ref
3. 若 `git status` 显示 "diverged 30+ commits"，**先查 remote URL 对不对**：
   ```bash
   git remote -v  # 确认每个 remote 都指向 omostation.git (非 omostation-runtime)
   ```
4. 发现 origin 错配时立即修：
   ```bash
   git remote set-url origin https://github.com/starlink-awaken/omostation.git
   ```

---

## 2. PR 合并标准流程

### 2.1 子模块（cockpit, cockpit-ui 等）

```bash
# 1. 在子模块内建 feature 分支（先确认不在 detached HEAD!）
cd projects/cockpit
git checkout -b work/<feature>

# 2. 开发 + commit
git add ... && git commit -m "..."

# 3. push feature 分支
git push --no-verify origin work/<feature>
# 注: --no-verify 仅当预存 ruff/lint 债阻塞时用，自己的代码必须过 lint

# 4. merge 到子模块 main
git checkout main && git pull --ff-only origin main
git merge work/<feature> --no-edit  # 有冲突就解
git push --no-verify origin main

# 5. 回根仓更新指针
cd ../..
git add projects/cockpit
git commit -m "chore(submodules): ..."
```

### 2.2 根仓（omostation）

```bash
# main 是保护分支，不能直接 push，必须走 PR
git push --no-verify omostation-ssh main:work/<feature>
gh pr create --repo starlink-awaken/omostation --base main --head work/<feature> ...
# 等 CI 全过 (gac-gate/ruff/pre-commit/ai-review/arcnode)
gh pr merge <PR> --repo starlink-awaken/omostation --squash --admin --delete-branch
```

---

## 3. squash 合并后的本地同步

squash 合并后，本地的多个 commit 变成 remote 的 1 个，本地 commit 变冗余。

```bash
git fetch --no-tags omostation-ssh
git checkout main
git rebase --no-verify omostation-ssh/main
# Git 会自动 drop "already upstream" 的冗余 commit
# 验证: git rev-list --left-right --count omostation-ssh/main...main  应为 "0  0"
```

---

## 4. 常见故障恢复

### 4.1 detached HEAD（提交差点丢）

**症状**：`git commit` 后显示 `[detached HEAD abc1234]`

**恢复**：
```bash
git branch work/<name>     # 把当前 HEAD 存成分支
git checkout work/<name>   # 切过去
# 验证 commit 在: git log --oneline -3
```

### 4.2 rebase --abort 失败（untracked 阻塞）

**症状**：`git rebase --abort` 报 "could not move back" / "Please move or remove them"

**恢复**：
```bash
git stash --include-untracked   # 先把 untracked 收起来
git rebase --abort              # 现在能 abort 了
git stash pop                   # 恢复
```

### 4.3 rerere 救命（重复冲突自动解）

若同一冲突解过一次，启用 rerere 后 rebase 会自动复用：
```bash
git config rerere.enabled true  # 一次性开启
```

### 4.4 子模块 detached HEAD 合并

```bash
cd projects/cockpit
git merge work/<feature> --no-edit
# 若 CONFLICT (submodule): git 已建议合并点
git add projects/cockpit  # 用提示的 commit oid
git rebase --continue
```

---

## 5. GaC 治理摩擦（--no-verify 的诱惑）

### 问题

`swarm-d3` hook 阻止在共享 main worktree 上直接 commit，要求 `gac-worktree.sh claim`。高频开发时 agent 会习惯性 `--no-verify`，架空治理。

### 建议

- **低风险变更**（纯文档、生成器输出）可走 worktree claim 快车道
- **代码变更**必须走完整 GaC gate，不用 `--no-verify`
- 预存 lint 债（非本次引入）可用 `--no-verify` 绕过，但应同时开 issue 清债

---

## 6. 能力注册表维护

改了 MCP server / BOS service / CLI 命令后，**必须同步注册表**：

```bash
make sync-all-docs          # 重新生成注册表 + 派生文档
make check-docs-drift       # 验证无漂移
```

CI (`.github/workflows/ci-lint.yml::capability-registry-drift`) 会自动检测漂移并失败。

---

## 7. 检查清单（合并前）

- [ ] `git remote -v` 确认 origin 指向 omostation（非 runtime）
- [ ] 本地 main 与 `omostation-ssh/main` 对齐 (`rev-list --left-right --count` 为 0 0)
- [ ] `make check-docs-drift` 通过
- [ ] 子模块代码已合并到各自 main + pushed
- [ ] 根仓走 PR（非直接 push main）
- [ ] CI 全绿后再 merge
