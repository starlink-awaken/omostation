#!/usr/bin/env bash
# test-sandbox-timemachine.sh — 集成测试: Git Worktree 物理沙箱 + 时光机回滚 (BET-Y1Q4-T10-133)
#
# 验证:
#   1. --help exit 0 (verify 命令)
#   2. 沙箱创建后主工作区 git status 不受影响 (隔离性)
#   3. 沙箱内失败 → 回滚后主工作区 git status 干净度 100% (时光机)
#   4. 沙箱内禁止 push/merge → 拦截
#
# 用法: bash tests/integration/test-sandbox-timemachine.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/bin/gac/resident-sandbox-timemachine.sh"
SESSION="it-$(date +%s)"
PASS=0
FAIL=0

ok()  { echo "✅ $1"; PASS=$((PASS + 1)); }
bad() { echo "❌ $1"; FAIL=$((FAIL + 1)); }

echo "=== [1/4] --help exit 0 ==="
if bash "$SCRIPT" --help >/dev/null 2>&1; then ok "--help exit 0"; else bad "--help exit 0"; fi

echo "=== [2/4] 沙箱创建隔离性: 主工作区不受影响 ==="
BEFORE="$(git -C "$ROOT" status --porcelain | wc -l | tr -d ' ')"
if bash "$SCRIPT" create "$SESSION" >/dev/null 2>&1; then
  ok "沙箱创建成功 (session=$SESSION)"
else
  bad "沙箱创建"
  exit 1
fi
AFTER="$(git -C "$ROOT" status --porcelain | wc -l | tr -d ' ')"
if [ "$BEFORE" = "$AFTER" ]; then
  ok "主工作区 git status 不受沙箱创建影响 ($BEFORE=$AFTER)"
else
  bad "主工作区被污染 (before=$BEFORE after=$AFTER)"
fi

echo "=== [3/4] 失败 → 时光机回滚后主工作区干净度 100% ==="
# 在沙箱内制造失败 (exit 1 命令)
if bash "$SCRIPT" run "$SESSION" -- "exit 1" >/dev/null 2>&1; then
  bad "沙箱内失败命令应返回非 0"
else
  ok "沙箱内失败命令正确返回非 0"
fi
# 回滚
if bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1; then
  ok "时光机回滚执行"
else
  bad "时光机回滚"
fi
# 主工作区干净度 100%
CLEAN="$(git -C "$ROOT" status --porcelain | wc -l | tr -d ' ')"
if [ "$CLEAN" = "$BEFORE" ]; then
  ok "回滚后主工作区 git status 干净度 100% (count=$CLEAN)"
else
  bad "回滚后主工作区不干净 (before=$BEFORE after=$CLEAN)"
fi

echo "=== [4/4] 沙箱内禁止 push/merge → 拦截 ==="
# 先重建沙箱 (上一步已回滚)
bash "$SCRIPT" create "$SESSION" >/dev/null 2>&1 || true
if bash "$SCRIPT" run "$SESSION" -- "git push origin main" >/dev/null 2>&1; then
  bad "push 未被拦截 (应 FAIL)"
else
  ok "git push 被硬约束拦截"
fi
bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true

echo ""
echo "结果: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ]
