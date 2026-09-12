#!/usr/bin/env python3
"""check-diff-lifecycle.py — 检测孤立未应用代码 diff

BET-Y1Q4-T10-145: 扫描 workspace 中的 .patch/.diff 文件，
检测其中包含的 commit 是否已被后续 merge 覆盖。

用法:
  python3 bin/gac/check-diff-lifecycle.py
  python3 bin/gac/check-diff-lifecycle.py --json
  python3 bin/gac/check-diff-lifecycle.py --workspace /path/to/repo
  python3 bin/gac/check-diff-lifecycle.py --base-branch main --head-branch HEAD
  python3 bin/gac/check-diff-lifecycle.py --fail-on-blocking
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def get_workspace() -> Path:
    """获取 workspace 根目录"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("ERROR: 不在 git 仓库中", file=sys.stderr)
        sys.exit(1)


def find_patch_files(workspace: Path, base_commit: str) -> List[Path]:
    """查找 base commit 之后新增的 .patch/.diff 文件"""
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:",
             base_commit + "..HEAD", "*.patch", "*.diff"],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
        files = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and (line.endswith(".patch") or line.endswith(".diff")):
                files.add(line)
        return [workspace / f for f in files]
    except subprocess.CalledProcessError:
        return []


def parse_patch_commits(patch_path: Path) -> List[Dict]:
    """解析 .patch/.diff 文件，提取 commit 信息"""
    commits = []
    try:
        text = patch_path.read_text(errors="replace")
    except (OSError, IOError):
        return commits

    current = None
    for line in text.splitlines():
        if line.startswith("commit "):
            if current:
                commits.append(current)
            current = {
                "sha": line.split()[1],
                "author": "",
                "subject": "",
                "files_modified": [],
            }
        elif current is not None:
            if line.startswith("Author: "):
                current["author"] = line[8:].strip()
            elif line.startswith("Subject: "):
                current["subject"] = line[9:].strip()
            elif line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 3:
                    current["files_modified"].append(parts[2])

    if current:
        commits.append(current)
    return commits


def check_commit_applied(workspace: Path, commit_sha: str) -> bool:
    """检查 commit 是否已在后续历史中"""
    try:
        # Use git branch --contains to check if commit is reachable
        result = subprocess.run(
            ["git", "branch", "--contains", commit_sha],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return False


def check_file_modified(workspace: Path, file_path: str) -> bool:
    """检查文件在 HEAD 中是否被修改过"""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1", "--", file_path],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return False


def run_checks(workspace: Path, base_commit: str, head_ref: str) -> Dict:
    """执行所有检测"""
    patch_files = find_patch_files(workspace, base_commit)
    results = {
        "total_patch_files": len(patch_files),
        "total_commits_in_patches": 0,
        "blocking": [],
        "warnings": [],
        "passed": [],
    }

    for patch_file in patch_files:
        commits = parse_patch_commits(patch_file)
        results["total_commits_in_patches"] += len(commits)

        for commit in commits:
            rel_path = str(patch_file.relative_to(workspace))
            sha = commit["sha"]

            # Check if commit is applied
            is_applied = check_commit_applied(workspace, sha)
            if is_applied:
                results["passed"].append({
                    "patch_file": rel_path,
                    "commit": sha[:12],
                    "subject": commit["subject"][:60],
                    "status": "APPLIED",
                })
                continue

            # Check file-level
            for f in commit.get("files_modified", []):
                if check_file_modified(workspace, f):
                    results["warnings"].append({
                        "patch_file": rel_path,
                        "commit": sha[:12],
                        "subject": commit["subject"][:60],
                        "file": f,
                        "reason": "文件在 HEAD 中已被修改，但 commit 未被应用",
                        "level": "warning",
                    })
                    break
            else:
                # No file modified → blocking
                results["blocking"].append({
                    "patch_file": rel_path,
                    "commit": sha[:12],
                    "subject": commit["subject"][:60],
                    "reason": "patch commit 未被应用，且相关文件在 HEAD 中未被修改",
                    "level": "blocking",
                })

    return results


def print_human_report(results: Dict) -> None:
    """人类可读报告"""
    print("=" * 60)
    print("  Diff Lifecycle Closure Report")
    print("=" * 60)
    print(f"\n  扫描 .patch/.diff 文件: {results['total_patch_files']}")
    print(f"  patch 内 commit 总数:   {results['total_commits_in_patches']}")
    print()

    if not results["blocking"] and not results["warnings"]:
        print("  ✅ 所有 patch commit 均已应用")
        return

    if results["blocking"]:
        print(f"  ❌ BLOCKING: {len(results['blocking'])} 个问题")
        print()
        for item in results["blocking"]:
            print(f"    [{item['patch_file']}]")
            print(f"    commit: {item['commit']} — {item['subject']}")
            print(f"    原因:   {item['reason']}")
            print()

    if results["warnings"]:
        print(f"  ⚠️  WARNINGS: {len(results['warnings'])} 个问题")
        print()
        for item in results["warnings"]:
            print(f"    [{item['patch_file']}]")
            print(f"    commit: {item['commit']} — {item['subject']}")
            print(f"    文件:   {item['file']}")
            print(f"    原因:   {item['reason']}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="检测孤立未应用代码 diff (BET-Y1Q4-T10-145)"
    )
    parser.add_argument("--workspace", type=str, default=None,
                        help="workspace 根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--base-branch", type=str, default="main",
                        help="base 分支 (默认: main)")
    parser.add_argument("--head-branch", type=str, default="HEAD",
                        help="head 分支 (默认: HEAD)")
    parser.add_argument("--fail-on-blocking", action="store_true",
                        help="存在 blocking 时 exit 1")
    args = parser.parse_args()

    workspace = Path(args.workspace) if args.workspace else get_workspace()

    def _resolve_ref(ref: str) -> str:
        """解析 ref；失败时 fallback 到 origin/<ref>（CI PR checkout 场景）。"""
        for candidate in (ref, f"origin/{ref}"):
            try:
                result = subprocess.run(
                    ["git", "rev-parse", candidate],
                    capture_output=True, text=True, check=True, cwd=workspace,
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError:
                continue
        print(f"ERROR: 无法解析 ref '{ref}' (及 origin/{ref})", file=sys.stderr)
        sys.exit(1)

    base_commit = _resolve_ref(args.base_branch)
    head_ref = args.head_branch

    results = run_checks(workspace, base_commit, head_ref)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_human_report(results)

    if args.fail_on_blocking and results["blocking"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
