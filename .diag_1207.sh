#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
cd ~/ws-mass-deletion-gate || exit 1
git fetch origin main work/fix-gac-worktree-submit -q 2>/dev/null

echo "=== #1207 分支的 commit ==="
git log --oneline origin/main..origin/work/fix-gac-worktree-submit 2>/dev/null | head -5

echo "=== 改了哪些文件 ==="
git diff --stat origin/main...origin/work/fix-gac-worktree-submit 2>/dev/null | tail -6

echo "=== 冲突在哪(试合并) ==="
git merge-tree --write-tree origin/main origin/work/fix-gac-worktree-submit >/dev/null 2>&1
git merge-tree origin/main origin/work/fix-gac-worktree-submit 2>/dev/null | grep -E '^\+<<<|^changed in both|^  (base|our|their)' | head -12

echo "=== main 上这两个文件近期改动 ==="
for f in bin/gac/gac-worktree.sh bin/ssot/submodule-reachability-gate.py; do
  echo "  --- $f ---"
  git log origin/main --oneline -3 -- "$f" 2>/dev/null | sed 's/^/    /'
done

echo "=== main 上 reachability gate 是否已有 --changed-from(可能别人也加了) ==="
git show origin/main:bin/ssot/submodule-reachability-gate.py 2>/dev/null | grep -c 'changed-from' | xargs echo "  出现次数:"
echo "=== main 上 gac-worktree.sh 的 git add 那行 ==="
git show origin/main:bin/gac/gac-worktree.sh 2>/dev/null | grep -n "git add -- ':!.subtrees'" | head -3
echo D1207DONE
