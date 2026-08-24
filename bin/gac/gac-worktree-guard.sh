#!/usr/bin/env bash
# gac-worktree-guard.sh — worktree 数量硬上限门禁
#
# 用法:
#   bash bin/gac/gac-worktree-guard.sh --check    超限返回 1 (CI 用)
#   bash bin/gac/gac-worktree-guard.sh --enforce  输出清理建议
#
# 环境变量:
#   MAX_WORKTREES=8   (上限, 默认 8)
#   WARN_THRESHOLD=6  (警告阈值, 默认 6)
#
set -euo pipefail

MAX_WORKTREES="${MAX_WORKTREES:-8}"
WARN_THRESHOLD="${WARN_THRESHOLD:-6}"
MODE="${1:---check}"

# 找到 workspace root（包含 .omo 目录的顶层仓库），而非子模块 root
_cwd="$(pwd)"
_root="$(git -C "$_cwd" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "❌ 不在 git 仓库" >&2
  exit 2
}
# 向上查找含 .omo 的目录（workspace root 标志）
ROOT="$_root"
while [ "$ROOT" != "/" ]; do
  if [ -d "$ROOT/.omo" ]; then
    break
  fi
  ROOT="$(dirname "$ROOT")"
done
if [ ! -d "$ROOT/.omo" ]; then
  echo "❌ 未找到 workspace root（无 .omo 目录）" >&2
  exit 2
fi

COUNT=$(git -C "$ROOT" worktree list --porcelain | grep -c "^worktree " || echo 0)

echo "worktree count: $COUNT (max=$MAX_WORKTREES, warn=$WARN_THRESHOLD)"

case "$MODE" in
  --check)
    if [ "$COUNT" -gt "$MAX_WORKTREES" ]; then
      echo "❌ 超限: $COUNT > $MAX_WORKTREES" >&2
      echo "运行 'bash bin/gac/gac-worktree-prune.sh' 清理" >&2
      exit 1
    elif [ "$COUNT" -gt "$WARN_THRESHOLD" ]; then
      echo "⚠️ 接近上限: $COUNT > $WARN_THRESHOLD"
    fi
    echo "✅ worktree 数量正常"
    ;;
  --enforce)
    if [ "$COUNT" -gt "$MAX_WORKTREES" ]; then
      echo "🔧 自动清理..."
      bash "$(dirname "$0")/gac-worktree-prune.sh" --apply
    else
      echo "✅ 无需清理 ($COUNT <= $MAX_WORKTREES)"
    fi
    ;;
  *)
    echo "用法: $0 [--check|--enforce]" >&2
    exit 2
    ;;
esac
