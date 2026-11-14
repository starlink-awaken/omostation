#!/usr/bin/env python3
"""SSOT usage reporter (ADR-0385 B2): 检查 _truth/registry/ 下 SSOT 文件的最近修改时间,
发现可能死掉/不再被消费的 SSOT。

用法:
  python3 bin/ssot/ssot-usage.py                  # 输出过期 SSOT
  python3 bin/ssot/ssot-usage.py --json           # JSON
  python3 bin/ssot/ssot-usage.py --max-age 7d     # 超过 7 天未修改 = 过期
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_DIR = WORKSPACE / ".omo" / "_truth" / "registry"


def _git_root(path: Path) -> Path | None:
    cur = path.resolve().parent
    while True:
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def file_age_days(path: Path) -> float:
    """内容新鲜度 = 该文件**最后一次提交**距今天数。

    2026-11-14: 原实现用文件系统 mtime —— 那量的是「这台机器多久没 checkout」,
    不是「内容多久没更新」。同一个仓实测: **干净 worktree 全部 age=0(stale=0)**,
    而 60 天没动的检出 **56/68 stale** —— 两个读数都不描述内容, 前者是空绿、
    后者是环境性假红。改用 `git log -1 --format=%ct -- <file>`;
    取不到提交时间(未跟踪/无历史/非 git 检出)才退回 mtime。
    """
    import subprocess

    now = datetime.now(UTC).timestamp()
    root = _git_root(path)
    if root is not None:
        try:
            rel = str(path.resolve().relative_to(root))
        except ValueError:
            rel = ""
        if rel:
            proc = subprocess.run(
                ["git", "-C", str(root), "log", "-1", "--format=%ct", "--", rel],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return (now - int(proc.stdout.strip())) / 86400
    return (now - os.path.getmtime(path)) / 86400


def check_sots(max_age_days: float) -> list[dict]:
    findings = []
    for f in sorted(REGISTRY_DIR.glob("*.yaml")):
        age = file_age_days(f)
        stale = age > max_age_days
        findings.append(
            {
                "file": f.name,
                "age_days": round(age, 1),
                "stale": stale,
            }
        )
    findings.sort(key=lambda x: -x["age_days"])
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-age", type=str, default="30d", help="超过 N 天未修改 = stale")
    args = parser.parse_args()

    unit = args.max_age[-1]
    n = int(args.max_age[:-1])
    max_age = n * (1 if unit == "d" else (1 / 24 if unit == "h" else 1))

    findings = check_sots(max_age)
    stale_count = sum(1 for f in findings if f["stale"])

    if args.json:
        print(
            json.dumps(
                {
                    "max_age_days": max_age,
                    "stale_count": stale_count,
                    "files": findings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if stale_count > 0 else 0

    print(f"SSOT usage: {len(findings)} files in {REGISTRY_DIR.name}/")
    if stale_count:
        print(f"\n⚠️  {stale_count} file(s) older than {args.max_age} (可能需审核/删除):")
        for f in findings:
            if f["stale"]:
                print(f"  ⚠️  {f['file']:50} {f['age_days']:.0f}d old")
    else:
        print(f"\n✅ 全部 < {args.max_age}")
    return 1 if stale_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
