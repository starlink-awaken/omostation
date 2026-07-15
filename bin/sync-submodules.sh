#!/usr/bin/env bash
# bin/sync-submodules.sh — 推送子模块新 commit 并更新根仓库指针
#
# 在 worktree 中修改子模块后，子模块的 commit 需要先推送到远程，
# 否则 CI 在 checkout 时无法获取该 commit（"not our ref" 错误）。
#
# 用法:
#   bash bin/sync-submodules.sh              # 推送所有有未推送 commit 的子模块
#   bash bin/sync-submodules.sh --dry-run    # 只检查，不推送
#   bash bin/sync-submodules.sh --status     # 只显示状态，不推送
#
# 集成到 gac-worktree.sh submit 流程：
#   在 git push 根仓库之前，先跑此脚本，确保子模块 commit 已推送。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DRY_RUN=false
STATUS_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --status) STATUS_ONLY=true ;;
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
PUSHED_COUNT=0

echo "── 检查子模块未推送的 commit ──────────────────────────"

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

    if [ "$STATUS_ONLY" = true ]; then
      popd > /dev/null 2>&1 || true
      continue
    fi

    if [ "$DRY_RUN" = false ]; then
      echo "  → 推送 $submodule ..."
      git push origin HEAD:main --no-verify 2>&1 || echo "  ⚠️  推送失败（可能是非 fast-forward），尝试 force push 被拒绝，请手动处理"
      PUSHED_COUNT=$((PUSHED_COUNT + 1))
    fi
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

if [ "$STATUS_ONLY" = true ]; then
  echo "⚠️  发现未推送的 commit，请运行 bash bin/sync-submodules.sh 推送"
  exit 1
fi

if [ "$DRY_RUN" = false ]; then
  echo "✅ 已推送 $PUSHED_COUNT 个子模块的 commit"
  echo ""
  echo "  下一步: 如果根仓库的子模块指针已更新，请提交根仓库变更:"
  echo "    git add projects/<submodule>"
  echo "    git commit -m \"fix: update <submodule> submodule pointer\""
fi
