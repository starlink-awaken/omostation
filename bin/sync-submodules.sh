#!/usr/bin/env bash
# bin/sync-submodules.sh — 检测子模块未推送/不可达 commit (WP1 Wave B2: detection-only)
#
# 在 worktree 中修改子模块后，子模块的 commit 需要先由托管交付事务推送到远程，
# 否则 CI 在 checkout 时无法获取该 commit（"not our ref" 错误）。
#
# 用法:
#   bash bin/sync-submodules.sh              # 检测未推送 commit；有则 exit 1
#   bash bin/sync-submodules.sh --dry-run    # 同上 (兼容别名)
#   bash bin/sync-submodules.sh --status     # 同上 (兼容别名)
#
# WP1 Wave B2: 不再 push；仅报告并非零退出。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

for arg in "$@"; do
  case "$arg" in
    --dry-run|--status) ;;
    *)
      echo "未知参数: $arg (仅支持 --dry-run / --status；默认即为 detection-only)" >&2
      exit 2
      ;;
  esac
done

cd "$WORKSPACE_ROOT"

# 获取所有子模块路径
SUBMODULES=$(git config --file .gitmodules --get-regexp path | awk '{print $2}' || true)

if [ -z "$SUBMODULES" ]; then
  echo "没有找到子模块"
  exit 0
fi

HAS_UNPUSHED=false

echo "── 检查子模块未推送的 commit (detection-only) ──────────"

for submodule in $SUBMODULES; do
  if [ ! -d "$submodule" ] || [ ! -d "$submodule/.git" ] && [ ! -f "$submodule/.git" ]; then
    continue
  fi

  pushd "$submodule" > /dev/null 2>&1 || continue

  # 获取远程
  REMOTE=$(git remote 2>/dev/null | head -1 || true)
  if [ -z "$REMOTE" ]; then
    popd > /dev/null 2>&1 || true
    continue
  fi

  # 检查是否有未推送的 commit
  UNPUSHED=$(git log --oneline "$REMOTE/main..HEAD" 2>/dev/null || true)
  UNPUSHED_COUNT=$(echo "$UNPUSHED" | grep -c . || true)

  # 也检查 detached HEAD 情况
  if [ "$UNPUSHED_COUNT" -eq 0 ]; then
    UNPUSHED=$(git log --oneline "origin/main..HEAD" 2>/dev/null || true)
    UNPUSHED_COUNT=$(echo "$UNPUSHED" | grep -c . || true)
  fi

  if [ "$UNPUSHED_COUNT" -gt 0 ]; then
    HAS_UNPUSHED=true
    echo "  ⚠️  $submodule: $UNPUSHED_COUNT 个未推送的 commit"
    echo "$UNPUSHED" | while read -r line; do
      echo "      $line"
    done
    echo "  → 需要托管交付事务发布 (本脚本不再 push)"
  else
    echo "  ✅  $submodule: 已同步"
  fi

  popd > /dev/null 2>&1 || true
done

echo ""
if [ "$HAS_UNPUSHED" = false ]; then
  echo "✅ 所有子模块已同步，无需推送"
  exit 0
fi

echo "❌ 发现未推送的子模块 commit；detection-only，拒绝自动 push"
exit 1
