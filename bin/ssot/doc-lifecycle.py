#!/usr/bin/env python3
"""doc-lifecycle — 文档生命周期治理工具.

提供 audit / archive / lint 三类子命令, 与 doc-ssot-lint.py 共用 SCAN_GLOBS.

用法:
  python3 bin/ssot/doc-lifecycle.py audit              # 审计无 frontmatter / 重复 / 过期文档
  python3 bin/ssot/doc-lifecycle.py archive [--dry-run] # 归档 ephemeral 文档
  python3 bin/ssot/doc-lifecycle.py lint [--fix]       # 生命周期合规检查

退出码:
  0 = 通过
  1 = 发现违规
  2 = 配置错误
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

SCAN_GLOBS = [
    "CLAUDE.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "LAYER-INDEX.md",
    "README.md",
    "CONTRIBUTING.md",
    "DESIGN.md",
    "docs/*.md",
    "docs/**/*.md",
    "projects/AGENTS.md",
    "projects/*/AGENTS.md",
    "projects/*/CLAUDE.md",
    "projects/*/ARCHITECTURE.md",
    "projects/*/README.md",
    "projects/*/BOUNDARY.md",
    "projects/*/GOVERNANCE.md",
]

EXCLUDE_SUBSTRINGS = [
    "node_modules",
    ".venv",
    "__pycache__",
    "_archived",
    "/archive/",
    "DOC-ARCH.md",
    ".pytest_cache",
]

ARCHIVE_DIR = WORKSPACE_ROOT / ".omo" / "_archive"
MAX_AGE_DAYS = 90


def find_md_files() -> list[Path]:
    files = []
    for glob_pat in SCAN_GLOBS:
        files.extend(WORKSPACE_ROOT.glob(glob_pat))
    seen = set()
    result = []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        path_str = str(f)
        if any(excl in path_str for excl in EXCLUDE_SUBSTRINGS):
            continue
        if f.is_file():
            result.append(f)
    return sorted(result)


def has_frontmatter(content: str) -> bool:
    return content.startswith("---")


def parse_frontmatter(content: str) -> dict:
    if not has_frontmatter(content):
        return {}
    fm = {}
    body = content.split("---", 2)[1]
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        fm[key] = val
    return fm


def get_file_type(path: Path) -> str:
    rel = path.relative_to(WORKSPACE_ROOT).as_posix()
    if rel.startswith("docs/"):
        return "docs"
    if rel.startswith("projects/"):
        return "project"
    return "root"


def audit_no_frontmatter() -> list[Path]:
    missing = []
    for fp in find_md_files():
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not has_frontmatter(content):
            missing.append(fp)
    return missing


def audit_duplicates() -> dict[str, list[Path]]:
    hashes = defaultdict(list)
    for fp in find_md_files():
        try:
            data = fp.read_bytes()
        except Exception:
            continue
        h = hashlib.sha256(data).hexdigest()
        hashes[h].append(fp)
    return {h: paths for h, paths in hashes.items() if len(paths) > 1}


def audit_ephemeral() -> list[tuple[Path, int]]:
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    old = []
    for fp in find_md_files():
        try:
            mtime = datetime.fromtimestamp(fp.stat().st_mtime)
        except Exception:
            continue
        if mtime < cutoff:
            old.append((fp, (datetime.now() - mtime).days))
    return sorted(old, key=lambda x: x[1], reverse=True)


def cmd_audit(args: argparse.Namespace) -> int:
    print("=== 文档生命周期审计 ===\n")

    no_fm = audit_no_frontmatter()
    print(f"无 frontmatter 文档: {len(no_fm)}")
    for fp in no_fm:
        print(f"  {fp.relative_to(WORKSPACE_ROOT)}")
    print()

    dups = audit_duplicates()
    print(f"重复文档组: {len(dups)}")
    for h, paths in dups.items():
        print(f"  {h[:12]}… ({len(paths)} 份)")
        for fp in paths:
            print(f"    {fp.relative_to(WORKSPACE_ROOT)}")
    print()

    old = audit_ephemeral()
    print(f"超过 {MAX_AGE_DAYS} 天未更新 (ephemeral): {len(old)}")
    for fp, days in old[:20]:
        print(f"  {fp.relative_to(WORKSPACE_ROOT)} ({days}d)")
    if len(old) > 20:
        print(f"  … 省略 {len(old) - 20} 项")

    return 0 if not no_fm and not dups and not old else 1


def cmd_archive(args: argparse.Namespace) -> int:
    dry_run = args.dry_run
    print(f"=== 归档 ephemeral 文档 {'(dry-run)' if dry_run else ''} ===\n")

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    old = audit_ephemeral()
    if not old:
        print("无需归档的文档")
        return 0

    moved = 0
    for fp, days in old:
        rel = fp.relative_to(WORKSPACE_ROOT)
        dest = ARCHIVE_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {rel} -> {dest} ({days}d)")
        if not dry_run:
            shutil.move(str(fp), str(dest))
        moved += 1

    print(f"\n{'将归档' if dry_run else '已归档'} {moved} 个文档到 {ARCHIVE_DIR}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    fix = args.fix
    print(f"=== 文档生命周期 lint {'(--fix)' if fix else ''} ===\n")

    findings = 0
    fixes = 0

    for fp in find_md_files():
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not has_frontmatter(content):
            findings += 1
            if fix:
                ftype = get_file_type(fp)
                now = datetime.now().strftime("%Y-%m-%d")
                fm = {
                    "root": f'---\ntype: ssot\nowner: governance-team\nlast_updated: {now}\n---\n',
                    "project": f'---\nproject: {fp.parent.name}\ntype: ssot\nowner: governance-team\nlast_updated: {now}\n---\n',
                    "docs": f'---\ntype: documentation\nowner: governance-team\nlast_updated: {now}\n---\n',
                }.get(ftype, f'---\ntype: ssot\nowner: governance-team\nlast_updated: {now}\n---\n')
                new_content = fm + content
                fp.write_text(new_content, encoding="utf-8")
                fixes += 1
                print(f"  [fix] {fp.relative_to(WORKSPACE_ROOT)}")

    print(f"\n发现 {findings} 个问题, {'修复' if fix else '需要修复'} {fixes} 个")
    return 0 if findings == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="文档生命周期治理工具")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit", help="审计无 frontmatter / 重复 / 过期文档")
    p_archive = sub.add_parser("archive", help="归档 ephemeral 文档")
    p_archive.add_argument("--dry-run", action="store_true", help="只报告不执行")
    p_lint = sub.add_parser("lint", help="生命周期合规检查")
    p_lint.add_argument("--fix", action="store_true", help="自动修复")

    args = parser.parse_args()
    if args.command == "audit":
        return cmd_audit(args)
    if args.command == "archive":
        return cmd_archive(args)
    if args.command == "lint":
        return cmd_lint(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
