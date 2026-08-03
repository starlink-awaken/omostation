#!/usr/bin/env bash
# sync-submodule-pointers.sh — 自动同步子模块指针到可达 commit
#
# 问题: PR 分支的子模块指针可能指向 submodule remote 上还没有的 commit → CI reachability gate 失败.
# 解法: 自动 fetch 所有子模块, 如果指针不可达则更新到最新 origin/main.
#
# 用法:
#   bash bin/ssot/sync-submodule-pointers.sh              # 自动修复
#   bash bin/ssot/sync-submodule-pointers.sh --check-only  # 只检查不修复
#   bash bin/ssot/sync-submodule-pointers.sh --dry-run    # 只显示将要做的修改

set -euo pipefail

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi

CHECK_ONLY=false
DRY_RUN=false
case "${1:-}" in
  --check-only) CHECK_ONLY=true ;;
  --dry-run) DRY_RUN=true ;;
esac

cd "$WS_ROOT"

# 获取所有子模块路径
SUBMODULES=$(git config --file .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}')
if [ -z "$SUBMODULES" ]; then
  echo "✅ 没有子模块"
  exit 0
fi

fixed=0
errors=0

for sub in $SUBMODULES; do
  [ -e "$sub/.git" ] || continue

  # 获取当前指针 SHA
  current_sha=$(git ls-files --stage -- "$sub" | awk '{print $2}')
  [ -n "$current_sha" ] || continue

  # 检查是否可达
  if git -C "$sub" cat-file -e "$current_sha" 2>/dev/null; then
    continue
  fi

  echo "⚠️  $sub: 指针 $current_sha 不可达, 尝试 fetch..."

  if [ "$DRY_RUN" = true ]; then
    echo "   [dry-run] 将 fetch 并更新到最新 origin/main"
    fixed=$((fixed + 1))
    continue
  fi

  # 尝试 fetch (包括 unshallow)
  git -C "$sub" fetch --unshallow origin 2>/dev/null || git -C "$sub" fetch origin 2>/dev/null || true

  # 再次检查
  if git -C "$sub" cat-file -e "$current_sha" 2>/dev/null; then
    echo "   ✅ fetch 后可达"
    continue
  fi

  # 仍然不可达 → 更新到最新 origin/main
  latest_sha=$(git -C "$sub" rev-parse origin/main 2>/dev/null)
  if [ -z "$latest_sha" ]; then
    echo "   ❌ 无法获取 origin/main"
    errors=$((errors + 1))
    continue
  fi

  echo "   🔄 更新到 origin/main ($latest_sha)"

  if [ "$CHECK_ONLY" = true ]; then
    fixed=$((fixed + 1))
    continue
  fi

  # 更新 index
  git update-index --cacheinfo 160000,"$latest_sha","$sub"
  fixed=$((fixed + 1))
done

echo "---"
if [ "$CHECK_ONLY" = true ] || [ "$DRY_RUN" = true ]; then
  echo "检查完成: $fixed 个需要修复, $errors 个错误"
else
  echo "同步完成: 修复 $fixed 个, 错误 $errors 个"
fi

[ "$errors" -gt 0 ] && exit 1
exit 0
