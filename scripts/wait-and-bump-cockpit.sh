#!/bin/bash
# scripts/wait-and-bump-cockpit.sh
# 历史 HITL cockpit bump 助手 — WP1 Wave B2: 发布效果已收敛到 clone-lifecycle integrate
#
#   --validate   只读历史检查 (不 checkout/commit/push/PR)
#   其他模式     立即停止并打印 PUBLICATION_OWNER_REQUIRED

set -euo pipefail

PR_NUMBER=129
EXPECTED_TITLE="feat(cockpit): extend decide commands for HITL proposal awareness"
COCKPIT_REMOTE="https://github.com/starlink-awaken/omostation-cockpit.git"

if [ "${1:-}" = "--validate" ]; then
  echo "[bump-cockpit] validate-only: historical check for cockpit PR #${PR_NUMBER}"
  echo "[bump-cockpit] expected title: ${EXPECTED_TITLE}"
  echo "[bump-cockpit] remote: ${COCKPIT_REMOTE}"
  if command -v gh >/dev/null 2>&1; then
    STATE=$(gh pr view "$PR_NUMBER" --repo "$COCKPIT_REMOTE" --json state,title --jq '"\(.state)|\(.title)"' 2>/dev/null || echo "UNAVAILABLE|")
    echo "[bump-cockpit] pr_state_title: ${STATE}"
  else
    echo "[bump-cockpit] gh unavailable; skipped live PR lookup"
  fi
  echo "[bump-cockpit] validate complete (read-only; no checkout/commit/push/PR)"
  exit 0
fi

echo "PUBLICATION_OWNER_REQUIRED" >&2
echo "[bump-cockpit] mutating modes disabled; use managed clone-lifecycle integrate" >&2
exit 2
