#!/usr/bin/env python3
"""check-pointer-regression.py — 子模块指针单调性检查.

检测根仓 staged 的子模块 gitlink 变更是否指向更早的 commit (回退).
正常操作: 指针只应前进 (指向更新的 commit).
合法回退: POINTER_REGRESSION_ACK=1 显式确认.

退出码:
  0 = 通过 (无回退 / 已确认)
  1 = 检测到指针回退 (blocking)
  2 = 错误

用法:
  python3 check-pointer-regression.py           # 检查 staged 变更
  python3 check-pointer-regression.py --json    # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def _git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def _is_ancestor(sha_a: str, sha_b: str, cwd: str | None = None) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha_a, sha_b],
        capture_output=True,
        cwd=cwd,
    )
    return result.returncode == 0


def _get_staged_submodule_changes() -> list[dict]:
    diff_out = _git("diff", "--cached", "--raw")
    if not diff_out:
        return []

    changes = []
    for line in diff_out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        meta = parts[0]
        filepath = parts[-1]

        if not meta.startswith(":160000"):
            continue

        old_sha = meta.split()[-2] if len(meta.split()) >= 2 else ""
        new_sha = meta.split()[-1] if len(meta.split()) >= 1 else ""

        staged_line = _git("ls-files", "--stage", "--", filepath)
        if staged_line:
            stage_parts = staged_line.split()
            if len(stage_parts) >= 2 and stage_parts[0] == "160000":
                new_sha = stage_parts[1]

        head_out = _git("ls-tree", "HEAD", "--", filepath)
        if head_out:
            head_parts = head_out.split()
            if len(head_parts) >= 3 and head_parts[0] == "160000":
                old_sha = head_parts[2]

        if old_sha and new_sha and old_sha != new_sha:
            changes.append(
                {
                    "submodule": filepath,
                    "old_sha": old_sha,
                    "new_sha": new_sha,
                }
            )

    return changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submodule pointer monotonicity check"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if os.environ.get("POINTER_REGRESSION_ACK") == "1":
        if args.json:
            print(json.dumps({"skipped": True, "reason": "POINTER_REGRESSION_ACK=1"}))
        return 0

    changes = _get_staged_submodule_changes()
    if not changes:
        if args.json:
            print(json.dumps({"regressions": [], "checked": 0}))
        return 0

    regressions = []
    for change in changes:
        sub = change["submodule"]
        old = change["old_sha"]
        new = change["new_sha"]

        if _is_ancestor(new, old):
            regressions.append(
                {
                    "submodule": sub,
                    "old_sha": old[:12],
                    "new_sha": new[:12],
                    "direction": "regression",
                }
            )

    if args.json:
        print(
            json.dumps(
                {"regressions": regressions, "checked": len(changes)},
                indent=2,
            )
        )

    if regressions:
        for r in regressions:
            print(
                f"[pointer-regression] ❌ {r['submodule']}: "
                f"pointer regression detected",
                file=sys.stderr,
            )
            print(
                f"[pointer-regression]   HEAD:  {r['old_sha']} (current)",
                file=sys.stderr,
            )
            print(
                f"[pointer-regression]   staged: {r['new_sha']} (older!)",
                file=sys.stderr,
            )
            print(
                f"[pointer-regression]   The staged SHA is an ancestor of HEAD — "
                f"this moves the pointer backwards.",
                file=sys.stderr,
            )
        print(
            "[pointer-regression]   Override: POINTER_REGRESSION_ACK=1 git commit ...",
            file=sys.stderr,
        )
        return 1

    if not args.json:
        print(f"[pointer-regression] ✅ {len(changes)} submodule pointer(s) checked, no regression")
    return 0


if __name__ == "__main__":
    sys.exit(main())
