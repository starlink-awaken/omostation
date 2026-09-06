#!/usr/bin/env python3
"""Runtime artifacts gate — 阻止运行时产物进入 git index (staged).

被 hook-runner 以 blocking 引用 (manifest: runtime-artifacts, pre-commit 段).
此前为 placeholder 空壳 (exit 0 零校验); 本实现移植 ci-local-fast.py 的
run_runtime_artifact_gate() 黑名单逻辑 (同源实现, 单一语义):

- git diff --cached --name-only --diff-filter=A 扫描新增暂存文件
- 黑名单后缀 (.sqlite/.db/.pyc/.class 等) / 黑名单文件名 (.DS_Store 等)
  / 黑名单前缀 (.omo/locks/, __pycache__/, node_modules/, dist/ 等)
- 命中任一 → FAIL (exit 1) 并列出违规文件与修复方式
- 无违规 → PASS (exit 0)

用法:
    check-runtime-artifacts.py --staged
"""

import argparse
import os
import subprocess
import sys

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERR = 2

BLACKLIST_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".exe",
}
BLACKLIST_FILENAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
BLACKLIST_PREFIXES = [
    ".omo/locks/", ".omo/_log/", ".omo/_delivery/", "__pycache__/", ".venv/",
    "node_modules/", "dist/", "build/", "target/debug/", "target/release/",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime artifacts gate (staged)")
    parser.add_argument("--staged", action="store_true", help="扫描 git 暂存区新增文件")
    args = parser.parse_args()

    if not args.staged:
        print("[check-runtime-artifacts] ⚠️ 未指定 --staged, 跳过 (hook-runner 总是传入)", file=sys.stderr)
        return EXIT_PASS

    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        print(f"[check-runtime-artifacts] ❌ git diff --cached 失败: {r.stderr.strip()}", file=sys.stderr)
        return EXIT_ERR

    violations = []
    for path in r.stdout.splitlines():
        path = path.strip()
        if not path:
            continue
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

    if violations:
        print(f"❌ {len(violations)} runtime artifact(s) blocked from staging:")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: git rm --cached <file> + add to .gitignore")
        return EXIT_FAIL

    print("✓ runtime artifacts gate: clean")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
