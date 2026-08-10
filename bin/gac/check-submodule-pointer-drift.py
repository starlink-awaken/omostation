#!/usr/bin/env python3
"""子模块指针漂移检测 (BET-Y1Q2-T1-05).

比对根仓 index/HEAD gitlink vs 子模块 origin/main HEAD, 检测指针错位.
错位场景: 根仓指针指向 side branch commit, 子模块 main 已前进但根仓未跟进.

用法:
  python3 bin/gac/check-submodule-pointer-drift.py           # 检测 (读 index)
  python3 bin/gac/check-submodule-pointer-drift.py --from-head  # 检测 (读 HEAD)
  python3 bin/gac/check-submodule-pointer-drift.py --fix      # 自动对齐 (dry-run)
  python3 bin/gac/check-submodule-pointer-drift.py --fix --apply  # 实际修改 index
  python3 bin/gac/check-submodule-pointer-drift.py --json      # JSON 输出
"""

import argparse
import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _git_local_env_vars() -> frozenset[str]:
    """Return Git variables that must not cross repository boundaries."""
    result = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return frozenset(result.stdout.split())


def _git_env(cwd: Path | None) -> dict[str, str]:
    """Clear superproject-local Git state before entering a submodule.

    Git hooks export GIT_DIR/GIT_WORK_TREE for the superproject. Merely changing
    ``cwd`` is therefore insufficient and makes every submodule command resolve
    against the root worktree.
    """
    env = os.environ.copy()
    if cwd is None or cwd.resolve() == REPO_ROOT.resolve():
        return env
    for name in _git_local_env_vars():
        env.pop(name, None)
    return env


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or REPO_ROOT,
        env=_git_env(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def get_submodules() -> list[str]:
    output = _git("config", "--file", ".gitmodules", "--get-regexp", "path")
    return [line.split()[-1] for line in output.splitlines() if line.strip()]


def get_gitlink(sub_path: str, from_head: bool = False) -> str | None:
    if from_head:
        output = _git("ls-tree", "HEAD", "--", sub_path)
        if not output:
            return None
        parts = output.split()
        if len(parts) >= 3 and parts[0] == "160000":
            return parts[2]
        return None
    output = _git("ls-files", "--stage")
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        mode, sha1, stage, path = parts[0], parts[1], parts[2], parts[3]
        if mode == "160000" and stage == "0" and path == sub_path:
            return sha1
    return None


def get_submodule_origin_main(sub_path: str) -> str | None:
    sub_dir = REPO_ROOT / sub_path
    if not (sub_dir / ".git").exists() and not (sub_dir / ".git").is_file():
        return None
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            cwd=sub_dir,
            env=_git_env(sub_dir),
            capture_output=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        # A stale remote probe must not wedge pre-push; use the last fetched ref.
        pass
    sha = _git("rev-parse", "origin/main", cwd=sub_dir)
    return sha if sha else None


def is_ancestor(commit: str, ancestor: str, sub_path: str) -> bool:
    sub_dir = REPO_ROOT / sub_path
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, ancestor],
        cwd=sub_dir,
        env=_git_env(sub_dir),
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _is_shallow(sub_path: str) -> bool:
    sub_dir = REPO_ROOT / sub_path
    if (sub_dir / ".git").is_file():
        git_dir = (sub_dir / ".git").read_text().split("gitdir: ")[-1].strip()
        shallow = Path(sub_dir) / git_dir / "shallow"
    else:
        shallow = sub_dir / ".git" / "shallow"
    return shallow.exists()


def check_drift(sub_path: str, from_head: bool = False) -> dict | None:
    gitlink = get_gitlink(sub_path, from_head=from_head)
    if not gitlink:
        return None

    origin_main = get_submodule_origin_main(sub_path)
    if not origin_main:
        return {"submodule": sub_path, "status": "skip", "reason": "no origin/main"}

    if gitlink == origin_main:
        return {"submodule": sub_path, "status": "aligned", "gitlink": gitlink[:12]}

    if is_ancestor(gitlink, origin_main, sub_path):
        return {
            "submodule": sub_path,
            "status": "behind",
            "gitlink": gitlink[:12],
            "origin_main": origin_main[:12],
            "detail": "gitlink is ancestor of origin/main (stale but reachable)",
        }

    if is_ancestor(origin_main, gitlink, sub_path):
        return {
            "submodule": sub_path,
            "status": "ahead",
            "gitlink": gitlink[:12],
            "origin_main": origin_main[:12],
            "detail": "gitlink is ahead of origin/main (local has unpushed commits, non-blocking)",
        }

    # shallow clone (CI fetch-depth:1) 无法判断祖先关系 → 两者 is_ancestor 均 False.
    # gitlink 是 checkout 出来的有效 commit (一定存在于本地), 非 bug → 视为 OK (不可判断).
    if _is_shallow(sub_path):
        return {
            "submodule": sub_path,
            "status": "unverifiable",
            "gitlink": gitlink[:12],
            "origin_main": origin_main[:12],
            "detail": "shallow clone (CI fetch-depth:1) — ancestry cannot be verified, non-blocking",
        }

    return {
        "submodule": sub_path,
        "status": "DIVERGED",
        "gitlink": gitlink[:12],
        "origin_main": origin_main[:12],
        "detail": "gitlink NOT on origin/main - code may be invisible from root",
    }


def fix_pointer(sub_path: str, apply: bool = False) -> str:
    sub_dir = REPO_ROOT / sub_path
    origin_main = get_submodule_origin_main(sub_path)
    if not origin_main:
        return "skip: no origin/main"

    if apply:
        _git("update-index", "--cacheinfo", f"160000,{origin_main},{sub_path}")
        subprocess.run(
            ["git", "checkout", "--detach", origin_main],
            cwd=sub_dir,
            env=_git_env(sub_dir),
            capture_output=True,
            check=False,
        )
        return f"fixed -> {origin_main[:12]}"
    return f"would fix -> {origin_main[:12]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="子模块指针漂移检测")
    parser.add_argument("--fix", action="store_true", help="显示修复建议")
    parser.add_argument("--apply", action="store_true", help="实际执行修复")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--strict", action="store_true", help="behind 也算 drift")
    parser.add_argument("--from-head", action="store_true", help="读 HEAD 而非 index")
    args = parser.parse_args()

    submodules = get_submodules()
    results = []
    diverged = []
    behind = []

    for sub in sorted(submodules):
        r = check_drift(sub, from_head=args.from_head)
        if r is None:
            continue
        results.append(r)
        if r["status"] == "DIVERGED":
            diverged.append(r)
        elif r["status"] == "behind":
            behind.append(r)

    if args.fix or args.apply:
        for r in diverged + (behind if args.strict else []):
            fix_msg = fix_pointer(r["submodule"], apply=args.apply)
            r["fix"] = fix_msg

    if args.json:
        print(json.dumps({"results": results, "diverged": len(diverged), "behind": len(behind)}, indent=2))
    else:
        for r in results:
            status = r["status"]
            sub = r["submodule"]
            if status == "aligned":
                print(f"  OK {sub}: {r['gitlink']}")
            elif status == "behind":
                print(f"  WARN {sub}: {r['gitlink']} <- origin/main {r['origin_main']} ({r.get('detail', '')})")
            elif status == "ahead":
                print(f"  OK {sub}: {r['gitlink']} (ahead of origin/main {r['origin_main']}, non-blocking)")
            elif status == "unverifiable":
                print(f"  OK {sub}: {r['gitlink']} (shallow — ancestry unverifiable, non-blocking)")
            elif status == "DIVERGED":
                print(f"  FAIL {sub}: {r['gitlink']} NOT on origin/main {r['origin_main']}")
            elif status == "skip":
                print(f"  SKIP {sub}: {r.get('reason', 'skipped')}")
            if "fix" in r:
                print(f"       -> {r['fix']}")

        print()
        total = len(results)
        aligned = sum(1 for r in results if r["status"] == "aligned")
        ahead_n = sum(1 for r in results if r["status"] == "ahead")
        unverifiable_n = sum(1 for r in results if r["status"] == "unverifiable")
        print(
            f"  Total: {total} submodules | {aligned} aligned | {ahead_n} ahead | "
            f"{unverifiable_n} unverifiable | {len(behind)} behind | {len(diverged)} DIVERGED"
        )

    if diverged:
        if not args.json:
            print(
                f"\n  {len(diverged)} DIVERGED - root pointer targets side branch, "
                "code may be invisible!"
            )
            if not args.fix and not args.apply:
                print("  Run --fix for fix suggestions, --fix --apply to execute")
        return 1

    if behind and args.strict:
        if not args.json:
            print(f"\n  {len(behind)} behind (strict mode)")
        return 1

    if not args.json:
        print(
            "\n  ALL ALIGNED"
            if not behind
            else f"\n  No divergence ({len(behind)} behind, non-blocking)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
