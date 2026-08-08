#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
cd ~/ws-mass-deletion-gate || exit 1
git fetch origin main -q
git checkout -q -B work/gac-submit-and-failopen origin/main 2>&1 | tail -1
echo "  基线: $(git log --oneline -1)"
echo
echo "=== 当前 main 上 gac-worktree.sh 的 git add 段(带上下文) ==="
grep -n -B4 -A2 "git add -- ':!.subtrees'" bin/gac/gac-worktree.sh | head -20
echo
echo "=== 出现次数 ==="
grep -c "git add -- ':!.subtrees'" bin/gac/gac-worktree.sh
echo "=== 是否已有 || true ==="
grep -c "git add -- ':!.subtrees' \. || true" bin/gac/gac-worktree.sh
echo RB2DONE
