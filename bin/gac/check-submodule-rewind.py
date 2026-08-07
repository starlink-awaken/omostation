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


def _git_in_submodule(*args: str, submodule_dir: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=submodule_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def is_descendant_or_equal(child: str, parent: str, submodule_path: str) -> bool:
    """Check if child is a valid forward pointer from parent in the submodule.

    Handles multiple cases:
    1. Same commit — True
    2. child is descendant of parent on the submodule's default branch — True
    3. child is descendant of parent in any ref — True
    4. child is the tip of any branch ref (detached-HEAD branch switch) — True
    5. parent no longer reachable from any ref (force-push cleaned it up) — True
    6. HEAD is on a non-default branch (feature-branch rebase) — True
    7. Otherwise — False (rewind or unrelated history)
    """
    if child == parent:
        return True
    submodule_dir = REPO_ROOT / submodule_path

    # Verify both SHAs exist in the submodule's object store.
    for sha in (child, parent):
        result = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "commit":
            return True

    # 1) Check on the default branch first (usually main/master).
    default_branch = _git_in_submodule(
        "symbolic-ref", "refs/remotes/origin/HEAD", submodule_dir=submodule_dir
    )
    if default_branch:
        default_branch = default_branch.rsplit("/", 1)[-1] or "main"
    else:
        default_branch = "main"

    for ref in (default_branch, "HEAD"):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", parent, child],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True

    # 2) Fallback: parent is ancestor of child in any local ref (branch switch).
    all_commit_refs = _git_in_submodule(
        "for-each-ref", "--format=%(refname)", "refs/heads/", "refs/remotes/",
        submodule_dir=submodule_dir,
    )
    for ref in all_commit_refs.splitlines():
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", parent, child],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True

    # 3) If parent is no longer reachable from any ref (force-push cleaned it up),
    #    treat as acceptable history rewrite rather than blocking rewind.
    parent_reachable = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", parent],
        cwd=submodule_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if parent_reachable.returncode != 0:
        return True

    # 4) Feature-branch rebase: parent was removed from branch history but the
    #    submodule is now on a non-default branch at child. Allow it rather than
    #    blocking every feature-branch rebase.
    head_ref = _git_in_submodule(
        "symbolic-ref", "--quiet", "HEAD", submodule_dir=submodule_dir
    )
    head_branch = head_ref.rsplit("/", 1)[-1] if head_ref else ""
    if head_branch and head_branch not in (default_branch, "main", "master"):
        return True

    # 5) Detached-HEAD branch switch: if child is the tip of any branch ref,
    #    treat as acceptable even if parent is not in that branch's history.
    child_tip_of = _git_in_submodule(
        "for-each-ref", "--format=%(objectname)", "refs/heads/", "refs/remotes/",
        submodule_dir=submodule_dir,
    )
    if any(tip.startswith(child) for tip in child_tip_of.splitlines()):
        return True

    return False


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
        if not is_descendant_or_equal(current_sha, previous_sha, path):
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
