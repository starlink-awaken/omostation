#!/usr/bin/env python3
"""check-bulk-deletion.py — 大批量删除门禁.

三种模式:
  (无参数)     检查当前 staged 的删除比例 (pre-commit 用)
  --submodules 检查所有子模块最近 commit 的删除比例 (pre-push 兜底)
  --scan-recent N  扫描所有子模块最近 N 个 commit (daemon/cron 用)

双指标 AND 逻辑:
  - staged 删除文件数 / repo 总文件数 >= 50%
  - staged 删除行数 >= 1000
  两者同时满足才阻断.

逃逸:
  BULK_DELETE_ACK=1  跳过检查 (显式确认)

路径白名单:
  以下路径的删除不计入统计: vendor/, node_modules/, dist/, build/,
  __pycache__/, *.pyc, .pyc, .egg-info/, .mypy_cache/, .ruff_cache/,
  .pytest_cache/, uv.lock, package-lock.json, yarn.lock, poetry.lock

退出码:
  0 = 通过 (或无异常)
  1 = 检测到异常删除 (blocking)
  2 = 错误
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DELETE_FILE_RATIO_THRESHOLD = 0.50
DELETE_LINE_THRESHOLD = 1000

WHITELIST_PREFIXES = (
    "vendor/",
    "node_modules/",
    "dist/",
    "build/",
    "__pycache__/",
    ".egg-info/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    ".tox/",
    ".venv/",
    "venv/",
    ".codebase-memory/",
    "runtime/",
)

WHITELIST_SUFFIXES = (
    ".pyc",
    ".pyo",
)

WHITELIST_EXACT = (
    "uv.lock",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
)


def _is_whitelisted(path: str) -> bool:
    for prefix in WHITELIST_PREFIXES:
        if path.startswith(prefix) or f"/{prefix}" in path:
            return True
    for suffix in WHITELIST_SUFFIXES:
        if path.endswith(suffix):
            return True
    basename = path.rsplit("/", 1)[-1]
    if basename in WHITELIST_EXACT:
        return True
    return False


def _git(*args: str, cwd: str | None = None) -> str:
    cmd = ["git"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def _count_files(repo_dir: str | None = None) -> int:
    out = _git("ls-files", cwd=repo_dir)
    if not out:
        return 0
    return len(out.splitlines())


def _check_staged(repo_dir: str | None = None) -> dict:
    diff_out = _git("diff", "--cached", "--numstat", cwd=repo_dir)
    if not diff_out:
        return {
            "deleted_files": 0,
            "deleted_lines": 0,
            "total_files": _count_files(repo_dir),
            "ratio": 0.0,
            "blocked": False,
            "details": [],
        }

    total_files = _count_files(repo_dir)
    deleted_files = 0
    deleted_lines = 0
    details = []

    for line in diff_out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_s, removed_s, filepath = parts
        if added_s == "-" or removed_s == "-":
            continue
        removed = int(removed_s)
        if removed == 0:
            continue
        if _is_whitelisted(filepath):
            continue
        deleted_files += 1
        deleted_lines += removed
        details.append({"file": filepath, "lines": removed})

    ratio = deleted_files / total_files if total_files > 0 else 0.0
    blocked = (
        ratio >= DELETE_FILE_RATIO_THRESHOLD
        and deleted_lines >= DELETE_LINE_THRESHOLD
    )

    return {
        "deleted_files": deleted_files,
        "deleted_lines": deleted_lines,
        "total_files": total_files,
        "ratio": round(ratio, 4),
        "blocked": blocked,
        "details": details[:20],
    }


def _check_submodule_recent_commits(
    workspace_root: str, n_commits: int = 1
) -> list[dict]:
    gitmodules = Path(workspace_root) / ".gitmodules"
    if not gitmodules.exists():
        return []

    results = []
    content = gitmodules.read_text()
    sub_path = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("path = "):
            sub_path = line.split("=", 1)[1].strip()
        elif line.startswith("[submodule") and sub_path:
            _scan_one_submodule(workspace_root, sub_path, n_commits, results)
            sub_path = None
    if sub_path:
        _scan_one_submodule(workspace_root, sub_path, n_commits, results)

    return results


def _scan_one_submodule(
    workspace_root: str, sub_path: str, n_commits: int, results: list[dict]
) -> None:
    full_path = Path(workspace_root) / sub_path
    if not (full_path / ".git").exists() and not (full_path / ".git").is_file():
        return

    log_out = _git(
        "log", f"--max-count={n_commits}", "--format=%H", cwd=str(full_path)
    )
    if not log_out:
        return

    for sha in log_out.splitlines():
        sha = sha.strip()
        if not sha:
            continue
        stat_out = _git(
            "diff", "--numstat", f"{sha}^", sha, cwd=str(full_path)
        )
        if not stat_out:
            continue

        ls_out = _git("ls-files", cwd=str(full_path))
        total_files_in_sub = len(ls_out.splitlines()) if ls_out else 0
        if total_files_in_sub == 0:
            total_files_in_sub = 1

        del_files = 0
        del_lines = 0
        del_details = []
        for line in stat_out.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added_s, removed_s, filepath = parts
            if added_s == "-" or removed_s == "-":
                continue
            removed = int(removed_s)
            if removed == 0:
                continue
            if _is_whitelisted(filepath):
                continue
            del_files += 1
            del_lines += removed
            del_details.append({"file": filepath, "lines": removed})

        ratio = del_files / total_files_in_sub
        blocked = (
            ratio >= DELETE_FILE_RATIO_THRESHOLD
            and del_lines >= DELETE_LINE_THRESHOLD
        )
        if blocked:
            results.append(
                {
                    "submodule": sub_path,
                    "commit": sha[:12],
                    "deleted_files": del_files,
                    "deleted_lines": del_lines,
                    "total_files": total_files_in_sub,
                    "ratio": round(ratio, 4),
                    "blocked": True,
                    "details": del_details[:10],
                }
            )


def _write_alert(workspace_root: str, entry: dict) -> None:
    from datetime import UTC, datetime

    alerts_path = Path(workspace_root) / ".omo" / "state" / "alerts.jsonl"
    alerts_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "source": "check-bulk-deletion",
        "severity": "critical",
        "message": (
            f"BULK DELETION detected in {entry['submodule']} "
            f"commit {entry['commit']}: "
            f"{entry['deleted_files']}/{entry['total_files']} files "
            f"({entry['ratio']*100:.1f}%), {entry['deleted_lines']} lines"
        ),
        "data": entry,
    }
    with open(alerts_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk deletion gate — dual-metric detection"
    )
    parser.add_argument(
        "--submodules",
        action="store_true",
        help="Check all submodules' most recent commit (pre-push mode)",
    )
    parser.add_argument(
        "--scan-recent",
        type=int,
        default=0,
        metavar="N",
        help="Scan last N commits in all submodules (daemon/cron mode)",
    )
    parser.add_argument(
        "--json", action="store_true", help="JSON output"
    )
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=None,
        help="Workspace root (auto-detected if omitted)",
    )
    args = parser.parse_args()

    if os.environ.get("BULK_DELETE_ACK") == "1":
        if args.json:
            print(json.dumps({"skipped": True, "reason": "BULK_DELETE_ACK=1"}))
        return 0

    if args.submodules or args.scan_recent > 0:
        ws_root = args.workspace_root or _git("rev-parse", "--show-toplevel")
        if not ws_root:
            print("ERROR: cannot determine workspace root", file=sys.stderr)
            return 2
        n = args.scan_recent if args.scan_recent > 0 else 1
        findings = _check_submodule_recent_commits(ws_root, n)
        if args.scan_recent > 0:
            for f in findings:
                _write_alert(ws_root, f)
        if args.json:
            print(json.dumps({"findings": findings}, indent=2, ensure_ascii=False))
        else:
            if findings:
                for f in findings:
                    print(
                        f"[bulk-deletion] ❌ {f['submodule']} @ {f['commit']}: "
                        f"{f['deleted_files']}/{f['total_files']} files "
                        f"({f['ratio']*100:.1f}%), {f['deleted_lines']} lines deleted",
                        file=sys.stderr,
                    )
                print(
                    f"[bulk-deletion] ❌ {len(findings)} submodule(s) have "
                    f"suspicious bulk deletions",
                    file=sys.stderr,
                )
                print(
                    "[bulk-deletion] Recovery: git -C <submodule> reset --hard <commit>^",
                    file=sys.stderr,
                )
                return 1
            else:
                print("[bulk-deletion] ✅ all submodules clean")
        return 1 if findings else 0

    result = _check_staged()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["blocked"]:
            print(
                f"[bulk-deletion] ❌ BULK DELETION detected:",
                file=sys.stderr,
            )
            print(
                f"[bulk-deletion]   {result['deleted_files']}/{result['total_files']} "
                f"files ({result['ratio']*100:.1f}%) staged for deletion",
                file=sys.stderr,
            )
            print(
                f"[bulk-deletion]   {result['deleted_lines']} lines will be removed",
                file=sys.stderr,
            )
            print(
                "[bulk-deletion]   Threshold: ≥50% files AND ≥1000 lines",
                file=sys.stderr,
            )
            if result["details"]:
                print("[bulk-deletion]   Top deleted files:", file=sys.stderr)
                for d in result["details"][:5]:
                    print(
                        f"[bulk-deletion]     {d['file']} (-{d['lines']} lines)",
                        file=sys.stderr,
                    )
            print(
                "[bulk-deletion]   Override: BULK_DELETE_ACK=1 git commit ...",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
