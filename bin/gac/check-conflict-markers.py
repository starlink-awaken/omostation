#!/usr/bin/env python3
"""check-conflict-markers: 检测入库文件的 git 合并冲突标记。

治本: ecos `0ff6ad3` 把含 `<<<<<<<` 的 sgf-policy.yaml commit 入库 (2026-08-07 实证),
      ci-local-fast 的 test-gac-engine 读它 YAML 解析 FAIL → 全仓 push 被卡。
本 gate 把"冲突标记入库"拦在最早 (commit/push 前), 而非等下游 yaml 解析报错。

检测标记 (低误报设计):
  - `<<<<<<< ` / `>>>>>>> `  git diff 冲突头/尾, 几乎不出现在正常代码
  - `||||||| `               diff3 base 标记
  - `=======`                仅当同文件出现 head/tail 时计 (避免误报 markdown <hr>/分隔线)

扫描范围:
  - 默认 / --staged: staged 文件 (读 index blob, pre-commit 场景)
  - --all:           所有 tracked 文件 (CI / gate 场景)

Output: exit 0 = 干净; exit 1 = 发现冲突标记 (blocking)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

CONFLICT_HEAD = re.compile(r"^<{7} ", re.MULTILINE)
CONFLICT_TAIL = re.compile(r"^>{7} ", re.MULTILINE)
CONFLICT_BASE = re.compile(r"^\|{7} ", re.MULTILINE)
CONFLICT_SEP = re.compile(r"^={7}$", re.MULTILINE)


def _staged_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"],
            cwd=WORKSPACE, capture_output=True, text=True, check=True,
        )
        return [f for f in out.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []


def _tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=WORKSPACE, capture_output=True, text=True, check=True,
        )
        return [f for f in out.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []


def _staged_blob(path: str) -> str | None:
    """读 index blob (staged 内容), 非磁盘 — pre-commit 场景必须读 index."""
    try:
        out = subprocess.run(
            ["git", "show", f":{path}"], cwd=WORKSPACE, capture_output=True, text=True, check=True,
        )
        return out.stdout
    except subprocess.CalledProcessError:
        return None


def _disk_content(path: str) -> str | None:
    p = WORKSPACE / path
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _scan(content: str) -> list[tuple[int, str]]:
    """返回 [(行号, 类型)]. ======= 仅在有 head/tail 时计, 防 md/hr 误报."""
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(content.splitlines(), 1):
        if CONFLICT_HEAD.match(line):
            hits.append((i, "head"))
        elif CONFLICT_TAIL.match(line):
            hits.append((i, "tail"))
        elif CONFLICT_BASE.match(line):
            hits.append((i, "base"))
        elif CONFLICT_SEP.match(line):
            hits.append((i, "separator"))
    has_headtail = any(k in ("head", "tail") for _, k in hits)
    if has_headtail:
        return hits
    return []  # 只有孤立的 ======= 不算 (md/hr 误报)


def main() -> int:
    ap = argparse.ArgumentParser(description="检测 git 合并冲突标记防入库")
    ap.add_argument("--staged", action="store_true", help="扫 staged (默认行为, 兼容 gac-local-gate)")
    ap.add_argument("--all", action="store_true", help="扫所有 tracked")
    ap.add_argument("--include-untracked", action="store_true", help="同 --all (兼容)")
    ap.add_argument("--file", action="append", default=[], help="限定文件 (可多次)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if args.file:
        files = args.file
        read = lambda f: (_staged_blob(f) if not args.all else None) or _disk_content(f)
        contents = {f: read(f) for f in files}
    elif args.all or args.include_untracked:
        files = _tracked_files()
        contents = {f: _disk_content(f) for f in files}
    else:
        files = _staged_files()
        contents = {f: _staged_blob(f) for f in files}

    findings: list[dict] = []
    for f, content in contents.items():
        if content is None:
            continue
        hits = _scan(content)
        if hits:
            findings.append({"file": f, "markers": [{"line": ln, "type": k} for ln, k in hits]})

    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False))
    elif findings:
        print(f"❌ check-conflict-markers: {len(findings)} 个文件含 git 冲突标记", file=sys.stderr)
        for fnd in findings:
            print(f"  {fnd['file']}:", file=sys.stderr)
            for m in fnd["markers"]:
                print(f"    line {m['line']}: {m['type']}", file=sys.stderr)
        print("  修复: 解决冲突后 git add, 勿把冲突标记入库", file=sys.stderr)
    else:
        print("✅ check-conflict-markers: 无冲突标记")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
