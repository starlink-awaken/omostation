#!/usr/bin/env bash
# test-sandbox-timemachine.sh — 集成测试: Git Worktree 物理沙箱 + 时光机回滚 (BET-Y1Q4-T10-133)
#
# 验证:
#   1. --help exit 0 (verify 命令)
#   2. 沙箱创建后主工作区 git status 不受影响 (隔离性)
#   3. 沙箱内失败 → 回滚后主工作区 git status 干净度 100% (时光机)
#   4. 沙箱内禁止 push/merge → 拦截
#   5. 熔断 + locked 残留清理 (2026-09-29 增): 用**与 runner 速度无关**的两条确定性构造 ——
#      SANDBOX_TIMEOUT_S=0 (0 秒预算必然熔断) 与 手工 `git worktree lock` (熔断被 kill 在
#      register+lock 之后的真实形态)。早先版本用 SANDBOX_TIMEOUT_S=1, 但 CI runner 上
#      `git worktree add` < 1s 完成 ⇒ 构造不成立 (PR #4555 首跑实证), 故弃用时间型构造。
#
# 用法: bash tests/integration/test-sandbox-timemachine.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/bin/gac/resident-sandbox-timemachine.sh"
SESSION="it-$(date +%s)"
SANDBOX_WT="$(dirname "$ROOT")/ws-sandbox-$SESSION"   # 与脚本 sandbox_path() 同口径
PASS=0
FAIL=0

ok()  { echo "✅ $1"; PASS=$((PASS + 1)); }
bad() { echo "❌ $1"; FAIL=$((FAIL + 1)); }

# 兜底清理: 任何中途退出 (含断言失败提前退出) 都不给主仓留沙箱。rollback 幂等。
cleanup() { bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "=== [1/5] --help exit 0 ==="
if bash "$SCRIPT" --help >/dev/null 2>&1; then ok "--help exit 0"; else bad "--help exit 0"; fi

echo "=== [2/5] 沙箱创建隔离性: 主工作区不受影响 ==="
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

echo "=== [3/5] 失败 → 时光机回滚后主工作区干净度 100% ==="
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

echo "=== [4/5] 沙箱内禁止 push/merge → 拦截 ==="
# 先重建沙箱 (上一步已回滚)
bash "$SCRIPT" create "$SESSION" >/dev/null 2>&1 || true
if bash "$SCRIPT" run "$SESSION" -- "git push origin main" >/dev/null 2>&1; then
  bad "push 未被拦截 (应 FAIL)"
else
  ok "git push 被硬约束拦截"
fi
bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true

echo "=== [5/5] 熔断与 locked 残留 (确定性构造) ==="
# 判据统一为「目录 + worktree 注册」两级 —— 只查目录会漏掉幽灵注册, 只查注册会漏掉 locked 目录。
residual_of() {
  local wt="$1" out=""
  if [ -d "$wt" ]; then out="目录仍在"; fi
  if git -C "$ROOT" worktree list --porcelain | command grep -qxF "worktree $wt"; then
    out="${out:+$out; }worktree 注册仍在"
  fi
  printf '%s' "$out"
}

# (a) 0 秒预算 ⇒ 必然熔断 (与 runner 速度无关), 且零残留
#     判别力边界 (实测): 0s 预算下 git 通常还来不及 register+lock 就被 kill ⇒ 本段守的是
#     「熔断后不留残留」这一**结果**(防回归), 而不是 create 失败分支里 unlock 的必要性
#     (回退该分支的 unlock 后本段仍绿)。create 分支的 unlock 与 (b) 段 rollback 的 unlock
#     是同一规律的两个入口, 判别力由 (b) 段提供。
if SANDBOX_TIMEOUT_S=0 bash "$SCRIPT" create "$SESSION" >/dev/null 2>&1; then
  bad "0s 预算下创建应熔断, 却成功了"
  bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true
else
  ok "0s 预算 ⇒ 熔断返回非 0 (circuit_breaker 生效)"
fi
res="$(residual_of "$SANDBOX_WT")"
if [ -n "$res" ]; then
  bad "熔断后残留 ($res)"
  bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true
else
  ok "熔断后零残留 (目录 + worktree 注册)"
fi

# (b) locked 沙箱 ⇒ rollback 能清掉 (locked 会让 `worktree remove` 与 `prune` 都跳过)
if bash "$SCRIPT" create "$SESSION" >/dev/null 2>&1; then
  git -C "$ROOT" worktree lock "$SANDBOX_WT" >/dev/null 2>&1 || true
  # 构造有效性断言: 没锁上 ⇒ 本段失去判别力, 必须红而不是假绿
  if git -C "$ROOT" worktree list | command grep -F "$SANDBOX_WT" | command grep -q locked; then
    ok "构造有效: 沙箱处于 locked"
  else
    bad "构造无效: 未能锁定 (本段失去判别力)"
  fi
  bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true
  res="$(residual_of "$SANDBOX_WT")"
  if [ -n "$res" ]; then
    bad "locked 沙箱回滚后残留 ($res)"
  else
    ok "locked 沙箱可被 rollback 清干净"
  fi
else
  bad "前置: 创建沙箱失败 (无法构造 locked)"
fi

echo ""
echo "结果: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ]
