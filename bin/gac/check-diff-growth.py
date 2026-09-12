#!/usr/bin/env python3
"""check-diff-growth.py — 检测单 PR 的代码膨胀

BET-Y1Q4-T10-147: 计算当前分支相对 base 分支的代码增长量，
超过阈值时标记 warning。

用法:
  python3 bin/gac/check-diff-growth.py
  python3 bin/gac/check-diff-growth.py --json
  python3 bin/gac/check-diff-growth.py --workspace /path/to/repo
  python3 bin/gac/check-diff-growth.py --base-branch main --head-branch HEAD
  python3 bin/gac/check-diff-growth.py --max-lines 1000 --max-files 50
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict


DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_FILES = 100


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


def get_diff_stats(workspace: Path, base_ref: str, head_ref: str) -> Dict:
    """获取 diff 统计"""
    # numstat
    try:
        numstat = subprocess.run(
            ["git", "diff", "--numstat", base_ref + ".." + head_ref],
            capture_output=True, text=True, check=True, cwd=workspace,
        )
    except subprocess.CalledProcessError:
        return {"files_changed": 0, "lines_added": 0, "lines_deleted": 0,
                "net_lines": 0, "by_language": {}, "files": []}

    files = []
    lines_added = 0
    lines_deleted = 0

    for line in numstat.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_str, deleted_str, filepath = parts[0], parts[1], parts[2]
        try:
            added = int(added_str) if added_str != "-" else 0
            deleted = int(deleted_str) if deleted_str != "-" else 0
        except ValueError:
            continue

        # Detect language from extension
        ext = Path(filepath).suffix.lower().lstrip(".")
        lang_map = {
            "py": "Python", "js": "JavaScript", "ts": "TypeScript",
            "jsx": "JSX", "tsx": "TSX", "json": "JSON", "yaml": "YAML",
            "yml": "YAML", "md": "Markdown", "css": "CSS", "html": "HTML",
            "sh": "Shell", "bash": "Shell", "zsh": "Shell", "rb": "Ruby",
            "go": "Go", "rs": "Rust", "java": "Java", "kt": "Kotlin",
            "swift": "Swift", "c": "C", "cpp": "C++", "h": "C/C++",
            "hpp": "C++", "hpp": "C++", "hpp": "C++",
        }
        lang = lang_map.get(ext, "Other") if ext else "Other"

        files.append({
            "path": filepath,
            "lines_added": added,
            "lines_deleted": deleted,
            "net_lines": added - deleted,
            "language": lang,
        })
        lines_added += added
        lines_deleted += deleted

    # Aggregate by language
    by_language = {}
    for f in files:
        lang = f["language"]
        if lang not in by_language:
            by_language[lang] = {"files": 0, "lines_added": 0, "lines_deleted": 0}
        by_language[lang]["files"] += 1
        by_language[lang]["lines_added"] += f["lines_added"]
        by_language[lang]["lines_deleted"] += f["lines_deleted"]

    return {
        "files_changed": len(files),
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "net_lines": lines_added - lines_deleted,
        "by_language": by_language,
        "files": files,
    }


def run_checks(workspace: Path, base_ref: str, head_ref: str,
               max_lines: int, max_files: int) -> Dict:
    """执行所有检测"""
    stats = get_diff_stats(workspace, base_ref, head_ref)

    results = {
        "stats": stats,
        "thresholds": {"max_lines": max_lines, "max_files": max_files},
        "violations": [],
        "passed": [],
    }

    if stats["net_lines"] > max_lines:
        results["violations"].append({
            "metric": "net_lines",
            "value": stats["net_lines"],
            "threshold": max_lines,
            "reason": f"净代码行 {stats['net_lines']} 超过阈值 {max_lines}",
            "level": "warning",
        })
    else:
        results["passed"].append({
            "metric": "net_lines",
            "value": stats["net_lines"],
            "threshold": max_lines,
            "status": "OK",
        })

    if stats["files_changed"] > max_files:
        results["violations"].append({
            "metric": "files_changed",
            "value": stats["files_changed"],
            "threshold": max_files,
            "reason": f"变更文件数 {stats['files_changed']} 超过阈值 {max_files}",
            "level": "warning",
        })
    else:
        results["passed"].append({
            "metric": "files_changed",
            "value": stats["files_changed"],
            "threshold": max_files,
            "status": "OK",
        })

    return results


def print_human_report(results: Dict) -> None:
    """人类可读报告"""
    stats = results["stats"]
    thresholds = results["thresholds"]

    print("=" * 60)
    print("  Diff Growth Detection Report")
    print("=" * 60)
    print()
    print(f"  变更文件数: {stats['files_changed']} (阈值: {thresholds['max_files']})")
    print(f"  新增行数:   {stats['lines_added']}")
    print(f"  删除行数:   {stats['lines_deleted']}")
    print(f"  净增长:     {stats['net_lines']} (阈值: {thresholds['max_lines']})")
    print()

    # By language
    print("  按语言分布:")
    for lang, info in sorted(stats["by_language"].items(),
                              key=lambda x: -x[1]["lines_added"]):
        print(f"    {lang:15s}  {info['files']:3d} files, "
              f"+{info['lines_added']:5d} / -{info['lines_deleted']:5d} lines")
    print()

    if results["violations"]:
        print(f"  ⚠️  膨胀警告: {len(results['violations'])} 项")
        print()
        for v in results["violations"]:
            print(f"    {v['metric']}: {v['value']} (阈值 {v['threshold']})")
            print(f"    原因: {v['reason']}")
            print()
    else:
        print("  ✅ 未超过膨胀阈值")


def main():
    parser = argparse.ArgumentParser(
        description="检测单 PR 的代码膨胀 (BET-Y1Q4-T10-147)"
    )
    parser.add_argument("--workspace", type=str, default=None,
                        help="workspace 根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--base-branch", type=str, default="main",
                        help="base 分支 (默认: main)")
    parser.add_argument("--head-branch", type=str, default="HEAD",
                        help="head 分支 (默认: HEAD)")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES,
                        help=f"最大净增长行数 (默认: {DEFAULT_MAX_LINES})")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES,
                        help=f"最大变更文件数 (默认: {DEFAULT_MAX_FILES})")
    parser.add_argument("--fail-on-violation", action="store_true",
                        help="存在膨胀违规时 exit(1)（CI 门禁）")
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

    results = run_checks(workspace, base_ref, head_ref,
                         args.max_lines, args.max_files)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_human_report(results)

    if args.fail_on_violation and results["violations"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
