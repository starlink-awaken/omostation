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
#   bash bin/ssot/sync-submodule-pointers.sh --verbose    # 显示详细错误信息
#   SYNC_ALL_SUBMODULES=1 bash bin/ssot/sync-submodule-pointers.sh  # 强制全部 fetch (CI 模式)
#
# 错误可见性:
#   - 默认: 显示 ⚠️/❌ 前缀的错误摘要
#   - --verbose: 显示完整 stderr、命令、退出码
#   - 退出码: 0=全部成功, 1=有需要修复的(可能已自动修复), 2=有无法修复的错误
#
# CI 注意:
#   - actions/checkout 使用 depth=1 浅克隆, 历史 commit 可能不可达
#   - 本脚本更新 index 中的 gitlink SHA, reachability gate 检查 index
#   - 需要 git add 让 gate 看到更新后的 index

set -euo pipefail

VERBOSE=false
CHECK_ONLY=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=true ;;
    --check-only) CHECK_ONLY=true ;;
    --dry-run) DRY_RUN=true ;;
  esac
done

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 2
fi

cd "$WS_ROOT"

# 获取所有子模块路径
SUBMODULES=$(git config --file .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}')
if [ -z "$SUBMODULES" ]; then
  echo "✅ 没有子模块"
  exit 0
fi

fixed=0
errors=0
declare -a ERROR_DETAILS=()

log_warn() { echo "⚠️  $1"; }
log_error() { echo "❌ $1" >&2; ERROR_DETAILS+=("$1"); }
log_info() { echo "   ℹ️  $1"; }
log_debug() { [ "$VERBOSE" = true ] && echo "   🔍 $1" || true; }

for sub in $SUBMODULES; do
  [ -e "$sub/.git" ] || continue

  # 获取当前指针 SHA
  current_sha=$(git ls-files --stage -- "$sub" | awk '{print $2}')
  [ -n "$current_sha" ] || continue

  # 检查是否可达
  if git -C "$sub" cat-file -e "$current_sha" 2>/dev/null; then
    log_debug "$sub: 指针 $current_sha 可达, 跳过"
    continue
  fi

  log_warn "$sub: 指针 ${current_sha:0:8} 不可达"

  if [ "$DRY_RUN" = true ]; then
    log_info "[dry-run] 将 fetch 并更新到最新 origin/main"
    fixed=$((fixed + 1))
    continue
  fi

  # 尝试 fetch (包括 unshallow) — 捕获错误到变量
  fetch_output=""
  fetch_rc=0
  if ! fetch_output="$(git -C "$sub" fetch --unshallow origin 2>&1)"; then
    # unshallow 失败, 尝试普通 fetch
    if ! fetch_output="$(git -C "$sub" fetch origin 2>&1)"; then
      fetch_rc=$?
      log_error "$sub: fetch 失败 (rc=$fetch_rc)"
      log_debug "fetch stderr: $fetch_output"
      log_debug "命令: git -C $sub fetch origin"
      # fetch 失败不一定是致命错误, 可能网络暂时不可用, 继续尝试
    fi
  fi

  # 再次检查
  if git -C "$sub" cat-file -e "$current_sha" 2>/dev/null; then
    log_info "fetch 后可达"
    continue
  fi

  # 仍然不可达 → 更新到最新 origin/main
  latest_sha=$(git -C "$sub" rev-parse origin/main 2>/dev/null) || true
  if [ -z "$latest_sha" ]; then
    log_error "$sub: 无法获取 origin/main (rev-parse 失败)"
    log_debug "可能原因: remote 未配置 / 网络问题 / 仓库为空"
    errors=$((errors + 1))
    continue
  fi

  log_info "更新到 origin/main (${latest_sha:0:8})"

  if [ "$CHECK_ONLY" = true ]; then
    fixed=$((fixed + 1))
    continue
  fi

  # 更新 index
  if git update-index --cacheinfo 160000,"$latest_sha","$sub"; then
    fixed=$((fixed + 1))
    log_debug "$sub: index 更新成功"
  else
    log_error "$sub: update-index 失败"
    errors=$((errors + 1))
  fi
done

echo "---"
if [ "$CHECK_ONLY" = true ] || [ "$DRY_RUN" = true ]; then
  echo "检查完成: $fixed 个需要修复, $errors 个错误"
else
  echo "同步完成: 修复 $fixed 个, $errors 个错误"
fi

# 详细错误汇总
if [ "$errors" -gt 0 ] && [ "$VERBOSE" = true ]; then
  echo ""
  echo "=== 错误汇总 ==="
  for detail in "${ERROR_DETAILS[@]}"; do
    echo "  - $detail"
  done
fi

# 退出码: 0=全部正常, 1=有修复(可接受), 2=有无法修复的错误
[ "$errors" -gt 0 ] && exit 2
[ "$fixed" -gt 0 ] && exit 1
exit 0
