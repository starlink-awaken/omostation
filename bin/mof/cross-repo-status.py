#!/usr/bin/env python3
"""cross-repo-status.py — B2.2 跨子模块统一 status 报告.

读取主仓 + 所有 projects/* 子模块的 git 状态, 输出统一 dashboard:
  - 主仓分支 + 是否 dirty
  - 每个子模块 HEAD 与 gitlink 是否一致
  - 各仓 git log -1 (最近 commit)
  - 各仓 open PR 数 (gh CLI 可选)

用法:
  python3 bin/mof/cross-repo-status.py [--json]
  python3 bin/mof/cross-repo-status.py --bet BET-Y1Q4-T10-02   # 关联某 BET 输出

依赖: git (必需), urllib (gh API 可选)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def git(args: list[str], cwd: Path | None = None) -> str:
    """Run git command, return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or WORKSPACE,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result.stdout.strip()


def main_status() -> dict:
    """读主仓 + 子模块 status, 返回统一 dict."""
    # 主仓
    main = {
        "name": "omostation",
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head_sha": git(["rev-parse", "HEAD"])[:7],
        "head_subject": git(["log", "-1", "--pretty=format:%s"]),
        "dirty": bool(git(["status", "--porcelain"])),
        "kind": "main",
    }

    # 子模块列表 (.gitmodules 解析)
    gitmodules = WORKSPACE / ".gitmodules"
    sub_names: list[str] = []
    if gitmodules.exists():
        for line in gitmodules.read_text().splitlines():
            m = re.match(r"\s*path\s*=\s*(.+)", line)
            if m:
                sub_names.append(m.group(1).strip())

    sub_statuses = []
    for path in sub_names:
        sub_dir = WORKSPACE / path
        # 仅当已 checkout
        if not (sub_dir / ".git").exists() and not (sub_dir / "HEAD").exists():
            sub_statuses.append({
                "name": path.split("/")[-1],
                "path": path,
                "checkout": False,
                "reason": "submodule not initialized (SSL/network or worktree)",
            })
            continue

        sha = git(["-C", path, "rev-parse", "HEAD"])[:7]
        branch = git(["-C", path, "rev-parse", "--abbrev-ref", "HEAD"])
        subject = git(["-C", path, "log", "-1", "--pretty=format:%s"])
        dirty = bool(git(["-C", path, "status", "--porcelain"]))
        gitlink_full = git(["ls-tree", "HEAD", path]).split()[2] if git(["ls-tree", "HEAD", path]) else None
        gitlink = gitlink_full[:7] if gitlink_full else None

        sub_statuses.append({
            "name": path.split("/")[-1],
            "path": path,
            "checkout": True,
            "branch": branch,
            "head_sha": sha,
            "head_subject": subject,
            "dirty": dirty,
            "gitlink_sha": gitlink,
            "head_matches_gitlink": sha == gitlink,
        })

    return {"main": main, "submodules": sub_statuses, "total": len(sub_statuses)}


def format_text(data: dict) -> str:
    """stdout 友好的表格."""
    lines = ["━━━ cross-repo-status ━━━", ""]
    main = data["main"]
    lines.append(f"主仓 {main['name']}")
    lines.append(f"  分支: {main['branch']} @ {main['head_sha']}")
    lines.append(f"  最近: {main['head_subject']}")
    lines.append(f"  dirty: {'是' if main['dirty'] else '否'}")
    lines.append("")
    lines.append(f"子模块 ({data['total']} 个):")
    lines.append("")
    lines.append(f"{'name':<20} {'checkout':<10} {'branch':<12} {'head':<8} {'dirty':<6} {'aligned'}")
    lines.append("-" * 80)
    for s in data["submodules"]:
        if not s["checkout"]:
            lines.append(f"{s['name']:<20} {'NO':<10} -          -        -       -")
            continue
        aligned = "✓" if s["head_matches_gitlink"] else "✗"
        dirty = "是" if s["dirty"] else "否"
        lines.append(
            f"{s['name']:<20} {'YES':<10} {s['branch']:<12} {s['head_sha']:<8} {dirty:<6} {aligned}"
        )
    lines.append("")
    not_aligned = [s for s in data["submodules"] if s["checkout"] and not s["head_matches_gitlink"]]
    if not_aligned:
        lines.append(f"⚠️  {len(not_aligned)} 个子模块 HEAD 与 gitlink 不一致:")
        for s in not_aligned:
            lines.append(f"  - {s['name']}: HEAD={s['head_sha']} gitlink={s['gitlink_sha']}")
    not_checkout = [s for s in data["submodules"] if not s["checkout"]]
    if not_checkout:
        lines.append(f"ℹ️  {len(not_checkout)} 个子模块未 checkout: {', '.join(s['name'] for s in not_checkout)}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--bet", help="关联某 BET 输出 (用于 closeout-pr.sh)")
    args = ap.parse_args()

    try:
        data = main_status()
    except subprocess.TimeoutExpired:
        print("❌ git 超时")
        return 1

    if args.bet:
        # 关联 BET: 输出额外 context
        data["bet_id"] = args.bet

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(format_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())