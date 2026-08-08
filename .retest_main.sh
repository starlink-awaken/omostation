#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
cd ~/ws-mass-deletion-gate || exit 1
git fetch origin main -q
git checkout -q main 2>/dev/null || git checkout -q -B main origin/main 2>/dev/null
git reset -q --hard origin/main 2>/dev/null
G=bin/ssot/submodule-reachability-gate.py
echo "  用位置: $(pwd)/$G"
echo "  WORKSPACE 会被解析为: $(python3 -c "import pathlib;print(pathlib.Path('$PWD/$G').resolve().parents[2])")"

echo
echo "=== main 版 changed_submodule_paths 实现 ==="
grep -n -A18 'def changed_submodule_paths' "$G" | head -24

echo
echo "=== 三种模式实跑(正确位置) ==="
echo "  --- 无参数 ---"; python3 "$G" 2>&1 | tail -2
echo "  --- --changed-from origin/main ---"; python3 "$G" --changed-from origin/main 2>&1 | tail -2
echo "  --- --changed-from 不可解析基线 ---"; python3 "$G" --changed-from nope-xyz-123 2>&1 | tail -3
echo "     rc=$(python3 "$G" --changed-from nope-xyz-123 >/dev/null 2>&1; echo $?)"
echo RMDONE
