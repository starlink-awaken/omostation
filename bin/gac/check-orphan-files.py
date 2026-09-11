#!/usr/bin/env python3
"""check-orphan-files.py — 检测孤立文件

BET-Y1Q4-T10-148 (repo hygiene): 检测 .omo/ 和 bin/ 中未被任何文档
或配置文件引用的文件，标记 warning。

用法:
  python3 bin/gac/check-orphan-files.py
  python3 bin/gac/check-orphan-files.py --json
  python3 bin/gac/check-orphan-files.py --workspace /path/to/repo
  python3 bin/gac/check-orphan-files.py --dirs .omo bin
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set


DEFAULT_SCAN_DIRS = [".omo", "bin"]
# 文件扩展名白名单（扫描这些类型的文件）
SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".md", ".txt",
                   ".sh", ".bash", ".zsh", ".toml", ".cfg", ".ini"}
# 引用检测的文件扩展名
REF_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".md", ".txt",
                  ".sh", ".bash", ".zsh", ".toml", ".cfg", ".ini"}


def get_workspace() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("ERROR: 不在 git 仓库中", file=sys.stderr)
        sys.exit(1)


def scan_files(workspace: Path, dirs: List[str]) -> List[str]:
    """扫描指定目录下的文件"""
    files = []
    for d in dirs:
        dir_path = workspace / d
        if not dir_path.exists():
            continue
        for root, _dirs, fnames in os.walk(dir_path):
            for fname in fnames:
                if Path(fname).suffix in SCAN_EXTENSIONS:
                    rel = str(Path(root, fname).relative_to(workspace))
                    files.append(rel)
    return sorted(files)


def find_references(workspace: Path, file_path: str) -> List[str]:
    """查找引用该文件的路径"""
    refs = []

    # Extract filename and basename (without extension) for matching
    filename = Path(file_path).name
    basename = Path(file_path).stem
    # Also check relative path without leading directory
    rel_path = file_path
    rel_no_dir = rel_path.replace("/", "/")  # keep as-is

    # Build search patterns
    patterns = []
    if filename != basename:
        patterns.append(filename)
    patterns.append(basename)

    # Use git grep for efficiency
    for pattern in patterns:
        try:
            result = subprocess.run(
                ["git", "grep", "-l", pattern, "--"],
                capture_output=True, text=True, check=True, cwd=workspace,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line != file_path:
                    refs.append(line)
        except subprocess.CalledProcessError:
            continue

    return sorted(set(refs))


def check_file_referenced(workspace: Path, file_path: str) -> bool:
    """检查文件是否被引用"""
    refs = find_references(workspace, file_path)
    return len(refs) > 0


def run_checks(workspace: Path, dirs: List[str]) -> Dict:
    """执行所有检测"""
    files = scan_files(workspace, dirs)
    orphaned = []
    referenced = 0

    for f in files:
        if check_file_referenced(workspace, f):
            referenced += 1
        else:
            orphaned.append({
                "path": f,
                "level": "warning",
            })

    return {
        "total_files": len(files),
        "referenced": referenced,
        "orphaned_count": len(orphaned),
        "orphaned_files": orphaned,
    }


def print_human_report(results: Dict) -> None:
    """人类可读报告"""
    print("=" * 60)
    print("  Orphan Files Report")
    print("=" * 60)
    print(f"\n  扫描文件数: {results['total_files']}")
    print(f"  被引用文件: {results['referenced']}")
    print(f"  孤立文件:   {results['orphaned_count']}")
    print()

    if results["orphaned_files"]:
        print(f"  ⚠️  孤立文件 (未被引用):")
        for item in results["orphaned_files"]:
            print(f"    {item['path']}")
        print()
        print("  建议: 检查是否可归档或删除")
    else:
        print("  ✅ 无孤立文件")


def main():
    parser = argparse.ArgumentParser(
        description="检测孤立文件"
    )
    parser.add_argument("--workspace", type=str, default=None,
                        help="workspace 根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--dirs", nargs="+", default=DEFAULT_SCAN_DIRS,
                        help=f"扫描目录 (默认: {' '.join(DEFAULT_SCAN_DIRS)})")
    args = parser.parse_args()

    workspace = Path(args.workspace) if args.workspace else get_workspace()
    results = run_checks(workspace, args.dirs)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_human_report(results)


if __name__ == "__main__":
    main()
