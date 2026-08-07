#!/usr/bin/env python3
"""子模块指针漂移检测 (BET-Y1Q2-T1-05).

比对根仓 HEAD gitlink vs 子模块 origin/main HEAD, 检测指针错位.
错位场景: 根仓指针指向 side branch commit, 子模块 main 已前进但根仓未跟进.

用法:
  python3 bin/gac/check-submodule-pointer-drift.py           # 检测
  python3 bin/gac/check-submodule-pointer-drift.py --fix      # 自动对齐 (dry-run)
  python3 bin/gac/check-submodule-pointer-drift.py --fix --apply  # 实际修改 index
  python3 bin/gac/check-submodule-pointer-drift.py --json      # JSON 输出
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def get_submodules() -> list[str]:
    output = _git("config", "--file", ".gitmodules", "--get-regexp", "path")
    return [line.split()[-1] for line in output.splitlines() if line.strip()]


def get_head_gitlink(sub_path: str) -> str | None:
    output = _git("ls-tree", "HEAD", "--", sub_path)
    if not output:
        return None
    parts = output.split()
    if len(parts) >= 3 and parts[0] == "160000":
        return parts[2]
    return None


def get_submodule_origin_main(sub_path: str) -> str | None:
    sub_dir = REPO_ROOT / sub_path
    if not (sub_dir / ".git").exists() and not (sub_dir / ".git").is_file():
        return None
    _git("fetch", "origin", "--quiet", cwd=sub_dir)
    sha = _git("rev-parse", "origin/main", cwd=sub_dir)
    return sha if sha else None


def is_ancestor(commit: str, ancestor: str, sub_path: str) -> bool:
    sub_dir = REPO_ROOT / sub_path
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, ancestor],
        cwd=sub_dir,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def check_drift(sub_path: str) -> dict | None:
    gitlink = get_head_gitlink(sub_path)
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

    return {
        "submodule": sub_path,
        "status": "DIVERGED",
        "gitlink": gitlink[:12],
        "origin_main": origin_main[:12],
        "detail": "gitlink NOT on origin/main — code may be invisible from root",
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
            capture_output=True,
            check=False,
        )
        return f"fixed → {origin_main[:12]}"
    return f"would fix → {origin_main[:12]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="子模块指针漂移检测")
    parser.add_argument("--fix", action="store_true", help="显示修复建议")
    parser.add_argument("--apply", action="store_true", help="实际执行修复")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--strict", action="store_true", help="behind 也算 drift")
    args = parser.parse_args()

    submodules = get_submodules()
    results = []
    diverged = []
    behind = []

    for sub in sorted(submodules):
        r = check_drift(sub)
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
                print(f"  ✅ {sub}: {r['gitlink']}")
            elif status == "behind":
                print(f"  ⚠️  {sub}: {r['gitlink']} ← origin/main {r['origin_main']} ({r.get('detail', '')})")
            elif status == "DIVERGED":
                print(f"  ❌ {sub}: {r['gitlink']} NOT on origin/main {r['origin_main']}")
            elif status == "skip":
                print(f"  ⏭  {sub}: {r.get('reason', 'skipped')}")
            if "fix" in r:
                print(f"      → {r['fix']}")

        print()
        total = len(results)
        aligned = sum(1 for r in results if r["status"] == "aligned")
        print(f"  总计: {total} 子模块 | {aligned} aligned | {len(behind)} behind | {len(diverged)} DIVERGED")

    if diverged:
        print(f"\n  ❌ {len(diverged)} DIVERGED — 根仓指针指向 side branch, 代码可能不可见!")
        if not args.fix and not args.apply:
            print("  运行 --fix 查看修复建议, --fix --apply 执行修复")
        return 1

    if behind and args.strict:
        print(f"\n  ⚠️  {len(behind)} behind (strict mode)")
        return 1

    print("\n  ✅ ALL ALIGNED" if not behind else f"\n  ✅ No divergence ({len(behind)} behind, non-blocking)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
