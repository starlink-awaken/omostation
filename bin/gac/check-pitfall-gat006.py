#!/usr/bin/env python3
"""PITFALL-GAT-006: 检测当前分支是否在 main 已自愈后重复造轮子。

逻辑 (对应 PITFALL-GAT-006.yaml / AGENTS.md §11):
  1. git fetch origin main (静默, 最多 10s 超时)
  2. git diff --name-only origin/main...HEAD → 若为空/无差异 → 说明当前分支相对 main 无改动
  3. git log origin/main --merges -10 → 若近期合并 commit 数 >= 2 → 说明 main 频繁吸收合并
  4. 两个条件同时满足 → 输出 WARNING (exit 0, 非阻断)

输出格式: JSON (可被 gac-local-gate.py extract_finding_topics 识别)
  { "ok": false, "message": "...", "findings": [...] }

退出码: 始终 0 (SOFT check — 警告, 不阻断门禁)

参考:
  - .omo/_knowledge/pitfalls/gate/PITFALL-GAT-006.yaml
  - AGENTS.md §11 "动手前先查 main 是否已自愈"
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _git(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a git command in the workspace, capturing output."""
    return subprocess.run(
        ["git"] + args,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def check_pitfall_gat006() -> dict:
    """Detect if current branch has no diff against main and main has recent merges."""
    findings: list[str] = []

    # Step 1: fetch latest origin/main (best-effort, non-blocking)
    fetch_result = _git(["fetch", "origin", "main"], timeout=15)
    if fetch_result.returncode != 0:
        # fetch failed (no network, no remote) — skip check gracefully
        return {"ok": True, "message": "PITFALL-GAT-006 skipped (git fetch failed)", "findings": []}

    # Step 2: check if branch has any diff against origin/main
    diff_result = _git(["diff", "--name-only", "origin/main...HEAD"])
    changed_files = [f for f in diff_result.stdout.strip().splitlines() if f.strip()]

    if changed_files:
        # Branch has meaningful changes — not a redundant-branch situation
        return {"ok": True, "message": "PITFALL-GAT-006 pass (branch has changes)", "findings": []}

    # Step 3: no diff — check if main has recent merge activity
    merge_log = _git(["log", "origin/main", "--merges", "-10", "--oneline"])
    merge_lines = [l.strip() for l in merge_log.stdout.strip().splitlines() if l.strip()]

    if len(merge_lines) < 2:
        # Main is quiet — not enough evidence of self-healing
        return {"ok": True, "message": "PITFALL-GAT-006 pass (main has no recent merges)", "findings": []}

    # Step 4: branch empty + main has recent merges = likely redundant branch
    msg = (
        f"PITFALL-GAT-006 WARNING: current branch has no diff against origin/main, "
        f"but main has {len(merge_lines)} recent merge(s). "
        f"Main may have already self-healed the target fix. "
        f"Consider abandoning this branch to avoid regressing main. "
        f"Recent merges: {'; '.join(merge_lines[:3])}"
    )
    findings.append(msg)

    return {
        "ok": False,
        "message": msg,
        "findings": findings,
        "details": {
            "changed_files_count": len(changed_files),
            "recent_merges_on_main": merge_lines[:5],
        },
    }


def main() -> int:
    result = check_pitfall_gat006()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Always exit 0 — this is a SOFT/warning-only check
    return 0


if __name__ == "__main__":
    sys.exit(main())
