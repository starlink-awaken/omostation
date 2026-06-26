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
#   gac-branch-protection.sh           # 设置 (交互确认)
#   gac-branch-protection.sh --check   # 查当前 protection 状态
#   gac-branch-protection.sh --remove  # 移除 protection (紧急回退)

set -e

REPO="starlink-awaken/omostation"

cmd="${1:---set}"

case "$cmd" in
  --check)
    echo "=== $REPO main branch protection 状态 ==="
    gh api "repos/$REPO/branches/main/protection" 2>&1 | head -20 \
      || echo "(未设置 protection)"
    ;;

  --remove)
    echo "⚠️  移除 main branch protection (回退到 direct push)"
    read -p "确认移除? (yes/no): " confirm
    [ "$confirm" != "yes" ] && echo "取消" && exit 0
    gh api "repos/$REPO/branches/main/protection" -X DELETE 2>&1 | head -3
    echo "✅ protection 移除 (direct push 恢复)"
    ;;

  *)
    echo "⚠️  设置 main branch protection (破坏性, 改全局 push 流程):"
    echo "   - Require PR before merging (禁 direct push main)"
    echo "   - 0 required reviews (单人可 merge)"
    echo "   - 不强制 Required CI (过渡, 避免测试红卡 merge)"
    echo ""
    echo "影响: 所有 agent direct push main 被拒, 必须走 PR."
    echo "      配合 gac-worktree.sh = 多 agent 真并行 (各 worktree 各 PR)."
    echo ""
    read -p "确认设置? (yes/no): " confirm
    [ "$confirm" != "yes" ] && echo "取消" && exit 0

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
