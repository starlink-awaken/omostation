#!/usr/bin/env bash
set -euo pipefail
# 机制: 自动清理已合并分支的 worktree + 孤儿 worktree
# 防止 worktree 堆积 (当前 17 个 worktree, 部分已合并但未清理)

echo "[worktree-cleanup] 检查已合并分支的 worktree..."

# 获取已合并到 origin/main 的分支列表
merged_branches=$(git branch --merged origin/main 2>/dev/null | grep -v "^\*\|main\|master" | sed 's/^ *//')

if [ -z "$merged_branches" ]; then
  echo "[worktree-cleanup] 无已合并分支"
  exit 0
fi

cleaned=0
for branch in $merged_branches; do
  # 查找对应的 worktree 路径
  wt_path=$(git worktree list --porcelain 2>/dev/null | grep "branch refs/heads/$branch$" | awk '{print $1}')
  if [ -n "$wt_path" ] && [ -d "$wt_path" ]; then
    echo "[worktree-cleanup] 清理: $branch ($wt_path)"
    git worktree remove --force "$wt_path" 2>/dev/null || echo "[worktree-cleanup] ⚠️ 清理失败: $wt_path"
    cleaned=$((cleaned + 1))
  fi
done

echo "[worktree-cleanup] 清理完成: $cleaned 个 worktree"

# 清理孤儿 worktree (目录不存在但 git 仍注册)
echo "[worktree-cleanup] 检查孤儿 worktree..."
git worktree prune 2>/dev/null || true
echo "[worktree-cleanup] ✅ 完成"
