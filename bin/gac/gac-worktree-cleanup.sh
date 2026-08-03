#!/bin/bash
# gac-worktree-cleanup.sh — PASW 子模块 Worktree 定时清理回收
#
# 回收过期的子模块 worktree 和 root worktree, 防止磁盘泄漏.
# 设计为 cron 定期执行 (推荐每 6h).
#
# 活跃性判断 (2026-08-03 修复): 最近 commit 时间 + open PR 检查,
# 替代不可靠的 mtime/atime (noatime 下不更新, 曾误清活跃 worktree
# 导致 submit 中断 + gate FileNotFoundError).
# 自包含: #850 后 main 的 gac-worktree.sh 无 cleanup 函数, 旧版委托会断.
#
# 用法:
#   bash bin/gac/gac-worktree-cleanup.sh              # 默认 TTL 24h
#   PASW_TTL_HOURS=12 bash bin/gac/gac-worktree-cleanup.sh  # 自定义 TTL
#   bash bin/gac/gac-worktree-cleanup.sh --dry-run    # 只查看, 不删除
#
# Cron 示例 (每 6h):
#   0 */6 * * * cd /Users/xiamingxing/Workspace && bash bin/gac/gac-worktree-cleanup.sh >> .omo/_log/pasw-cleanup.log 2>&1

set -euo pipefail

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

PASW_TTL_HOURS="${PASW_TTL_HOURS:-24}"
WS_PARENT="$(dirname "$WS_ROOT")"
# CANONICAL_ROOT_REPO: 从 origin url 推导 owner/repo (gh pr list 需要)
CANONICAL_ROOT_REPO=$(git -C "$WS_ROOT" config --get remote.origin.url 2>/dev/null \
  | sed 's#.*github.com[:/]##; s#\.git$##' || echo "starlink-awaken/omostation")

echo "=== PASW Cleanup $(date -u +%Y-%m-%dT%H:%M:%SZ) TTL=${PASW_TTL_HOURS}h dry=$DRY_RUN repo=$CANONICAL_ROOT_REPO ==="

now=$(date +%s)
reclaimed=0
skipped=0
for wt_path in "$WS_PARENT"/ws-*/; do
  [ -d "$wt_path" ] || continue
  wt_name=$(basename "$wt_path")

  # open PR 检查: 有 PR = 活跃, 跳过 (防误清正在用的 worktree)
  branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
  if [ -n "$branch" ] && command -v gh >/dev/null 2>&1; then
    if gh pr list --repo "$CANONICAL_ROOT_REPO" --head "$branch" --state open 2>/dev/null | grep -q .; then
      echo "⏭️  $wt_name: 分支 $branch 有 open PR, 跳过 (活跃)"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  # 用最近 commit 时间判断过期 (比 mtime/atime 可靠: 反映真实工作)
  last_commit=$(git -C "$wt_path" log -1 --format=%ct 2>/dev/null || echo 0)
  if [ "$last_commit" -eq 0 ]; then
    echo "⚠️  $wt_name: 无 commit 历史, 跳过 (避免误删)"
    skipped=$((skipped + 1))
    continue
  fi
  age_hours=$(( (now - last_commit) / 3600 ))

  if [ "$age_hours" -ge "$PASW_TTL_HOURS" ]; then
    echo "🧹 回收过期 worktree: $wt_name (最后 commit: ${age_hours}h 前)"
    for sub_wt in "$wt_path"/.subtrees/*/; do
      [ -d "$sub_wt" ] || continue
      if [ "$DRY_RUN" = true ]; then
        echo "   └─ [dry-run] 子模块 worktree: $(basename "$sub_wt")"
      else
        git -C "$wt_path" worktree remove "$sub_wt" 2>/dev/null || \
          echo "   ⚠️  子模块 worktree 移除失败 (可能有改动), 保留: $sub_wt"
      fi
    done
    if [ "$DRY_RUN" = true ]; then
      continue
    fi
    rmdir "$wt_path/.subtrees" 2>/dev/null || true
    # root worktree (失败 = 有改动, 不 rm -rf 强删)
    git worktree remove "$wt_path" 2>/dev/null || {
      echo "   ⚠️  root worktree 移除失败 (可能有未保存改动), 跳过"
      continue
    }
    reclaimed=$((reclaimed + 1))
    echo "   ✅ 已回收 $wt_name"
  fi
done

echo "=== PASW Cleanup 完成: 回收 $reclaimed, 跳过 $skipped ==="
