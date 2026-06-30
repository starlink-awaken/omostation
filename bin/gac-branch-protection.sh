#!/bin/bash
# gac-branch-protection.sh — main branch protection 设置 (ADR-0106, P2)
#
# 多 agent 并行的平台兜底: 禁 direct push main + Require PR.
# 治本 concurrent-agent-contention (agent 绕不过平台, 被迫走 PR).
#
# 影响 (破坏性, 改全局流程):
#   - 所有 agent (含老王 + 并发) direct push main 被拒
#   - 必须走 PR (gac-worktree.sh claim → submit → merge)
#   - 配合 worktree per session = 多 agent 真并行 (各 worktree 各 PR)
#
# 策略 (过渡):
#   - Require PR (核心隔离) ✅
#   - 禁 direct push ✅
#   - 不强制 Required CI (过渡, 避免 omo 测试红卡 merge; 稳定后加)
#   - 0 required reviews (单人可 merge, 不阻塞)
#
# 用法:
#   gac-branch-protection.sh                # 设置 (交互确认)
#   gac-branch-protection.sh --yes          # 设置 (非交互, agent/CI 用)
#   gac-branch-protection.sh --check        # 查 protection 状态 (解析各项, 可读)
#   gac-branch-protection.sh --remove       # 移除 (紧急回退, 交互)
#   gac-branch-protection.sh --remove --yes # 移除 (非交互)
#
# 落地计划: docs/AGENT-ISOLATION-ROLLOUT.md (Phase 3, 需 Phase 2 eCOS 迁 PR 先行)

set -e

REPO="starlink-awaken/omostation"

# 解析: 第一个位置参数 = 子命令, 其余扫描 --yes
cmd="${1:---set}"
[ $# -gt 0 ] && shift
AUTO_YES=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y) AUTO_YES=true ;;
  esac
done

# 非交互模式 (--yes) 跳过 read, 否则交互确认 (agent/CI 用 --yes)
confirm_action() {
  local prompt="$1"
  if [ "$AUTO_YES" = "true" ]; then
    echo "⚡ 非交互 (--yes): $prompt"
    return 0
  fi
  read -p "$prompt (yes/no): " confirm
  [ "$confirm" = "yes" ] || { echo "取消"; exit 0; }
}

case "$cmd" in
  --check)
    echo "=== $REPO main branch protection 状态 ==="
    resp=$(gh api "repos/$REPO/branches/main/protection" 2>/dev/null) || {
      echo "❌ 未设置 protection (HTTP 404) — main 裸奔, direct push 允许"
      echo "   设置: bash $0 [--yes]"
      exit 0
    }
    echo "$resp" | python3 -c '
import sys, json
d = json.load(sys.stdin)
rpr = d.get("required_pull_request_reviews") or {}
ea = d.get("enforce_admins") or {}
rsc = d.get("required_status_checks") or {}
afp = d.get("allow_force_pushes") or {}
ad = d.get("allow_deletions") or {}
def yn(b): return "YES" if b else "no"
print("  Require PR:            " + yn(bool(rpr)))
if rpr:
    print("    required reviews:   " + str(rpr.get("required_approving_review_count", 0)))
print("  Enforce admins:        " + yn(ea.get("enabled")))
ctxs = ",".join(rsc.get("contexts", [])) if rsc else "none (transition)"
print("  Required status chks:  " + ctxs)
print("  Allow force push:      " + yn(afp.get("enabled")))
print("  Allow deletions:       " + yn(ad.get("enabled")))
'
    ;;

  --remove)
    echo "⚠️  移除 main branch protection (回退到 direct push)"
    confirm_action "确认移除?"
    gh api "repos/$REPO/branches/main/protection" -X DELETE 2>&1 | head -3
    echo "✅ protection 移除 (direct push 恢复)"
    ;;

  --help|-h)
    sed -n '2,30p' "$0"
    ;;

  *)
    echo "⚠️  设置 main branch protection (破坏性, 改全局 push 流程):"
    echo "   - Require PR before merging (禁 direct push main)"
    echo "   - 0 required reviews (单人可 merge)"
    echo "   - 不强制 Required CI (过渡, 避免测试红卡 merge)"
    echo ""
    echo "影响: 所有 agent direct push main 被拒, 必须走 PR."
    echo "      配合 gac-worktree.sh = 多 agent 真并行 (各 worktree 各 PR)."
    echo "      ⚠️  eCOS auto-push (direct push main) 会断! 须先完成 Phase 2 (eCOS 迁 PR)."
    echo ""
    confirm_action "确认设置?"

    # GitHub branch protection API (v3)
    gh api "repos/$REPO/branches/main/protection" -X PUT --input - <<'EOF'
{
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  },
  "enforce_admins": false,
  "required_status_checks": null,
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
    echo ""
    echo "✅ main branch protection 设置完成"
    echo "   验证: bash $0 --check"
    echo "   回退: bash $0 --remove"
    ;;
esac
