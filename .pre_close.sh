#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
R=starlink-awaken/omostation

echo "########## #1206 分支上的全部 commit ##########"
gh pr view 1206 --repo $R --json commits --jq '.commits[]|"  \(.oid[0:9]) \(.messageHeadline)"' 2>&1 | head -10

echo
echo "########## #1206 的完整 diff 是不是只有 gitlink ##########"
gh pr diff 1206 --repo $R 2>/dev/null | grep '^diff --git' | sed 's/^/  /' | head -15
echo "  --- 非 Subproject 的实际内容改动 ---"
n=$(gh pr diff 1206 --repo $R 2>/dev/null | grep -E '^[+-]' | grep -v '^[+-][+-]' | grep -vE '^[+-]Subproject commit' | wc -l | tr -d ' ')
echo "  行数: $n  (0 = 纯 gitlink bump, 关掉不丢任何代码)"

echo
echo "########## T6-01 的真实工作是不是已在 main ##########"
cd ~/ws-mass-deletion-gate 2>/dev/null && {
  git fetch origin main -q
  git log origin/main --oneline --grep='T6-01' 2>/dev/null | head -5
}

echo
echo "########## #1207 现状 ##########"
gh pr view 1207 --repo $R --json state,mergeable,mergeStateStatus,headRefOid \
  --jq '"  state=\(.state) mergeable=\(.mergeable) mergeState=\(.mergeStateStatus) head=\(.headRefOid[0:9])"' 2>&1
echo "  --- checks ---"
gh pr checks 1207 --repo $R 2>&1 | head -5
echo PCDONE
