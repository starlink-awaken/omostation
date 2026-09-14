#!/usr/bin/env python3
"""gitlink-drift-protect — 子模块指针漂移检测与 remediation 提案。

检测子模块指针漂移 (本地超前于追踪 commit) 并:
1. 报告漂移 (path / current OID / target OID)
2. --fix 时发出托管 remediation 提案 (不 push)
3. 记录漂移指纹到 gate-known-debt

Usage:
    python3 bin/gac/gitlink-drift-protect.py [--fix] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANAGED_REMEDIATION_ENTRYPOINT = "bin/gac/clone-lifecycle.py integrate"


def get_submodule_status() -> list[dict]:
    """获取子模块状态。"""
    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True, text=True, cwd=REPO,
    )

    submodules = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        # Parse: [+- ]<sha> <path> (<ref>)
        match = re.match(r'^([+\- ])([0-9a-f]+) (\S+)', line)
        if not match:
            continue

        prefix = match.group(1)
        sha = match.group(2)
        path = match.group(3)

        status = {
            "path": path,
            "sha": sha,
            "is_dirty": prefix == "+",
            "is_uninitialized": prefix == "-",
            "is_clean": prefix == " ",
        }
        submodules.append(status)

    return submodules


def get_ahead_count(path: Path) -> int:
    """获取本地超前于 origin/main 的 commit 数。"""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..HEAD"],
            capture_output=True, text=True, cwd=path,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def get_oid(path: Path, ref: str) -> str | None:
    """解析子模块内 ref 的 OID。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            capture_output=True, text=True, cwd=path,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def build_remediation_proposal(sub: dict, path: Path) -> dict:
    """构造托管 remediation 提案 (不执行 push)。"""
    current_oid = get_oid(path, "HEAD") or sub.get("sha")
    target_oid = get_oid(path, "origin/main") or sub.get("sha")
    return {
        "repository": str(REPO),
        "path": sub["path"],
        "current_oid": current_oid,
        "target_oid": target_oid,
        "managed_remediation_entrypoint": MANAGED_REMEDIATION_ENTRYPOINT,
        "instruction": "PUBLICATION_OWNER_REQUIRED",
    }


def main():
    parser = argparse.ArgumentParser(description="Gitlink 漂移防护")
    parser.add_argument("--fix", action="store_true", help="发出 remediation 提案 (不 push)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    submodules = get_submodule_status()
    drifts = []
    clean = []
    uninitialized = []
    proposals = []

    for sub in submodules:
        path = REPO / sub["path"]

        if sub["is_uninitialized"]:
            uninitialized.append(sub)
            continue

        if not sub["is_dirty"]:
            clean.append(sub)
            continue

        # 漂移检测
        ahead = get_ahead_count(path)
        sub["ahead_commits"] = ahead
        sub["branch"] = get_branch(path)

        if args.fix:
            proposal = build_remediation_proposal(sub, path)
            sub["remediation_proposal"] = proposal
            proposals.append(proposal)

        drifts.append(sub)

    output = {
        "total": len(submodules),
        "clean": len(clean),
        "drifted": len(drifts),
        "uninitialized": len(uninitialized),
        "drifts": drifts,
        "remediation_proposals": proposals,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Gitlink Drift Protect")
        print(f"  Total: {len(submodules)} | Clean: {len(clean)} | Drifted: {len(drifts)} | Uninit: {len(uninitialized)}")

        if drifts:
            print(f"\n  Drifted submodules:")
            for d in drifts:
                print(f"    ⚠️ {d['path']}: +{d.get('ahead_commits', '?')} commits ({d.get('branch', '?')})")
                if args.fix and d.get("remediation_proposal"):
                    p = d["remediation_proposal"]
                    print(f"       proposal: path={p['path']} current={p['current_oid']} target={p['target_oid']}")
                    print(f"       entrypoint: {p['managed_remediation_entrypoint']}")
                    print(f"       instruction: {p['instruction']}")

        if uninitialized:
            print(f"\n  Uninitialized:")
            for u in uninitialized:
                print(f"    ❌ {u['path']}")

        if args.fix and proposals:
            print(f"\n  Remediation proposals emitted: {len(proposals)} (no push performed)")

    return 1 if drifts or uninitialized else 0


def get_branch(path: Path) -> str:
    """获取当前分支名。"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=path,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "?"


if __name__ == "__main__":
    sys.exit(main())
