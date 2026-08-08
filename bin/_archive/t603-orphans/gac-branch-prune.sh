#!/usr/bin/env bash
# gac-branch-prune.sh — 清理已合并和过期的 work 分支
#
# 清理规则:
# 1. 远程已删除的本地分支 (git fetch --prune)
# 2. 已合并到 main 的本地 work 分支
# 3. 超过 TTL 且无 open PR 的本地 work 分支
#
# 安全: 不删除 main, 不删除有 open PR 的分支, 不删除有未保存改动的 worktree.
#
# 用法:
#   bash bin/gac/gac-branch-prune.sh              # 执行清理
#   bash bin/gac/gac-branch-prune.sh --dry-run    # 只查看不删除

set -euo pipefail

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

REMOTE="${REMOTE:-origin}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
TTL_HOURS="${PASW_TTL_HOURS:-24}"

echo "=== GaC Branch Prune $(date -u +%Y-%m-%dT%H:%M:%Z) dry=$DRY_RUN ==="

# 1. 清理远程已删除的本地分支
echo "── 1. Prune 远程已删除的分支 ──"
if [ "$DRY_RUN" = true ]; then
  echo "   [dry-run] 将运行: git fetch --prune $REMOTE"
else
  git fetch --prune "$REMOTE" 2>&1 | tail -3
  echo "   ✅ Done"
fi

# 2. 清理已合并到 main 的本地 work 分支
echo "── 2. 清理已合并的 work 分支 ──"
merged=0
while IFS= read -r branch; do
  branch=$(echo "$branch" | tr -d ' *')
  [ -z "$branch" ] && continue
  [ "$branch" = "$MAIN_BRANCH" ] && continue
  [[ "$branch" != work/* ]] && continue

  if git merge-base --is-ancestor "$branch" "$MAIN_BRANCH" 2>/dev/null; then
    echo "   已合并: $branch"
    if [ "$DRY_RUN" = false ]; then
      git branch -d "$branch" 2>/dev/null || git branch -D "$branch" 2>/dev/null || true
    fi
    merged=$((merged + 1))
  fi
done < <(git branch --format='%(refname:short)')
echo "   ✅ 已清理 $merged 个已合并分支"

# 3. 清理过期且无 open PR 的 work 分支
echo "── 3. 清理过期 work 分支 (TTL: ${TTL_HOURS}h) --"
stale=0
now=$(date +%s)
while IFS= read -r branch; do
  branch=$(echo "$branch" | tr -d ' *')
  [ -z "$branch" ] && continue
  [ "$branch" = "$MAIN_BRANCH" ] && continue
  [[ "$branch" != work/* ]] && continue

  # 检查是否有 open PR
  if command -v gh >/dev/null 2>&1; then
    has_pr=$(gh pr list --head "$branch" --state open --json number 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    if [ "$has_pr" != "0" ]; then
      continue
    fi
  fi

  # 检查最后 commit 时间
  last_commit=$(git log -1 --format=%ct "$branch" 2>/dev/null || echo 0)
  age_hours=$(( (now - last_commit) / 3600 ))

  if [ "$age_hours" -ge "${TTL_HOURS}" ]; then
    echo "   过期 (${age_hours}h): $branch"
    if [ "$DRY_RUN" = false ]; then
      # 检查是否有对应的 worktree 且有未保存改动
      wt_path="$(git rev-parse --show-toplevel)/../$(echo "$branch" | sed 's|work/||')"
      if [ -d "$wt_path" ] && ! git -C "$wt_path" diff --quiet 2>/dev/null; then
        echo "   ⚠️  跳过 (worktree 有未保存改动): $branch"
        continue
      fi
      git branch -D "$branch" 2>/dev/null || true
    fi
    stale=$((stale + 1))
  fi
done < <(git branch --format='%(refname:short)')
echo "   ✅ 已清理 $stale 个过期分支"

echo "=== Branch Prune 完成: 合并=$merged, 过期=$stale ==="
