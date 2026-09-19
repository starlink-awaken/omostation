#!/usr/bin/env python3
"""主工作区提交守卫 — 强制"主工作区只读, 改动走 worktree".

机制 22d 续 (2026-09-18): AGENTS.md § Worktree Policy 早已声明
「主工作区只读，凡改动必 worktree」「Direct commit to main ❌ Prohibited」,
但这条约定**没有执行层** —— 全凭自觉。当天 3 次同类事故即为代价:

  1. 在 agent/governance-agent/t7-08-assisted-routine 上提交 e4787d290,
     并发会话把共享工作区切到 main 后提交孤立 (同日 #3976 "dropped from #3969")
  2. commit 时裹入他人暂存内容 (子模块指针)
  3. 未提交改动被并发分支切换抹掉

根因不是"没快照"而是**此约定无可执行检查**。本脚本补上执行层:

判定 (仅主工作区; worktree 天然隔离, 直接放行):
  1. 非主工作区                        → PASS
  2. GAC_ALLOW_MAIN_WORKSPACE_COMMIT=1 → PASS  (逃生舱, 记入 override 台账)
  3. 主工作区 (任意分支)               → BLOCK

**判据修正 (2026-09-19)** —— 初版只拦"非 main 分支", 实证后改为拦**任意分支**:

  ▸ 非 main 分支: 主工作区被多 agent 共享, HEAD 停在非 main 分支意味着该分支
    随时可能被别人切走 → 提交孤立 (2026-09-18 实证 e4787d290; 同日 #3976
    "dropped from #3969" 是同一事故)。
  ▸ main 分支: 在这里提交会让**本地 main 领先 origin/main**。此后一旦 origin
    前进(任何 PR 合并)即成**双向分叉**, 而 `git merge --ff-only origin/main`
    对分叉态只打印 hint、**不报错也不退出非零** —— 并发会话都以为自己同步了,
    实际停在旧提交上。2026-09-19 实证: 该状态持续近 1 小时无人察觉。

两种模式都是"在共享工作区提交"的直接后果, 故判据收敛为**按位置而非按分支**。

用法:
  python3 bin/gac/check-main-workspace-commit.py [--json] [--branch <b>]

退出码: 0 = 放行; 1 = 拦截
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
ALLOW_ENV = "GAC_ALLOW_MAIN_WORKSPACE_COMMIT"
OVERRIDE_LEDGER = _ROOT / "runtime" / "logs" / "main-workspace-commit-overrides.jsonl"


def _git(*args: str, root: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root or _ROOT), *args],
                          capture_output=True, text=True, check=False)


def is_main_workspace(root: Path | None = None) -> bool:
    """主工作区: git-dir == git-common-dir (worktree 时前者在 .git/worktrees/<n>)."""
    gd = _git("rev-parse", "--git-dir", root=root).stdout.strip()
    gcd = _git("rev-parse", "--git-common-dir", root=root).stdout.strip()
    return bool(gd) and gd == gcd


def current_branch(root: Path | None = None) -> str:
    b = _git("rev-parse", "--abbrev-ref", "HEAD", root=root).stdout.strip()
    return b


def unpushed_count(branch: str, root: Path | None = None) -> int:
    for base in ("origin/main", "main"):
        if _git("rev-parse", "--verify", "--quiet", base, root=root).returncode == 0:
            res = _git("rev-list", "--count", f"{base}..{branch}", root=root)
            if res.returncode == 0 and res.stdout.strip().isdigit():
                return int(res.stdout.strip())
            return 0
    return 0


def divergence(root: Path | None = None) -> dict:
    """本地 main 相对 origin/main 的领先/落后.

    **领先 > 0 是一个全局故障**: 共享工作区的 `git merge --ff-only origin/main`
    会静默拒绝(只打印 hint, 不报错、不退出非零) —— 所有并发会话都以为自己同步了,
    实际停在旧提交上。注意: 仅"领先"(behind=0) 时 ff-only 是合法 no-op 且不报错,
    故**更容易被误读为"已同步"**; 一旦 origin 前进即成双向分叉并开始拒绝。
    2026-09-19 实证: 该状态持续近 1 小时无人察觉。
    """
    for base in ("origin/main",):
        if _git("rev-parse", "--verify", "--quiet", base, root=root).returncode != 0:
            continue
        ahead = _git("rev-list", "--count", f"{base}..main", root=root)
        behind = _git("rev-list", "--count", f"main..{base}", root=root)
        return {"base": base,
                "ahead": int(ahead.stdout.strip()) if ahead.stdout.strip().isdigit() else 0,
                "behind": int(behind.stdout.strip()) if behind.stdout.strip().isdigit() else 0}
    return {"base": None, "ahead": 0, "behind": 0}


def _record_override(branch: str, reason: str, root: Path | None = None) -> None:
    try:
        OVERRIDE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with OVERRIDE_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(UTC).isoformat(),
                "branch": branch,
                "reason": reason,
                "root": str(root or _ROOT),
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 台账失败不影响提交


def evaluate(branch: str | None = None, root: Path | None = None,
             allow_env: str | None = None) -> dict:
    """返回 {verdict: pass|block, reason, branch, main_workspace, unpushed}."""
    root = root or _ROOT
    main_ws = is_main_workspace(root)
    branch = branch or current_branch(root)

    if not main_ws:
        return {"verdict": "pass", "reason": "not_main_workspace",
                "branch": branch, "main_workspace": False, "unpushed": 0,
                "divergence": {"base": None, "ahead": 0, "behind": 0}}

    allow = allow_env if allow_env is not None else os.environ.get(ALLOW_ENV, "")
    if allow == "1":
        _record_override(branch, "env_override", root)
        return {"verdict": "pass", "reason": "env_override",
                "branch": branch, "main_workspace": True,
                "unpushed": unpushed_count(branch, root),
                "divergence": divergence(root)}

    div = divergence(root)
    if branch in ("main", "HEAD", ""):
        # 2026-09-19 修正: 原判据放行 main, 但实证"共享工作区直提 main"同样有害 ——
        # 本地 main 领先 origin/main 后, 所有人的 `merge --ff-only` 静默失效。
        return {"verdict": "block", "reason": "main_workspace_main_branch",
                "branch": branch or "HEAD", "main_workspace": True,
                "unpushed": div["ahead"], "divergence": div}

    return {"verdict": "block", "reason": "main_workspace_non_main_branch",
            "branch": branch, "main_workspace": True,
            "unpushed": unpushed_count(branch, root),
            "divergence": div}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--branch", default=None, help="覆盖分支判定 (测试用)")
    ap.add_argument("--root", default=None, help="覆盖仓库根 (测试用)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else None
    result = evaluate(branch=args.branch, root=root)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    if result["verdict"] == "block":
        b = result["branch"]
        div = result.get("divergence") or {}
        print(f"\n🔴 主工作区提交被拦截 —— 当前分支 `{b}`。\n", file=sys.stderr)
        print("   主工作区被多 agent 共享, 在这里提交会产生两种已实证的故障:\n",
              file=sys.stderr)
        if result["reason"] == "main_workspace_main_branch":
            print("   ▸ 提交 main → **本地 main 领先 origin/main**。此后一旦 origin\n"
                  "     前进(任何 PR 合并)即成**双向分叉**, 而 `git merge --ff-only\n"
                  "     origin/main` 对分叉态只打印 hint **不报错、不退出非零** ——\n"
                  "     并发会话都以为自己同步了, 实际停在旧提交上。\n"
                  "     2026-09-19 实证: 该状态持续近 1 小时无人察觉。\n", file=sys.stderr)
        else:
            print(f"   ▸ 提交非 main 分支 → 该分支随时可能被并发会话切走,\n"
                  f"     提交会因此孤立。2026-09-18 实证: e4787d290 提交被切走后\n"
                  f"     从工作树消失 (同日 #3976 『dropped from #3969』是同一事故)。\n",
                  file=sys.stderr)
        if div.get("ahead"):
            print(f"   当前风险: 本地 main 已领先 {div['base']} {div['ahead']} 个提交"
                  f" —— ff-only 同步正被静默阻塞。\n", file=sys.stderr)
        elif result["unpushed"]:
            print(f"   当前风险: `{b}` 已有 {result['unpushed']} 个未推送提交。\n",
                  file=sys.stderr)
        print("   正确做法: bash bin/gac/gac-worktree.sh claim <session>\n"
              "            然后在该 worktree 里提交 (隔离, 不受并发影响; PR 合并回 main)\n",
              file=sys.stderr)
        print(f"   确需在主工作区提交: {ALLOW_ENV}=1 git commit ..."
              f"\n   (会记入 runtime/logs/main-workspace-commit-overrides.jsonl)\n",
              file=sys.stderr)
        print("   已孤立/分叉提交的处置:\n"
              "     python3 bin/gac/workspace-wip-guard.py list-protected   # 查看钉扎\n"
              "     git log --oneline origin/main..main                     # 查分叉\n",
              file=sys.stderr)
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
