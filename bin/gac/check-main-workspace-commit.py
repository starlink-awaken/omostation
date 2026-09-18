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
  2. 当前分支 == main                  → PASS  (main 上提交不产生"分支被切走"孤立)
  3. GAC_ALLOW_MAIN_WORKSPACE_COMMIT=1 → PASS  (逃生舱, 记入 override 台账)
  4. 其他分支                          → BLOCK

为什么按"分支 != main"判据: 主工作区被多 agent 共享, HEAD 停在非 main 分支
意味着**该分支随时可能被别人切走** —— 这正是孤立事故的触发条件。这与
`workspace-wip-guard.py status` 的 branch_anomaly 信号同源同判据。

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
                "branch": branch, "main_workspace": False, "unpushed": 0}
    if branch in ("main", "HEAD", ""):
        return {"verdict": "pass", "reason": "on_main_or_detached",
                "branch": branch, "main_workspace": True, "unpushed": 0}

    allow = allow_env if allow_env is not None else os.environ.get(ALLOW_ENV, "")
    if allow == "1":
        _record_override(branch, "env_override", root)
        return {"verdict": "pass", "reason": "env_override",
                "branch": branch, "main_workspace": True,
                "unpushed": unpushed_count(branch, root)}

    return {"verdict": "block", "reason": "main_workspace_non_main_branch",
            "branch": branch, "main_workspace": True,
            "unpushed": unpushed_count(branch, root)}


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
        print(f"\n🔴 主工作区提交被拦截 —— 当前分支 `{b}` 不是 main。\n", file=sys.stderr)
        print("   为什么: 主工作区被多 agent 共享, HEAD 停在非 main 分支意味着该分支"
              "随时可能\n   被并发会话切走 —— 提交会因此孤立 (2026-09-18 实证: "
              "e4787d290 提交被\n   切走后从工作树消失, 同日 #3976 『dropped from "
              "#3969』是同一事故)。\n", file=sys.stderr)
        if result["unpushed"]:
            print(f"   当前风险: 该分支已有 {result['unpushed']} 个未推送提交。\n",
                  file=sys.stderr)
        print("   正确做法: bash bin/gac/gac-worktree.sh claim <session>\n"
              "            然后在该 worktree 里提交 (隔离, 不受并发影响)\n", file=sys.stderr)
        print(f"   确需在主工作区提交: {ALLOW_ENV}=1 git commit ..."
              f"\n   (会记入 runtime/logs/main-workspace-commit-overrides.jsonl)\n",
              file=sys.stderr)
        print("   恢复已孤立的提交: python3 bin/gac/workspace-wip-guard.py "
              "list-protected\n", file=sys.stderr)
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
