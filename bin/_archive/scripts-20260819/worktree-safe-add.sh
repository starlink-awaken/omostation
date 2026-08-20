#!/usr/bin/env bash
set -euo pipefail
# 机制: worktree add 强制基于 origin/main (防止 #1257/#1261 重演)
# 用法: worktree-safe-add <branch-name> [path]

branch="${1:?用法: worktree-safe-add <branch-name> [path]}"
path="${2:-../$branch}"

# 确保 origin/main 新鲜
echo "[worktree-safe-add] fetch origin main..."
git fetch origin main --quiet 2>/dev/null || true

# 检查当前 HEAD 是否是 origin/main 的后代
if ! git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
  echo "[worktree-safe-add] ⚠️ 当前 HEAD 不是 origin/main 的后代"
  echo "[worktree-safe-add] ⚠️ 强制基于 origin/main 创建 worktree (避免并行 agent 的并行分支混入)"
fi

# 基于 origin/main 创建 worktree
git worktree add -b "$branch" "$path" origin/main 2>/dev/null || git worktree add "$path" "$branch" 2>/dev/null || {
  echo "[worktree-safe-add] ❌ worktree 创建失败"
  exit 1
}

echo "[worktree-safe-add] ✅ worktree 创建完成: $path @ $branch (基于 origin/main)"
exit 0
