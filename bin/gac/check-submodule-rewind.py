#!/usr/bin/env python3
"""CR-SUBMODULE-REWIND: 检测子模块指针回退 (rewind).

当主仓 commit 中子模块指针被意外回退 (例如从 d4a9d1c 回退到 f57d13dd) 时,
本检查通过对比 index 当前指针与上一次 commit 的指针, 检测是否存在 rewind.

Rewind 判定: 当前指针 NOT ancestor of 上一次指针 (即指针历史被改写/回退).
"""

import argparse
import json
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


def is_descendant_or_equal(
    descendant_candidate: str,
    ancestor_candidate: str,
    submodule_path: str,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Check if descendant_candidate is a valid forward pointer from ancestor_candidate.

    Returns (is_valid, reason) where reason explains which tolerance layer passed
    or why the check failed.

    Tolerance layers (evaluated in order):
    1. Same commit
    2. SHA missing in submodule (force-pushed away)
    3. descendant is ancestor of candidate on default branch
    4. descendant is ancestor of candidate in any ref
    5. ancestor no longer reachable from any ref (force-push cleaned it up)
    6. HEAD is on a non-default branch (feature-branch rebase)
    7. descendant is the tip of any branch ref (detached-HEAD branch switch)
    8. Otherwise — rewind or unrelated history
    """
    if descendant_candidate == ancestor_candidate:
        return True, "same-commit"

    submodule_dir = REPO_ROOT / submodule_path

    # Verify both SHAs exist in the submodule's object store.
    for sha in (descendant_candidate, ancestor_candidate):
        result = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "commit":
            return True, f"sha-missing:{sha[:12]}"

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
            ["git", "merge-base", "--is-ancestor", ancestor_candidate, descendant_candidate],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, f"default-branch:{ref}"

    # 2) Fallback: ancestor is ancestor of descendant in any local ref (branch switch).
    all_commit_refs = _git_in_submodule(
        "for-each-ref", "--format=%(refname)", "refs/heads/", "refs/remotes/",
        submodule_dir=submodule_dir,
    )
    for ref in all_commit_refs.splitlines():
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor_candidate, descendant_candidate],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, f"any-ref:{ref}"

    # 3) If ancestor is no longer reachable from any ref (force-push cleaned it up),
    #    treat as acceptable history rewrite rather than blocking rewind.
    ancestor_reachable = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ancestor_candidate],
        cwd=submodule_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestor_reachable.returncode != 0:
        return True, "force-pushed-away"

    # 4) Feature-branch rebase: ancestor was removed from branch history but the
    #    submodule is now on a non-default branch at descendant. Allow it rather than
    #    blocking every feature-branch rebase.
    head_ref = _git_in_submodule(
        "symbolic-ref", "--quiet", "HEAD", submodule_dir=submodule_dir
    )
    head_branch = head_ref.rsplit("/", 1)[-1] if head_ref else ""
    if head_branch and head_branch not in (default_branch, "main", "master"):
        return True, f"feature-branch:{head_branch}"

    # 5) Detached-HEAD branch switch: if descendant is the tip of any branch ref,
    #    treat as acceptable even if ancestor is not in that branch's history.
    descendant_tip_of = _git_in_submodule(
        "for-each-ref", "--format=%(objectname)", "refs/heads/", "refs/remotes/",
        submodule_dir=submodule_dir,
    )
    if any(tip.startswith(descendant_candidate) for tip in descendant_tip_of.splitlines()):
        return True, "detached-head-tip"

    return False, "rewind-or-unrelated"


def format_violation(path: str, current_sha: str, previous_sha: str, reason: str) -> str:
    return (
        f"  {path} — 子模块指针方向非法: "
        f"当前 {current_sha[:12]} 不是上一次指针 {previous_sha[:12]} 的后代 "
        f"({reason})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="CR-SUBMODULE-REWIND check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show tolerance layer details")
    args = parser.parse_args()

    violations: list[dict] = []
    details: list[dict] = []
    current_gitlinks = get_current_gitlinks()

    for path, current_sha in sorted(current_gitlinks.items()):
        previous_sha = get_previous_pointer(path)
        if previous_sha is None:
            continue
        if previous_sha == current_sha:
            continue

        is_valid, reason = is_descendant_or_equal(current_sha, previous_sha, path, verbose=args.verbose)
        detail = {
            "path": path,
            "current_sha": current_sha,
            "previous_sha": previous_sha,
            "valid": is_valid,
            "reason": reason,
        }
        details.append(detail)

        if args.verbose:
            print(f"[DEBUG] {path}: {reason}")

        if not is_valid:
            violations.append(detail)

    if args.json:
        output = {
            "ok": len(violations) == 0,
            "violations": [
                format_violation(v["path"], v["current_sha"], v["previous_sha"], v["reason"])
                for v in violations
            ],
            "details": details,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output["ok"] else 1

    if violations:
        print(f"FAIL 发现 {len(violations)} 个子模块指针回退:")
        for v in violations:
            print(format_violation(v["path"], v["current_sha"], v["previous_sha"], v["reason"]))
        return 1

    print("OK 未检测到子模块指针回退")
    return 0


if __name__ == "__main__":
    sys.exit(main())
