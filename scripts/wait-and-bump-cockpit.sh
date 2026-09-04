#!/bin/bash
# scripts/wait-and-bump-cockpit.sh
# 等待 cockpit PR #129 合并,然后 bump 主仓 cockpit 指针完成 HITL 集成

set -euo pipefail

PR_NUMBER=129
EXPECTED_TITLE="feat(cockpit): extend decide commands for HITL proposal awareness"
WORKTREE="/Users/xiamingxing/ws-hitl-proposal-system"
COCKPIT_REMOTE="https://github.com/starlink-awaken/omostation-cockpit.git"

echo "[bump-cockpit] 等待 cockpit PR #${PR_NUMBER} 合并..."

# 轮询检查 PR 状态,每 30s 一次,直到 merged
for i in $(seq 1 60); do
  STATE=$(gh pr view "$PR_NUMBER" --repo "$COCKPIT_REMOTE" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN")
  if [ "$STATE" = "MERGED" ]; then
    echo "[bump-cockpit] PR #${PR_NUMBER} 已合并!"
    break
  fi
  if [ $i -eq 60 ]; then
    echo "[bump-cockpit] 超时: 30 分钟内 PR 未合并"
    exit 1
  fi
  echo "[bump-cockpit] 状态: $STATE, 30s 后重试 ($i/60)..."
  sleep 30
done

# 获取合并后的 cockpit main tip
echo "[bump-cockpit] 获取 cockpit main 最新 commit..."
COCKPIT_NEW_SHA=$(git -C "$WORKTREE/projects/cockpit" fetch origin main 2>&1 >/dev/null && \
                   git -C "$WORKTREE/projects/cockpit" rev-parse origin/main)
echo "[bump-cockpit] cockpit main tip: $COCKPIT_NEW_SHA"

# 在 worktree 中 bump pointer
cd "$WORKTREE"
git -C projects/cockpit checkout "$COCKPIT_NEW_SHA" 2>&1 | tail -2
git add projects/cockpit

# 同步 capability-registry(因为 cockpit 代码变了)
echo "[bump-cockpit] 重新生成 capability-registry..."
make sync-capability-registry 2>&1 | tail -5
git add docs/generated/capability-registry.yaml

# 提交
git commit -m "$(cat <<'EOF'
chore(submodule): bump projects/cockpit to HITL-aware merge commit

Completes BET-Y1Q4-HITL-01 integration after cockpit PR #129 merged.
This bumps the cockpit submodule pointer to the merge commit and
re-syncs capability-registry so the new `hitl-proposal` integration
is registered.

💘 Generated with Crush

Assisted-by: Crush:longcat-2.0
EOF
)"

# Push
echo "[bump-cockpit] 推送到 work/hitl-proposal-system..."
git push origin HEAD:refs/heads/work/hitl-proposal-system 2>&1 | tail -5

echo "[bump-cockpit] ✅ 完成! 等待 PR #3077 review 后合并"
