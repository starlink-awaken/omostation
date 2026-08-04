#!/usr/bin/env python3
"""DRY 冲突检测器 (G4) — merge CONFLICTING 时标记被 base 取代的 PR 改动.

P79 / #907 教训: PR merge CONFLICTING 时, 可能是 PR 改动被 base 取代 (DRY,
两边实现同功能), 不是真冲突. 本工具 diff PR vs merge-base, 标记 base 端也有
同符号实现的改动 → 提示丢弃 PR 改动取 base (而非无脑 merge main 解冲突).

用法:
  python3 bin/gac/dry-conflict-detector.py --base origin/main --head HEAD
  python3 bin/gac/dry-conflict-detector.py --base main --head work/my-pr
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def merge_base(base: str, head: str, cwd: Path) -> str:
    return run(["git", "merge-base", base, head], cwd).stdout.strip()


def changed_files(base: str, head: str, cwd: Path) -> list[str]:
    """PR 改的文件 (vs merge-base)."""
    mb = merge_base(base, head, cwd)
    if not mb:
        return []
    r = run(["git", "diff", "--name-only", mb, head], cwd)
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def base_also_changed(base: str, head: str, file: str, cwd: Path) -> bool:
    """base 端是否也改了该文件 (双方都改 = 冲突源)."""
    mb = merge_base(base, head, cwd)
    if not mb:
        return False
    r = run(["git", "diff", "--name-only", mb, base, "--", file], cwd)
    return bool(r.stdout.strip())


def new_symbols_in_head(base: str, head: str, file: str, cwd: Path) -> list[str]:
    """PR 新增的函数/类符号 (def/class/function/func)."""
    mb = merge_base(base, head, cwd)
    if not mb:
        return []
    diff = run(["git", "diff", mb, head, "--", file], cwd).stdout
    symbols: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+"):
            continue
        m = re.match(r"\+(?:def|class|function|func)\s+(\w+)", line)
        if m:
            symbols.append(m.group(1))
    return symbols


def symbol_in_base(base: str, symbol: str, cwd: Path) -> bool:
    """base 端是否有同名符号定义 (git grep in base rev)."""
    pattern = rf"\b(?:def|class|function|func)\s+{re.escape(symbol)}\b"
    r = run(["git", "grep", "-l", "-E", pattern, base], cwd)
    return bool(r.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description="DRY 冲突检测器 (G4, P79/#907)")
    ap.add_argument("--base", default="origin/main", help="base 分支 (默认 origin/main)")
    ap.add_argument("--head", default="HEAD", help="head 分支 (默认 HEAD)")
    ap.add_argument("--cwd", default=".", help="工作目录")
    args = ap.parse_args()
    cwd = Path(args.cwd)

    files = changed_files(args.base, args.head, cwd)
    if not files:
        print("✅ PR 无改动文件 (vs merge-base)")
        return 0

    dry_findings: list[str] = []
    conflict_files: list[str] = []
    for f in files:
        if not base_also_changed(args.base, args.head, f, cwd):
            continue
        conflict_files.append(f)
        for sym in new_symbols_in_head(args.base, args.head, f, cwd):
            if symbol_in_base(args.base, sym, cwd):
                dry_findings.append(
                    f"{f}: 符号 '{sym}' PR 新增但 base 也有 (DRY 候选, 考虑丢弃 PR 改动取 base)"
                )

    print(f"=== DRY 冲突检测 (base={args.base} head={args.head}) ===")
    print(f"PR 改动文件: {len(files)}, 双方都改: {len(conflict_files)}")
    if dry_findings:
        print(f"\n⚠️ DRY 候选 ({len(dry_findings)}):")
        for f in dry_findings:
            print(f"  • {f}")
        print(
            "\n建议: 这些 PR 改动可能被 base 取代 (DRY), merge 冲突时优先丢弃 PR 取 base, "
            "而非无脑 merge main 解冲突 (#907 教训)."
        )
        return 1
    print("✅ 无 DRY 候选 (PR 改动不被 base 取代)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
