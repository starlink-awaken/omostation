#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
cd ~/ws-mass-deletion-gate || exit 1
git fetch origin main -q

echo "=== main 版 --changed-from 的实现 ==="
git show origin/main:bin/ssot/submodule-reachability-gate.py 2>/dev/null \
  | grep -n -B3 -A12 'changed.from' | head -40

echo
echo "=== 拉下来实跑三种模式 ==="
T=/tmp/mainhat; rm -rf $T; mkdir -p $T
git show origin/main:bin/ssot/submodule-reachability-gate.py > $T/gate.py 2>/dev/null
python3 -c "import ast;ast.parse(open('$T/gate.py').read())" && echo "  语法 OK"
cd ~/Workspace
echo "  --- 无参数 ---"
python3 $T/gate.py 2>&1 | tail -2
echo "  --- --changed-from origin/main ---"
python3 $T/gate.py --changed-from origin/main 2>&1 | tail -2
echo "  --- --changed-from 不存在的基线 ---"
python3 $T/gate.py --changed-from nope-xyz 2>&1 | tail -2

echo
echo "=== main 的 gac-worktree.sh 第 141 行还需不需要修 ==="
cd ~/ws-mass-deletion-gate
git show origin/main:bin/gac/gac-worktree.sh 2>/dev/null | sed -n '138,144p' | sed 's/^/  /'
echo CMIDONE
