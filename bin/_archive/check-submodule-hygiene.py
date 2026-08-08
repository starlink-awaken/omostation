#!/usr/bin/env python3
"""check-submodule-hygiene.py — 子模块卫生守门 (Round 5f, ADR-0151)

3 类问题检测:
1. submodule-dirty: 任意子模块内部有 uncommitted changes (本地子模块脏)
2. tracked-derived: 派生面路径 tracked (应是 gitignored)
3. submodule-pointer-stale: 任意子模块 SHA 与 origin/main 不一致 (PR 推动时会 reset)

用法:
    uv run --with pyyaml python bin/ssot/check-submodule-hygiene.py
    uv run --with pyyaml python bin/ssot/check-submodule-hygiene.py --json
    uv run --with pyyaml python bin/ssot/check-submodule-hygiene.py --strict   # 任何错都 exit 1

CI 集成: 在 OMO operating-rhythm weekly cron (周一 10:00) 跑 --strict,
失败 → 自动 PR 报告到 #134 类型的 governance-track 频道.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]


def _run(cmd: list[str], cwd: Path = WS) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


def _git(*args: str) -> tuple[int, str]:
    rc, out, _ = _run(["git", *args])
    return rc, out.strip()


def check_submodule_dirty() -> list[dict]:
    """检测子模块内部 uncommitted changes"""
    findings = []
    # 列所有 submodule path
    rc, out = _git("config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$")
    if rc != 0:
        return findings
    for line in out.splitlines():
        if not line:
            continue
        _, sub_path = line.split()
        # 跳 nested submodule (3 级及以上)
        depth = sub_path.count("/projects/") + sub_path.count("/scripts/")
        if depth > 0 and "/projects/" in sub_path:
            # projects/* (1-level)
            depth = 1
        # submodule 内部 status
        rc2, out2, _ = _run(["git", "-C", sub_path, "status", "--porcelain"])
        if rc2 == 0 and out2.strip():
            # 提取 untracked + modified 文件
            files = [line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) > 1 else line
                     for line in out2.strip().splitlines() if line.strip()]
            findings.append({
                "type": "submodule-dirty",
                "submodule": sub_path,
                "files": files[:5],  # 最多 5 个
                "n_files": len(files),
            })
    return findings


def check_tracked_derived() -> list[dict]:
    """检测派生面路径被 tracked (应是 gitignored)"""
    findings = []
    # 已知派生面路径
    derived_paths = [
        "runtime/.watch-dispatch-stamps.json",
        ".omo/_derived/",
    ]
    for dp in derived_paths:
        rc, _, _ = _run(["git", "ls-files", "--error-unmatch", dp])
        if rc == 0:
            # 被 tracked
            findings.append({
                "type": "tracked-derived",
                "path": dp,
                "fix": "在 .gitignore 加 gitignore 规则",
            })
    return findings


def check_submodule_pointer_stale() -> list[dict]:
    """检测子模块 SHA 与 origin/main 不一致 (非 fast-forward)"""
    findings = []
    # 拉 origin/main
    _run(["git", "fetch", "origin", "main"])
    # 主仓本地与 origin/main 的 submodule diff
    rc1, main_subs, _ = _run(["git", "ls-tree", "origin/main", "--name-only"])
    rc2, local_subs, _ = _run(["git", "ls-tree", "HEAD", "--name-only"])
    if rc1 != 0 or rc2 != 0:
        return findings
    # parse projects/* and scripts
    main_map = {}
    for line in main_subs.splitlines():
        if line.startswith("projects/") or line == "scripts":
            parts = line.split()
            if len(parts) == 3:
                _, sha, path = parts
                main_map[path] = sha
    local_map = {}
    for line in local_subs.splitlines():
        if line.startswith("projects/") or line == "scripts":
            parts = line.split()
            if len(parts) == 3:
                _, sha, path = parts
                local_map[path] = sha
    for path in set(main_map) | set(local_map):
        m_sha = main_map.get(path)
        l_sha = local_map.get(path)
        if m_sha and l_sha and m_sha != l_sha:
            findings.append({
                "type": "submodule-pointer-stale",
                "submodule": path,
                "main_sha": m_sha,
                "local_sha": l_sha,
                "fix": "git submodule update --init <path>",
            })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="任一错 exit 1")
    args = parser.parse_args()

    findings = []
    findings.extend(check_submodule_dirty())
    findings.extend(check_tracked_derived())
    findings.extend(check_submodule_pointer_stale())

    by_type: dict[str, list] = {}
    for f in findings:
        by_type.setdefault(f["type"], []).append(f)

    if args.json:
        print(json.dumps({
            "ws": str(WS),
            "n_findings": len(findings),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "findings": findings,
        }, ensure_ascii=False, indent=2, default=str))
        return 0 if not findings or not args.strict else 1

    print(f"# Submodule Hygiene Check (ws={WS})")
    print(f"  total findings: {len(findings)}")
    print()
    if not findings:
        print("✅ 全部干净")
        return 0

    for ftype, items in by_type.items():
        print(f"## {ftype} ({len(items)} 项)")
        for f in items:
            if ftype == "submodule-dirty":
                print(f"  - {f['submodule']}: {f['n_files']} 个 uncommitted (例: {f['files'][:3]})")
            elif ftype == "tracked-derived":
                print(f"  - {f['path']} (fix: {f['fix']})")
            elif ftype == "submodule-pointer-stale":
                print(f"  - {f['submodule']}: main={f['main_sha'][:7]} local={f['local_sha'][:7]} (fix: {f['fix']})")
        print()

    if args.strict:
        print("❌ --strict 模式, exit 1")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
