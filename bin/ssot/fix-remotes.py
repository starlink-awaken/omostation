#!/usr/bin/env python3
"""fix-remotes.sh → fix-remotes.py — 自动修复 root + 全部 submodule 的 origin 指向.

T10-134 hook-manifest.yaml: remote-hygiene check 的 fix 字段指引此脚本.

2026-09-13 Python 重写 (bash 版三重缺陷, 均为实证污染事故根因):
  1. [ -d .git ] 判断 — worktree 中 .git 是文件 → 脚本在全部 worktree 静默失效
  2. awk 解析 .gitmodules 失效 (段名含 '/' 时 $NF 永不等于 path/url) →
     子模块修复从未执行
  3. 对未初始化子模块 (目录存在但无 .git) 执行 git remote set-url 会
     向上解析到主仓共享 config — "修复"实际上把子模块 URL 写进主仓
     origin (串联覆盖, 最后写的赢) → 这就是 root origin 被改写成
     omostation-runtime 的机制

行为:
  1. 修复 root remote.origin.url (fetch + push) → canonical omostation
  2. 按 .gitmodules 修复已初始化子模块的 origin (跳过未初始化目录)
  3. 幂等 — 仅在当前 URL 与期望不符时写入
"""

from __future__ import annotations

import configparser
import os
import subprocess
import sys

CANONICAL_ROOT = "https://github.com/starlink-awaken/omostation.git"


def _git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")},
    )


def _normalize(url: str) -> str:
    if url.startswith("git@github.com:"):
        url = f"https://github.com/{url.split(':', 1)[1]}"
    return url


def _matches(actual: str, expected: str) -> bool:
    return _normalize(actual) == _normalize(expected)


def main() -> int:
    ws = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if ws.returncode != 0 or not ws.stdout.strip():
        print(f"[fix-remotes] ❌ 不在 git 仓库内", file=sys.stderr)
        return 1
    root = ws.stdout.strip()

    # ── root: fetch + push URL ──
    for flag, label in (([], "fetch"), (["--push"], "push")):
        cur = _git(["remote", "get-url", *flag, "origin"], root)
        if cur.returncode != 0:
            continue
        actual = cur.stdout.strip()
        if actual and not _matches(actual, CANONICAL_ROOT):
            print(f"[fix-remotes] root: 修复 origin {label} {actual} → {CANONICAL_ROOT}")
            _git(["remote", "set-url", *flag, "origin", CANONICAL_ROOT], root)

    # ── submodules: 按 .gitmodules 修复已初始化的 ──
    gm = os.path.join(root, ".gitmodules")
    if os.path.isfile(gm):
        parser = configparser.ConfigParser()
        parser.read(gm)
        for section in parser.sections():
            sub_path = parser.get(section, "path", fallback=None)
            sub_url = parser.get(section, "url", fallback=None)
            if not sub_path or not sub_url:
                continue
            sub_dir = os.path.join(root, sub_path)
            # 关键守卫: 未初始化子模块 (无 .git 文件/目录) 必须跳过 —
            # 否则 git -C 向上解析到主仓 config, "修复"反成污染源.
            if not os.path.exists(os.path.join(sub_dir, ".git")):
                continue
            cur = _git(["remote", "get-url", "origin"], sub_dir)
            if cur.returncode != 0:
                continue
            actual = cur.stdout.strip()
            if actual and not _matches(actual, sub_url):
                print(f"[fix-remotes] submodule {sub_path}: 修复 {actual} → {sub_url}")
                _git(["remote", "set-url", "origin", sub_url], sub_dir)

    print("[fix-remotes] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
