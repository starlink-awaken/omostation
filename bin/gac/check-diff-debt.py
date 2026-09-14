#!/usr/bin/env python3
"""check-diff-debt.py — 跟踪代码变更中的历史债务

BET-Y1Q4-T10-146: 扫描当前分支 diff 中新增的 FIXME/HACK/TODO 标记，
检查对应代码在 base 中是否已存在未解决的债务。

用法:
  python3 bin/gac/check-diff-debt.py
  python3 bin/gac/check-diff-debt.py --json
  python3 bin/gac/check-diff-debt.py --workspace /path/to/repo
  python3 bin/gac/check-diff-debt.py --base-branch main --head-branch HEAD
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


DEBT_PATTERN = re.compile(
    r'(FIXME|HACK|TODO|XXX)[\s:]*([^\n]*)',
    re.IGNORECASE,
)

# 排除注释行（Python # 注释）
COMMENT_PREFIXES = ("#", "//", "/*", "*")


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


def get_diff_files(workspace: Path, base_ref: str, head_ref: str) -> List[str]:
    """获取 diff 中新增/修改的文件列表"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref + ".." + head_ref,
             "--diff-filter=AM"],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []


def scan_debt_markers(workspace: Path, file_path: str,
                       base_ref: str, head_ref: str) -> List[Dict]:
    """扫描文件中的债务标记"""
    debt_items = []

    # Get added lines from diff
    try:
        diff_result = subprocess.run(
            ["git", "diff", base_ref + ".." + head_ref, "--", file_path],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
    except subprocess.CalledProcessError:
        return debt_items

    added_lines = {}
    line_num = 0
    for line in diff_result.stdout.splitlines():
        if line.startswith("@@"):
            # Parse hunk header: @@ -start,count +start,count @@
            parts = line.split()
            if len(parts) >= 3:
                try:
                    line_num = int(parts[2].lstrip("+").split(",")[0])
                except ValueError:
                    pass
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            # Check for debt markers (including in comments)
            match = DEBT_PATTERN.search(content)
            if match:
                marker = match.group(1).upper()
                context = match.group(2).strip()
                debt_items.append({
                    "file": file_path,
                    "line": line_num,
                    "marker": marker,
                    "context": context[:100],
                    "level": "warning",
                })
            line_num += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass  # removed line, skip
        else:
            line_num += 1

    return debt_items


def check_debt_in_base(workspace: Path, file_path: str,
                        marker: str, base_ref: str) -> bool:
    """检查该债务标记在 base 中是否已存在"""
    try:
        result = subprocess.run(
            ["git", "grep", "-l", marker, base_ref, "--", file_path],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return False


def run_checks(workspace: Path, base_ref: str, head_ref: str) -> Dict:
    """执行所有检测"""
    files = get_diff_files(workspace, base_ref, head_ref)
    results = {
        "total_files_scanned": len(files),
        "total_debt_markers": 0,
        "existing_debt": [],
        "new_debt": [],
        "passed": [],
    }

    for file_path in files:
        debts = scan_debt_markers(workspace, file_path, base_ref, head_ref)
        results["total_debt_markers"] += len(debts)

        for debt in debts:
            if check_debt_in_base(workspace, file_path,
                                   debt["marker"], base_ref):
                debt["reason"] = "base 中已存在相同债务标记"
                results["existing_debt"].append(debt)
            else:
                debt["reason"] = "新增债务标记，base 中无对应标记"
                results["new_debt"].append(debt)

    return results


def print_human_report(results: Dict) -> None:
    """人类可读报告"""
    print("=" * 60)
    print("  Diff Debt Tracking Report")
    print("=" * 60)
    print(f"\n  扫描文件数: {results['total_files_scanned']}")
    print(f"  债务标记总数: {results['total_debt_markers']}")
    print()

    if not results["existing_debt"] and not results["new_debt"]:
        print("  ✅ 无新增债务标记")
        return

    if results["existing_debt"]:
        print(f"  ⚠️  已有债务: {len(results['existing_debt'])} 处")
        print()
        for item in results["existing_debt"]:
            print(f"    [{item['file']}:{item['line']}]")
            print(f"    标记: {item['marker']} — {item['context']}")
            print(f"    原因: {item['reason']}")
            print()

    if results["new_debt"]:
        print(f"  ⚠️  新增债务: {len(results['new_debt'])} 处")
        print()
        for item in results["new_debt"]:
            print(f"    [{item['file']}:{item['line']}]")
            print(f"    标记: {item['marker']} — {item['context']}")
            print(f"    原因: {item['reason']}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="跟踪代码变更中的历史债务 (BET-Y1Q4-T10-146)"
    )
    parser.add_argument("--workspace", type=str, default=None,
                        help="workspace 根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--base-branch", type=str, default="main",
                        help="base 分支 (默认: main)")
    parser.add_argument("--head-branch", type=str, default="HEAD",
                        help="head 分支 (默认: HEAD)")
    args = parser.parse_args()

    workspace = Path(args.workspace) if args.workspace else get_workspace()

    def _resolve_ref(ref: str) -> str:
        """解析 ref；失败时 fallback 到 origin/<ref>（CI PR checkout 场景）。"""
        for candidate in (ref, f"origin/{ref}"):
            try:
                subprocess.run(
                    ["git", "rev-parse", candidate],
                    capture_output=True, text=True, check=True, cwd=workspace,
                )
                return candidate
            except subprocess.CalledProcessError:
                continue
        print(f"ERROR: 无法解析 ref '{ref}' (及 origin/{ref})", file=sys.stderr)
        sys.exit(1)

    base_ref = _resolve_ref(args.base_branch)
    head_ref = _resolve_ref(args.head_branch)

    results = run_checks(workspace, base_ref, head_ref)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_human_report(results)


if __name__ == "__main__":
    main()
