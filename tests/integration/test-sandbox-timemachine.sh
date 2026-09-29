#!/usr/bin/env bash
# test-sandbox-timemachine.sh — 集成测试: Git Worktree 物理沙箱 + 时光机回滚 (BET-Y1Q4-T10-133)
#
# 验证:
#   1. --help exit 0 (verify 命令)
#   2. 沙箱创建后主工作区 git status 不受影响 (隔离性)
#   3. 沙箱内失败 → 回滚后主工作区 git status 干净度 100% (时光机)
#   4. 沙箱内禁止 push/merge → 拦截
#   5. 熔断仍可被触发 → 非 0 且零残留 (2026-09-29 增: 阈值改为可 env 覆盖后, 用 SANDBOX_TIMEOUT_S=1
#      构造超时。这条同时是「熔断器没被提阈值提废」的负控制 —— 若哪天阈值提得让 1s 也能过, 它会红)
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

echo "=== [5/5] 熔断可触发 (SANDBOX_TIMEOUT_S=1) → 非 0 且零残留 ==="
if SANDBOX_TIMEOUT_S=1 bash "$SCRIPT" create "$SESSION" >/dev/null 2>&1; then
  bad "1s 预算下创建应熔断 (返回非 0), 却成功了"
else
  ok "熔断返回非 0 (circuit_breaker 生效)"
fi
# 零残留: 目录 + worktree 注册。超时时 git 被 kill 在半途并**持有 lock**, 只 prune 清不掉 (locked 被跳过),
# 故判据必须两级都查 —— 只查目录会漏掉幽灵注册, 只查注册会漏掉 locked 目录。
residual=""
# 用 if 而非 `[ -d x ] && var=...`: 后者在这行侥幸安全 (set -e 豁免 `&&` 列表中非末条命令的失败,
# 已实测: 条件为假时脚本继续), 但那份豁免很隐晦 —— 一旦把该行挪进函数/子 shell, 或在末尾追加命令,
# 就会变成静默退出。if 无歧义, 不必依赖读者记得这条规则。
if [ -d "$SANDBOX_WT" ]; then residual="目录仍在: $SANDBOX_WT"; fi
if git -C "$ROOT" worktree list | command grep -qF "$SANDBOX_WT"; then
  residual="${residual:+$residual; }worktree 注册仍在"
fi
if [ -n "$residual" ]; then
  bad "熔断后残留 ($residual)"
  SANDBOX_TIMEOUT_S=1 bash "$SCRIPT" rollback "$SESSION" >/dev/null 2>&1 || true
else
  ok "熔断后零残留 (目录 + worktree 注册)"
fi

echo ""
echo "结果: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ]
