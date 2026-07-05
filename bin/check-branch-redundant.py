#!/usr/bin/env python3
"""Check redundant work/* branches against main (git cherry based).

P74 solidification (常态化治理). 工具化 redundant 检测, 避免手工 cherry 评估.
三层验证纪律落地: redundant 判据用 git cherry (patch-level), 不用 grep (word-level, 假阴性).

Usage:
  python3 bin/check-branch-redundant.py            # 全量扫 (人读)
  python3 bin/check-branch-redundant.py --json     # JSON 输出 (agent/cron 用)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent


def run(cmd, cwd=WORKSPACE):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def list_work_branches():
    r = run(["git", "branch", "-r"])
    if r.returncode != 0:
        return []
    return [
        line.strip().replace("origin/work/", "")
        for line in r.stdout.splitlines()
        if "origin/work/" in line and line.strip()
    ]


def cherry_count(branch):
    """git cherry origin/main origin/work/<branch>: + unique / - dup (patch-level)."""
    r = run(["git", "cherry", "origin/main", f"origin/work/{branch}"])
    unique = sum(1 for line in r.stdout.splitlines() if line.startswith("+"))
    dup = sum(1 for line in r.stdout.splitlines() if line.startswith("-"))
    return unique, dup


def assess():
    results = []
    for br in list_work_branches():
        unique, dup = cherry_count(br)
        last = run(["git", "log", "-1", "--format=%cs", f"origin/work/{br}"]).stdout.strip()
        ahead_out = run(["git", "rev-list", "--count", f"origin/main..origin/work/{br}"]).stdout.strip()
        results.append({
            "branch": br,
            "unique": unique,
            "dup": dup,
            "ahead": int(ahead_out) if ahead_out.isdigit() else 0,
            "last": last,
            "verdict": "redundant" if unique == 0 else "unique",
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Check redundant work/* branches vs main")
    parser.add_argument("--json", action="store_true", help="JSON output for agent/cron")
    args = parser.parse_args()

    results = assess()
    if args.json:
        print(json.dumps({"branches": results, "total": len(results),
                          "redundant": sum(1 for r in results if r["verdict"] == "redundant"),
                          "unique": sum(1 for r in results if r["verdict"] == "unique")}, indent=2))
        return 0

    if not results:
        print("✅ 无 work/* 分支")
        return 0

    redundant = [r for r in results if r["verdict"] == "redundant"]
    unique = [r for r in results if r["verdict"] == "unique"]

    print(f"=== work/* 分支审计 (vs origin/main, git cherry patch-level) ===")
    print(f"总计 {len(results)} 个: {len(unique)} unique, {len(redundant)} redundant\n")

    if redundant:
        print(f"🔴 redundant ({len(redundant)}, 可删, 验证后 git push origin --delete):")
        for r in redundant:
            print(f"  work/{r['branch']}: 0 unique/{r['ahead']} ahead, last={r['last']}")

    if unique:
        print(f"\n🟢 unique ({len(unique)}, 待评估合并, cherry-pick 验证价值):")
        for r in unique:
            print(f"  work/{r['branch']}: {r['unique']} unique/{r['ahead']} ahead, last={r['last']}")

    print(f"\n💡 redundant 判据: git cherry (patch-level) > grep (word-level, 假阴性)")
    print(f"   删 redundant: git push origin --delete work/<branch> --no-verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
