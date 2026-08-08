#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
cd ~/ws-mass-deletion-gate || exit 1
R=starlink-awaken/omostation

git add bin/gac/gac-worktree.sh bin/ssot/submodule-reachability-gate.py
git commit -F- <<'MSG' 2>&1 | tail -3
fix(gac): submit 静默中断 + reachability gate 基线不可解析时 fail-open

两个都会让守门流程"看起来通过、其实没跑"。

1. gac-worktree.sh submit 静默中断
   `.gitignore` 含 `.subtrees/`, `git add` 撞上被忽略路径返回 1
   (实测 `:!.subtrees` / `:!.subtrees/` / `:(exclude).subtrees/*` 四种写法都是 1)。
   脚本是 `set -euo pipefail`, 于是 submit 在这一行直接退出 ——
   后面的 push 分支 / 开 PR / CI 校验全都没执行, 且不报错。
   非忽略文件其实已暂存成功, 表现为"提交了但没 PR", 很难察觉。
   #1203 就是这样断的, 手动补 push+PR 才完成。

2. reachability gate 基线不可解析时 fail-open
   `changed_submodule_paths` 在 `git diff` 失败时返回 `set()`,
   而空集会命中 `check()` 的 incremental-empty 快速路径 → 直接 ok=True,
   打印 "PASS (0 gitlinks)" 且 rc=0 —— 一个 submodule 都没查却宣称通过。
   pre-push hook 传的正是 `origin/main`, 新克隆 / ref 未 fetch / 拼错时
   都会踩到。改为回退全量并打印提示。

   实测 `--changed-from nope-xyz-123`:
     修前 → PASS (0 gitlinks), rc=0
     修后 → 回退全量, FAIL (18 failures), rc=1  (如实反映本 worktree 状态)
   正常基线仍走增量, 无参数全量行为不变。

注: 本分支不再包含 --changed-from 的实现 —— main 已由 ca0d87740 提供。
MSG

echo "  HEAD: $(git log --oneline -1)"
echo
echo "=== push (新分支, 老分支被别的 worktree 占用) ==="
git push -u origin work/gac-submit-and-failopen 2>&1 | tail -4

echo
echo "=== 关掉旧的 #1207, 开新 PR ==="
gh pr close 1207 --repo $R --comment "以 work/gac-submit-and-failopen 重开 —— 原分支与 main 冲突,且其中的 \`--changed-from\` 实现与 main 的 \`ca0d87740\` 重复(我当时看的主树落后 7 个 commit,没看到已有实现),还夹带了两个不属于本次改动的 \`.omo/\` 文件。新 PR 只保留两个真实修复。" 2>&1 | tail -2
gh pr create --repo $R --base main --head work/gac-submit-and-failopen \
  --title "fix(gac): submit 静默中断 + reachability gate 基线不可解析时 fail-open" \
  --body-file /Users/xiamingxing/Workspace/.b1207.md 2>&1 | tail -3
echo P1207DONE
