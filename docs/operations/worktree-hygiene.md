# Worktree 卫生（多 agent 栈落地后）

## 何时清理

| 状态 | 动作 |
|------|------|
| PR 已 squash 合入 main，worktree **干净** | `git worktree remove --force <path>` + `git branch -D work/<session>` |
| PR 合入但 worktree **dirty** 仅为 runtime/cron/submodule mtime | 可 force remove（先 `git status` 确认无真改） |
| 仍有 **unique patch**（`git cherry origin/main` 含 `+`） | **保留**，先评估是否另开 PR |
| 进行中 session | 保留 |

## 推荐命令

```bash
# 列表
git worktree list
git branch -vv | grep 'work/'

# 补丁级是否已落地（squash 后 tip 不是 ancestor，用 cherry）
git cherry origin/main work/<session>   # 全为 - 表示已等价合入

# 释放
git worktree remove --force ../ws-<session>
git branch -D work/<session>
git fetch origin --prune
```

辅助脚本（只 dry-run 默认）：

```bash
bash bin/gac/gac-worktree-prune.sh          # 打印可删候选
bash bin/gac/gac-worktree-prune.sh --apply  # 真删 unique=0 且 dirty=0
```

## claim 注意

- 从 **已更新** 的仓库根跑 `bin/gac/gac-worktree.sh claim`（含 ADR-0204 默认 init）。  
  若本地 main 落后 origin，脚本本身可能是旧版 → 先 `git fetch` / 更新主仓指针或直接用 `origin/main` 上的脚本。
- 默认 init：`ecos scripts omo cockpit agora`。
