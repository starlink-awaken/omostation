#!/usr/bin/env bash
# gac-worktree-prune.sh — 清理已合并的 work 分支和过期分支
#
# 清理规则:
# 1. 远程已删除的本地分支 (--prune)
# 2. 已合并到 main 的本地 work 分支
# 3. 超过 TTL 且无 open PR 的本地 work 分支
#
# 用法:
#   bash bin/gac/gac-worktree-prune.sh              # 执行清理
#   bash bin/gac/gac-worktree-prune.sh --dry-run    # 只查看不删除

set -euo pipefail

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

REMOTE="${REMOTE:-origin}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"

echo "=== GaC Worktree Branch Prune $(date -u +%Y-%m-%dT%H:%M:%Z) dry=$DRY_RUN ==="

# 1. 清理远程已删除的本地分支
echo "── 1. 清理远程已删除的分支 ──"
if [ "$DRY_RUN" = true ]; then
  echo "   [dry-run] git fetch --prune (只显示, 不删除)"
  git branch -r | grep "$REMOTE/" | while read remote_branch; do
    branch_name=$(echo "$remote_branch" | sed "s|$REMOTE/||")
    if [ "$branch_name" != "HEAD" ] && ! git ls-remote --heads "$REMOTE" "$branch_name" 2>/dev/null | grep -q .; then
      echo "   可清理: $remote_branch"
    fi
  done
else
  git fetch --prune "$REMOTE" 2>&1 | tail -5
  echo "   ✅ 已 prune 远程删除的分支"
fi

# 2. 清理已合并到 main 的本地 work 分支
echo "── 2. 清理已合并的 work 分支 ──"
merged=0
while IFS= read -r branch; do
  branch=$(echo "$branch" | tr -d ' *')
  [ -z "$branch" ] && continue
  [ "$branch" = "$MAIN_BRANCH" ] && continue
  [[ "$branch" != work/* ]] && continue

  # 检查是否已合并到 main
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
echo "── 3. 清理过期 work 分支 (TTL: ${PASW_TTL_HOURS:-24}h) --"
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

  if [ "$age_hours" -ge "${PASW_TTL_HOURS:-24}" ]; then
    echo "   过期 (${age_hours}h): $branch"
    if [ "$DRY_RUN" = false ]; then
      git branch -D "$branch" 2>/dev/null || true
    fi
    stale=$((stale + 1))
  fi
done < <(git branch --format='%(refname:short)')

echo "   ✅ 已清理 $stale 个过期分支"

# 4. 清理孤儿 worktree (worktree 目录已删除但 git 仍记录, 或分支已不存在)
echo "── 4. 清理孤儿 worktree ──"
orphaned=0
while IFS= read -r wt_line; do
  # Skip main worktree (first line)
  wt_path=$(echo "$wt_line" | awk '{print $1}')
  [ "$wt_path" = "$(git rev-parse --show-toplevel)" ] && continue

  # Check if worktree directory exists
  if [ ! -d "$wt_path" ]; then
    echo "   孤儿 (目录不存在): $wt_path"
    if [ "$DRY_RUN" = false ]; then
      git worktree remove "$wt_path" --force 2>/dev/null || true
    fi
    orphaned=$((orphaned + 1))
    continue
  fi

  # Check if branch still exists
  wt_branch=$(echo "$wt_line" | grep -o '\[.*\]' | tr -d '[]')
  if [ -n "$wt_branch" ] && ! git rev-parse --verify "$wt_branch" >/dev/null 2>&1; then
    echo "   孤儿 (分支已删除): $wt_path"
    if [ "$DRY_RUN" = false ]; then
      git worktree remove "$wt_path" --force 2>/dev/null || true
    fi
    orphaned=$((orphaned + 1))
    continue
  fi
done < <(git worktree list)

# Prune stale worktree metadata
if [ "$DRY_RUN" = false ]; then
  git worktree prune --verbose 2>/dev/null || true
fi
echo "   ✅ 已清理 $orphaned 个孤儿 worktree"

echo "=== Branch Prune 完成: 合并=$merged, 过期=$stale, 孤儿worktree=$orphaned ==="
