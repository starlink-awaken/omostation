#!/usr/bin/env bash
set -euo pipefail
# 机制: submodule bump 前检查 origin/main 是否已领先
# 防止 #1202 重演 (并行 agent 已 bump 到更新版本时仍白跑一轮)

sub="${1:?用法: pre-bump-check <submodule-path>}"
repo=$(git -C "$sub" remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}')

echo "[pre-bump] 检查 $sub ($repo) 远程是否有更新..."

# fetch 远程 main
git -C "$sub" fetch origin main --quiet 2>/dev/null || { echo "[pre-bump] ⚠️ 无法 fetch 远程, 跳过检查"; exit 0; }

local_head=$(git -C "$sub" rev-parse HEAD)
remote_main=$(git -C "$sub" rev-parse origin/main 2>/dev/null || echo "$local_head")

if [ "$local_head" != "$remote_main" ]; then
  # 检查 local_head 是否是 remote_main 的祖先 (即远程领先)
  if git -C "$sub" merge-base --is-ancestor "$local_head" "$remote_main" 2>/dev/null; then
    echo "[pre-bump] ❌ 远程 origin/main ($remote_main) 已领先于本地 HEAD ($local_head)"
    echo "[pre-bump] ❌ 并行 agent 可能已 bump, 本次 bump 冗余 → 中止"
    echo "[pre-bump] 提示: 如需强制 bump, 请先确认 worktree HEAD 已含目标 commit"
    exit 1
  fi
fi

echo "[pre-bump] ✅ 本地 HEAD 未落后于远程, 可以 bump"
exit 0
