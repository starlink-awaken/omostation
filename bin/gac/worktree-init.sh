#!/usr/bin/env bash
# worktree-init.sh — 新 worktree 一键初始化关键子模块 (BET-Y1Q3-T10-09)
# 用法: bash bin/gac/worktree-init.sh [--minimal|--full]
#   --minimal (默认): 仅 ruff scope 四子模块(omo/ecos/agora/cockpit), ~30s
#   --full: 全部子模块 (开启 --filter=blob:none 后 ~1min, 原 >5min)
# 前提: 主仓 /Users/xiamingxing/Workspace 存在(作为 --reference 本地加速)
# 性能优化 (T10-138 submodule 调研落地, 2026-09-07):
#   --filter=blob:none: lazy-fetch blob, 节省 ~90% 磁盘
#   --depth 1: 仅当前 commit
#   --reference: 主仓作本地 object pool 复用
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
MAIN_WS="${OMO_WORKSPACE_ROOT:-$HOME/Workspace}"
MODE="${1:---minimal}"

if [ "$MODE" = "--minimal" ]; then
  SUBS=(projects/omo projects/ecos projects/agora projects/cockpit)
else
  SUBS=($(git config --file .gitmodules --get-regexp 'submodule\..*\.path' | awk '{print $2}'))
fi

echo "worktree-init: mode=$MODE root=$ROOT"
FAIL=0
for sub in "${SUBS[@]}"; do
  # 已有内容则跳过
  if [ -d "$ROOT/$sub" ] && [ "$(ls -A "$ROOT/$sub" 2>/dev/null | grep -cv '^\.git$')" -gt 0 ]; then
    echo "  ✓ $sub (already initialized)"
    continue
  fi
  # 空目录或不存在 → 清理后 init
  rm -rf "$ROOT/$sub"
  # 用主仓作 reference 加速(无网络克隆) + --filter=blob:none (lazy blob)
  if git -C "$ROOT" submodule update --init --depth 1 --filter=blob:none \
      --reference "$MAIN_WS/$sub" "$sub" > /dev/null 2>&1; then
    git -C "$ROOT/$sub" reset --hard HEAD > /dev/null 2>&1
    echo "  ✓ $sub (initialized from local reference + filter blob:none)"
  else
    # fallback 无 reference 直连
    if git -C "$ROOT" submodule update --init --depth 1 --filter=blob:none \
        "$sub" > /dev/null 2>&1; then
      git -C "$ROOT/$sub" reset --hard HEAD > /dev/null 2>&1
      echo "  ✓ $sub (initialized from remote + filter blob:none)"
    else
      echo "  ✗ $sub (FAILED)"
      FAIL=1
    fi
  fi
done

# 修复空检出(git dir 在但文件未物化 — 本周三连坑)
for sub in "${SUBS[@]}"; do
  if [ -f "$ROOT/$sub/.git" ] && [ ! -f "$ROOT/$sub/package.json" ] && [ ! -d "$ROOT/$sub/src" ]; then
    git -C "$ROOT/$sub" checkout -- . 2>/dev/null || true
    git -C "$ROOT/$sub" checkout -f HEAD -- . 2>/dev/null || true
  fi
done

exit $FAIL
