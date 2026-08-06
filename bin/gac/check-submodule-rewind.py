#!/usr/bin/env python3
"""CR-SUBMODULE-REWIND: 检测子模块指针回退 (rewind).

当主仓 commit 中子模块指针被意外回退 (例如从 d4a9d1c 回退到 f57d13dd) 时,
本检查通过对比 index 当前指针与上一次 commit 的指针, 检测是否存在 rewind.

Rewind 判定: 当前指针 NOT ancestor of 上一次指针 (即指针历史被改写/回退).
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def get_current_gitlinks() -> dict[str, str]:
    """Read current submodule gitlinks from the index.

    Returns {submodule_path: sha1} for each submodule entry in the index.
    """
    output = _git("ls-files", "--stage")
    gitlinks: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        mode, sha1, stage, path = parts[0], parts[1], parts[2], parts[3]
        if mode == "160000" and stage == "0":
            gitlinks[path] = sha1
    return gitlinks


def get_previous_pointer(path: str) -> str | None:
    """Get the submodule pointer from the last commit that touched it."""
    sha = _git("log", "-1", "--format=%H", "--", path)
    return sha if sha else None


def is_descendant_or_equal(child: str, parent: str) -> bool:
    """Check if child is a descendant of (or equal to) parent in git history.
    
    Returns True if parent is an ancestor of child, meaning child advanced forward
    from parent or is the same commit. Returns False if child is unrelated to or
    behind parent (rewind/history rewrite).
    """
    if child == parent:
        return True
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", parent, child],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    violations: list[str] = []
    current_gitlinks = get_current_gitlinks()

    for path, current_sha in sorted(current_gitlinks.items()):
        previous_sha = get_previous_pointer(path)
        if previous_sha is None:
            # No previous commit (e.g., newly added submodule) — skip
            continue
        if previous_sha == current_sha:
            # No change — skip
            continue

        # Direction check: current pointer must be a descendant of (or equal to) previous pointer.
        # This ensures the submodule only moves forward in history, never rewinds.
        if not is_descendant_or_equal(previous_sha, current_sha):
            violations.append(
                f"  {path} — 子模块指针方向非法: "
                f"当前 {current_sha[:12]} 不是上一次指针 {previous_sha[:12]} 的后代 (rewind/history rewrite)"
            )

    if violations:
        print(f"FAIL 发现 {len(violations)} 个子模块指针回退:")
        for v in violations:
            print(v)
        return 1

    print("OK 未检测到子模块指针回退")
    return 0


if __name__ == "__main__":
    sys.exit(main())
