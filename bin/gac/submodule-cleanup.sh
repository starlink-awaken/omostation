#!/usr/bin/env bash
# 机制 22d (2026-09-06): 子模块远程分支/Tags 清理.
#
# 清理规则:
#   1. 远程分支: 已合入 origin/main 且超过 TTL 天数的 branch
#   2. Tags: 超过保留数量的旧 tags (保留最近 N 个)
#   3. 悬空 tracking: 远程已删除但本地仍 tracking 的分支
#
# 使用:
#   bash bin/gac/submodule-cleanup.sh              # dry-run (仅查看)
#   bash bin/gac/submodule-cleanup.sh --apply       # 实际执行清理
#   bash bin/gac/submodule-cleanup.sh --ttl 30      # 设置 TTL 天数 (默认 30)
#   bash bin/gac/submodule-cleanup.sh --keep-tags 20 # 保留最近 N 个 tags (默认 20)
#   bash bin/gac/submodule-cleanup.sh --json        # JSON 输出

set -euo pipefail

WORKSPACE="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
APPLY=0
TTL_DAYS=30
KEEP_TAGS=20
JSON_OUTPUT=0

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --ttl) TTL_DAYS="$2"; shift ;;
    --keep-tags) KEEP_TAGS="$2"; shift ;;
    --json) JSON_OUTPUT=1 ;;
  esac
done

echo "=== 子模块清理 (TTL=${TTL_DAYS}d, keep-tags=${KEEP_TAGS}, apply=${APPLY}) ==="

CLEANUP_LOG="[]"

cleanup_submodule() {
  local sub_path="$1"
  local sub_name="$(basename "$sub_path")"
  cd "$sub_path"

  # 跳过非 git 目录
  if [ ! -d ".git" ] && [ ! -f ".git" ]; then
    return
  fi

  local remote="origin"
  local main_branch="main"

  # 获取远端 main tip
  local main_tip
  main_tip=$(git rev-parse --verify "$remote/$main_branch" 2>/dev/null || echo "")
  if [ -z "$main_tip" ]; then
    return
  fi

  echo ""
  echo "── $sub_name ──"

  # 1. 清理已合入 main 且超过 TTL 天数的远程分支
  local merged_branches
  merged_branches=$(git branch -r --merged "$remote/$main_branch" 2>/dev/null \
    | grep "  $remote/" \
    | grep -v "HEAD" \
    | grep -v "$main_branch$" \
    | sed 's/^ *//' || true)

  if [ -n "$merged_branches" ]; then
    echo "  已合入 main 的远程分支:"
    echo "$merged_branches" | while read -r branch; do
      # 检查最后 commit 时间
      local last_commit_date
      last_commit_date=$(git log -1 --format='%ci' "$branch" 2>/dev/null || echo "")
      if [ -z "$last_commit_date" ]; then
        continue
      fi

      local last_commit_epoch
      last_commit_epoch=$(date -j -f '%Y-%m-%d %H:%M:%S %z' "$last_commit_date" '+%s' 2>/dev/null || echo 0)
      local now_epoch
      now_epoch=$(date '+%s')
      local age_days=$(( (now_epoch - last_commit_epoch) / 86400 ))

      if [ "$age_days" -gt "$TTL_DAYS" ]; then
        echo "    - $branch (${age_days}d)"
        if [ "$APPLY" -eq 1 ]; then
          local short_branch="${branch#$remote/}"
          git push "$remote" --delete "$short_branch" 2>/dev/null || echo "      ⚠️ 删除失败"
        fi
      fi
    done
  fi

  # 2. 清理过期 tags
  local tag_count
  tag_count=$(git tag | wc -l | tr -d ' ')
  if [ "$tag_count" -gt "$KEEP_TAGS" ]; then
    echo "  Tags: ${tag_count} 个 (保留最近 ${KEEP_TAGS} 个)"
    if [ "$APPLY" -eq 1 ]; then
      # 按时间排序，删除最旧的 tags
      git tag --sort=-creatordate | tail -n +"$((KEEP_TAGS + 1))" | while read -r tag; do
        git tag -d "$tag" 2>/dev/null || true
        git push "$remote" --delete "$tag" 2>/dev/null || true
      done
    fi
  fi

  # 3. 清理悬空 tracking 分支
  local pruned
  pruned=$(git remote prune "$remote" --dry-run 2>/dev/null || true)
  if [ -n "$pruned" ]; then
    echo "  悬空 tracking 分支:"
    echo "$pruned" | sed 's/^/    /'
    if [ "$APPLY" -eq 1 ]; then
      git remote prune "$remote" 2>/dev/null || true
    fi
  fi

  cd "$WORKSPACE"
}

# 遍历所有子模块
for sub in $(grep 'path = ' .gitmodules 2>/dev/null | awk '{print $3}'); do
  if [ -d "$sub" ]; then
    cleanup_submodule "$sub"
  fi
done

echo ""
echo "=== 清理完成 ==="
if [ "$APPLY" -eq 0 ]; then
  echo "  (dry-run 模式, 使用 --apply 实际执行)"
fi
