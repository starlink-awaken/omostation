#!/usr/bin/env python3
"""P78 R1: 跨子仓联动检查.

检测 omostation 根仓与子仓 (ecos / agora / cockpit / omo / runtime) 的状态:
- 子仓 commit 是否落后 (mof-version 引用)
- 子仓 dirty state (未提交修改)
- 子仓 ahead/behind origin 计数

使用:
  python3 bin/ssot/cross-submodule-check.py
  python3 bin/ssot/cross-submodule-check.py --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


# 关注的核心子仓
KEY_SUBMODULES = ["ecos", "agora", "cockpit", "omo", "runtime", "scripts"]


def run_git(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """运行 git 命令."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, cwd=cwd, timeout=30,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except Exception as e:
        return 1, str(e)


def check_submodule(root: Path, name: str) -> dict:
    """检查单个子仓."""
    sub = root / "projects" / name
    info = {
        "name": name,
        "path": str(sub.relative_to(root)) if sub.exists() else None,
        "exists": sub.exists(),
        "dirty": False,
        "ahead": 0,
        "behind": 0,
        "current": None,
        "error": None,
    }
    if not sub.exists():
        info["error"] = "path not found"
        return info
    rc, out = run_git(["status", "--short"], cwd=sub)
    info["dirty"] = bool(out.strip())
    rc, out = run_git(["log", "-1", "--format=%H %s"], cwd=sub)
    if out.strip():
        parts = out.strip().split(" ", 1)
        info["current"] = {"hash": parts[0][:8], "subject": parts[1] if len(parts) > 1 else ""}
    # ahead/behind
    rc, out = run_git(["rev-list", "--count", "HEAD..@{u}"], cwd=sub)
    if out.strip().isdigit():
        info["behind"] = int(out.strip())
    rc, out = run_git(["rev-list", "--count", "@{u}..HEAD"], cwd=sub)
    if out.strip().isdigit():
        info["ahead"] = int(out.strip())
    return info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P78: 跨子仓联动检查 (ecos/agora/cockpit/omo/runtime/scripts)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--module", help="仅检查指定子仓")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".git").exists():
        print(f"❌ {root} 不是 git 仓库")
        return 1

    modules = [args.module] if args.module else KEY_SUBMODULES
    results = []
    summary = {"healthy": 0, "dirty": 0, "behind": 0, "missing": 0, "error": 0}

    for name in modules:
        info = check_submodule(root, name)
        results.append(info)
        if not info["exists"]:
            summary["missing"] += 1
        elif info["dirty"]:
            summary["dirty"] += 1
        elif info["behind"] > 0:
            summary["behind"] += 1
        elif info["error"]:
            summary["error"] += 1
        else:
            summary["healthy"] += 1

    if args.json:
        out = {
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "workspace_root": str(root),
            "summary": summary,
            "submodules": results,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # text 格式
    print("=" * 70)
    print(f"🔗 P78 跨子仓联动检查 ({len(modules)} 个子仓)")
    print("=" * 70)
    print(f"📁 Workspace: {root}")
    print(f"🕐 生成时间: {datetime.now(UTC).isoformat()}Z")
    print()
    print(f"{'子仓':<12s}{'状态':<12s}{'落后':<6s}{'领先':<6s}{'当前 commit'}")
    print("-" * 70)
    for info in results:
        if not info["exists"]:
            status = "❌ 不存在"
        elif info["error"]:
            status = f"⚠️  {info['error']}"
        elif info["dirty"]:
            status = "🔴 未提交"
        elif info["behind"] > 0:
            status = f"🟡 落后 {info['behind']}"
        else:
            status = "🟢 健康"
        current = info["current"]["hash"] if info["current"] else "-"
        subject = info["current"]["subject"] if info["current"] else ""
        print(f"{info['name']:<12s}{status:<12s}{info['behind']:<6d}{info['ahead']:<6d}{current} {subject[:30]}")
    print("-" * 70)
    print()
    print(f"📊 汇总: 健康 {summary['healthy']} / 落后 {summary['behind']} / 未提交 {summary['dirty']} / 错误 {summary['error']} / 不存在 {summary['missing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())