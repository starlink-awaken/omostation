#!/usr/bin/env python3
"""doc-commit-ratio — 观察 doc 类提交占比 (BET-Y1Q3-T6-06 维护模式观察指标).

背景: doc-ssot-lint 已达 0 违规基线 (186 文件), 文档治理进入纯维护模式
(见 .omo/standards/doc-ssot-contract.md §维护模式). 维护模式的目标之一是把
doc 类提交占比从 ~15% 降到 ~8% (done_when #2).

本工具: 仅做观察, 不设门槛不阻断 (维护模式 non_goal: 不新增 lint 规则/门禁).
统计窗口内:
  - 提交总数
  - 含 doc 类文件 (.md 等) 的提交数及其占比
  - doc 类文件变更量占全部变更文件量的比例

口径 (与 bet evidence E2 一致):
  - doc 类 = 提交变更文件中含 .md (markdown) 路径; 另有 --doc-pattern 可扩展
  - 默认窗口 14 天 (对应 bet 的"两周 217 条 doc 提交")

用法:
  python3 bin/ssot/doc-commit-ratio.py                 # 近 14 天
  python3 bin/ssot/doc-commit-ratio.py --days 30
  python3 bin/ssot/doc-commit-ratio.py --json          # 机器可读 JSON

运行位置: 在**主仓 main** 上运行以获得全仓口径 (worktree/功能分支历史会偏差).
git log 统计 `HEAD` 的历史; 建议主仓 cwd 下运行, 或指定 `--since` 之外自行换分支.

退出码:
  0 = 观察成功 (无论占比高低, 本工具不判定通过/失败)
  2 = 参数/运行错误
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone


def _git_log_commits(since_iso: str) -> list[tuple[str, list[str]]]:
    """Return [(commit_hash, [changed_paths...])] in window using git log."""
    cmd = [
        "git",
        "log",
        f"--since={since_iso}",
        "--name-only",
        "--format=%H",
        "HEAD",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    commits: list[tuple[str, list[str]]] = []
    current: str | None = None
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            if current is not None:
                commits.append((current, paths))
            current = line
            paths = []
        else:
            paths.append(line)
    if current is not None:
        commits.append((current, paths))
    return commits


def _is_doc_path(path: str, doc_patterns: tuple[str, ...]) -> bool:
    """doc 类 = 匹配任一 doc 模式 (默认 .md 后缀)."""
    return any(path.endswith(pat) for pat in doc_patterns)


def compute_ratio(
    commits: list[tuple[str, list[str]]],
    doc_patterns: tuple[str, ...],
) -> dict:
    total_commits = len(commits)
    doc_commits = 0
    pure_doc_commits = 0
    total_files = 0
    doc_files = 0
    for _hash, paths in commits:
        has_doc = any(_is_doc_path(p, doc_patterns) for p in paths)
        if has_doc:
            doc_commits += 1
            if all(_is_doc_path(p, doc_patterns) for p in paths):
                pure_doc_commits += 1
        total_files += len(paths)
        doc_files += sum(1 for p in paths if _is_doc_path(p, doc_patterns))
    return {
        "total_commits": total_commits,
        "doc_commits": doc_commits,
        "doc_commit_ratio": round(doc_commits / total_commits, 4) if total_commits else 0.0,
        "pure_doc_commits": pure_doc_commits,
        "pure_doc_commit_ratio": round(pure_doc_commits / total_commits, 4) if total_commits else 0.0,
        "total_files": total_files,
        "doc_files": doc_files,
        "doc_file_ratio": round(doc_files / total_files, 4) if total_files else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="观察 doc 类提交占比 (维护模式观察指标, 不设门槛)")
    parser.add_argument("--days", type=int, default=14, help="观察窗口天数 (默认 14)")
    parser.add_argument(
        "--doc-pattern",
        action="append",
        default=[],
        help="额外的 doc 文件后缀/关键字 (默认含 .md)",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    doc_patterns = tuple({".md", *args.doc_pattern})
    since = (datetime.now(UTC) - timedelta(days=args.days)).isoformat()
    try:
        commits = _git_log_commits(since)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: git log failed: {exc}", file=sys.stderr)
        return 2

    result = compute_ratio(commits, doc_patterns)
    result["days"] = args.days
    result["since"] = since

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"近 {args.days} 天 doc 类提交占比观察 (仅观察, 不判定):")
        print(f"  提交总数: {result['total_commits']}")
        print(f"  含 doc 文件提交: {result['doc_commits']} ({result['doc_commit_ratio']:.1%})")
        print(f"  纯 doc 提交: {result['pure_doc_commits']} ({result['pure_doc_commit_ratio']:.1%})")
        print(f"  文件变更总数: {result['total_files']}")
        print(f"  doc 文件变更: {result['doc_files']} ({result['doc_file_ratio']:.1%})")
        print("提示: 建议在主仓 main 上运行以获得全仓口径 (worktree 分支历史会偏差)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
