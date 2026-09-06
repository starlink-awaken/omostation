#!/usr/bin/env python3
"""运行时产物黑名单闸门 — 阻止运行时产物进入 git index.

与 bin/gac/ci-local-fast.py 的 run_runtime_artifact_gate 同源（同一黑名单语义），
独立化供 pre-commit 阶段的 hook-runner 使用（--staged 只扫本次新增文件）。

判定 (任一命中即 block):
  - 黑名单扩展名: .sqlite/.db/.pyc/.o/.so/.dll 等
  - 黑名单文件名: .DS_Store/Thumbs.db/desktop.ini
  - 黑名单目录前缀: .omo/locks/、.omo/_log/、__pycache__/、.venv/、node_modules/ 等

用法:
  python bin/gac/check-runtime-artifacts.py --staged
  python bin/gac/check-runtime-artifacts.py --staged --json
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

BLACKLIST_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".exe",
}
BLACKLIST_FILENAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
BLACKLIST_PREFIXES = [
    ".omo/locks/", ".omo/_log/", ".omo/_delivery/", "__pycache__/", ".venv/",
    "node_modules/", "dist/", "build/", "target/debug/", "target/release/",
]


def staged_added_files(root: str) -> list[str]:
    """返回 staged 的新增文件 (A) 路径列表."""
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        return []
    return [p.strip() for p in r.stdout.splitlines() if p.strip()]


def check(root: str) -> tuple[list[str], int]:
    """扫描 staged 新增文件, 返回 (violations, rc)."""
    violations = []
    for path in staged_added_files(root):
        basename = os.path.basename(path)
        if basename in BLACKLIST_FILENAMES:
            violations.append(f"{path} (blacklisted filename)")
            continue
        if any(path.endswith(s) for s in BLACKLIST_SUFFIXES):
            violations.append(f"{path} (blacklisted suffix)")
            continue
        if any(path.startswith(p) for p in BLACKLIST_PREFIXES):
            violations.append(f"{path} (blacklisted prefix)")
            continue
    return violations, 1 if violations else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime artifact blacklist gate")
    parser.add_argument("--staged", action="store_true", help="Scan staged added files (default behavior)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if not root:
        print("❌ 不在 git 仓库", file=sys.stderr)
        return 2

    violations, rc = check(root)
    if args.json:
        import json
        print(json.dumps({"ok": rc == 0, "violations": violations, "count": len(violations)}, indent=2))
        return rc

    if violations:
        print(f"❌ {len(violations)} runtime artifact(s) blocked from staging:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print("   请移除运行时产物，只提交源码/配置/文档。", file=sys.stderr)
    else:
        print("✅ runtime-artifacts: clean")
    return rc


if __name__ == "__main__":
    sys.exit(main())
