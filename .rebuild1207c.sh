#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
cd ~/ws-mass-deletion-gate || exit 1

python3 - <<'PY'
import pathlib
wt = pathlib.Path.home()/"ws-mass-deletion-gate"

# --- 修 1: gac-worktree.sh submit 静默中断 ---
f = wt/"bin/gac/gac-worktree.sh"
t = f.read_text()
old = "      git add -- ':!.subtrees' .\n"
assert t.count(old) == 1, f"锚点出现 {t.count(old)} 次"
new = ("      # .gitignore 含 .subtrees/ → git add 撞上被忽略路径会返回 1\n"
       "      # (实测 ':!.subtrees' / ':!.subtrees/' / ':(exclude).subtrees/*' 都是 1),\n"
       "      # 但非忽略文件其实已暂存成功。set -euo pipefail 下必须吞掉这个返回码,\n"
       "      # 否则 submit 在此静默中断 —— 后面的 push / 开 PR / CI 校验一个都不执行。\n"
       "      git add -- ':!.subtrees' . || true\n")
f.write_text(t.replace(old, new, 1))
print("  ✅ 修 1: gac-worktree.sh")

# --- 修 2: reachability gate fail-open ---
f = wt/"bin/ssot/submodule-reachability-gate.py"
t = f.read_text()
old2 = '''    result = run(["git", "diff", "--name-only", base, "HEAD", "--", ".gitmodules", "projects/*"])
    if result.returncode != 0:
        return set()'''
assert old2 in t, "gate 锚点未匹配"
new2 = '''    # 基线不可解析 (拼错 / ref 未 fetch / 新克隆还没有 origin/main) 时必须回退全量。
    # 原实现返回 set(), 而空集会命中 check() 的 incremental-empty 快速路径
    # → 直接 ok=True, 报 "PASS (0 gitlinks)" 且 rc=0 —— 守门员一个都没查却宣称通过。
    # pre-push hook 传的正是 origin/main, 新克隆里它可能尚不存在。
    if run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]).returncode != 0:
        sys.stderr.write(f"[reachability] 基线 {base} 不可解析, 回退全量检查\\n")
        return set(submodule_paths())
    result = run(["git", "diff", "--name-only", base, "HEAD", "--", ".gitmodules", "projects/*"])
    if result.returncode != 0:
        sys.stderr.write(f"[reachability] git diff 相对 {base} 失败, 回退全量检查\\n")
        return set(submodule_paths())'''
f.write_text(t.replace(old2, new2, 1))
print("  ✅ 修 2: gate fail-open")
PY

echo
echo "=== 语法 ==="
bash -n bin/gac/gac-worktree.sh && echo "  gac-worktree.sh OK"
python3 -c "import ast;ast.parse(open('bin/ssot/submodule-reachability-gate.py').read())" && echo "  gate OK"

echo
echo "=== 验证修 2 (关键) ==="
G=bin/ssot/submodule-reachability-gate.py
echo "  --- 不可解析基线 ---"
python3 "$G" --changed-from nope-xyz-123 2>&1 | tail -3
python3 "$G" --changed-from nope-xyz-123 >/dev/null 2>&1; echo "     rc=$? (修前恒为 0 且 0 gitlinks; 现应回退全量)"
echo "  --- 正常基线仍走增量 ---"
python3 "$G" --changed-from origin/main 2>&1 | tail -2
python3 "$G" --changed-from origin/main >/dev/null 2>&1; echo "     rc=$?"
echo "  --- 无参数(全量, 行为不变) ---"
python3 "$G" 2>&1 | tail -1

echo
echo "=== 只改了两个文件 ==="
git status --short
echo RB3DONE
