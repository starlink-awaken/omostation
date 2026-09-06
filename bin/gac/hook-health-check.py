#!/usr/bin/env python3
"""
Hook 完整性校验 — 检查已安装 hook 的版本、hash、缺失、孤儿.

使用:
  python bin/gac/hook-health-check.py           # 文本输出
  python bin/gac/hook-health-check.py --json    # JSON 输出
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys


def get_file_hash(path: str) -> str:
    """计算文件 sha256."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description="Hook 健康检查")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    canonical_dir = os.path.join(root, ".githooks")
    git_dir = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    target_dir = os.path.join(git_dir, "hooks") if git_dir else os.path.join(root, ".git/hooks")

    canonical_version = ""
    version_path = os.path.join(canonical_dir, "VERSION")
    if os.path.exists(version_path):
        canonical_version = open(version_path).read().strip()

    installed_version = ""
    installed_version_path = os.path.join(target_dir, ".version")
    if os.path.exists(installed_version_path):
        installed_version = open(installed_version_path).read().strip()

    # 计算 canonical hash (与 hook-installer.sh 同算法: find|xargs shasum|shasum)
    canonical_hash_hex = ""
    try:
        find_cmd = (
            f"find {canonical_dir} -type f -not -name '*.md' -not -name '.*' "
            "| sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 | awk '{print $1}'"
        )
        canonical_hash_hex = subprocess.run(
            ["bash", "-c", find_cmd],
            capture_output=True, text=True, check=False,
        ).stdout.strip()[:16]
    except OSError:
        canonical_hash_hex = ""

    installed_hash = ""
    installed_hash_path = os.path.join(target_dir, ".content-hash")
    if os.path.exists(installed_hash_path):
        installed_hash = open(installed_hash_path).read().strip()[:16]

    # canonical 文件清单 (用于逐 hook 状态 + missing/orphaned)
    canonical_files = sorted([
        f for f in os.listdir(canonical_dir)
        if os.path.isfile(os.path.join(canonical_dir, f))
        and not f.endswith(".md") and not f.startswith(".") and f != "VERSION"
    ])

    # 检查每个 hook
    hooks_status = {}
    for name in canonical_files:
        target_path = os.path.join(target_dir, name)
        installed = os.path.exists(target_path)
        target_hash = get_file_hash(target_path) if installed else ""
        source_hash = get_file_hash(os.path.join(canonical_dir, name))
        hooks_status[name.replace("-", "_")] = {
            "installed": installed,
            "hash_match": target_hash == source_hash if installed else False,
            "version_match": installed_version == canonical_version,
            "size": os.path.getsize(target_path) if installed else 0,
        }

    # 查找孤儿 hook (在 target 但不在 canonical)
    orphaned = []
    if os.path.isdir(target_dir):
        for name in os.listdir(target_dir):
            if name.startswith(".") or name.endswith(".sample"):
                continue
            if name not in canonical_files and name not in ("prepare-commit-msg",):
                orphaned.append(name)

    missing = [f for f in canonical_files if not os.path.exists(os.path.join(target_dir, f))]

    result = {
        "version": canonical_version,
        "hash_match": canonical_hash_hex == installed_hash,
        "canonical_hash": canonical_hash_hex,
        "installed_hash": installed_hash,
        "hooks": hooks_status,
        "missing_hooks": missing,
        "orphaned_hooks": orphaned,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Hook Health Check")
    print(f"=================")
    print(f"  Version: {canonical_version} (installed: {installed_version}) {'✅' if installed_version == canonical_version else '⚠️'}")
    print(f" Hash:     {canonical_hash_hex} (installed: {installed_hash}) {'✅' if canonical_hash_hex == installed_hash else '⚠️'}")
    print()
    for name, status in hooks_status.items():
        icon = "✅" if status["installed"] and status["hash_match"] else "❌"
        print(f"  {icon} {name}: {'installed' if status['installed'] else 'MISSING'} ({status['size']} bytes)")
    if missing:
        print(f"\n  Missing: {missing}")
    if orphaned:
        print(f"\n  Orphaned: {orphaned}")

    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
