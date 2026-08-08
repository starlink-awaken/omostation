#!/usr/bin/env python3
"""Autoloop Executor — 在worktree里执行确定性变更 → submit PR (T2).

门禁后移架构核心: 系统在沙盒(worktree)里自由操作, submit PR后由审查矩阵审.
复用: gac-worktree.sh claim/submit/merge + 已有工具(rule-adapt/proposal-to-adr等).

Usage:
  python3 bin/ssot/autoloop-executor.py --action rule_downgrade --dry-run
  python3 bin/ssot/autoloop-executor.py --action adr_draft
  python3 bin/ssot/autoloop-executor.py --action tool_archive --target capability-zombie-tasks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from _shared import ROOT, load_yaml

PERMISSION_MATRIX = ROOT / ".omo" / "_truth" / "registry" / "action-permission-matrix.yaml"
GAC_WORKTREE = ROOT / "bin" / "gac" / "gac-worktree.sh"


def _load_matrix() -> dict:
    return load_yaml(PERMISSION_MATRIX)


def _check_permission(action_type: str) -> str:
    """Check action against permission matrix. Returns 'whitelist'|'graylist'|'blacklist'|'unknown'."""
    matrix = _load_matrix()
    for tier in ("whitelist", "graylist", "blacklist"):
        for item in matrix.get(tier, []):
            if item.get("action_type") == action_type:
                return tier
    return "unknown"


def _dispatch_change(action_type: str, target: str | None, worktree: Path) -> dict:
    """Execute the actual change inside the worktree."""
    wt_str = str(worktree)
    results = {"action": action_type, "target": target or "", "changes": []}

    if action_type == "rule_downgrade":
        proc = subprocess.run(
            ["python3", "bin/ssot/rule-adapt.py", "--apply", "--confirm", "--json"],
            capture_output=True, text=True, timeout=30, check=False, cwd=wt_str,
        )
        results["changes"].append(f"rule-adapt --apply: rc={proc.returncode}")

    elif action_type == "adr_draft":
        proc = subprocess.run(
            ["python3", "bin/ssot/proposal-to-adr.py"],
            capture_output=True, text=True, timeout=15, check=False, cwd=wt_str,
        )
        results["changes"].append(f"proposal-to-adr: rc={proc.returncode}")

    elif action_type == "tool_archive" and target:
        archive = worktree / "bin" / "_archive"
        archive.mkdir(parents=True, exist_ok=True)
        src = worktree / "bin" / "ssot" / f"{target}.py"
        if src.exists():
            dst = archive / f"{target}.py"
            src.rename(dst)
            results["changes"].append(f"archived {target}.py")

    elif action_type == "verification_cmd_fix":
        results["changes"].append("verification_cmd update (placeholder)")

    elif action_type == "vision_gap_append":
        results["changes"].append("vision gap append (placeholder)")

    else:
        results["changes"].append(f"unknown action: {action_type}")

    return results


def execute_in_worktree(
    action_type: str,
    *,
    target: str | None = None,
    dry_run: bool = False,
    root: Path | None = None,
) -> dict:
    """Execute a deterministic change in a worktree → submit PR."""
    root = root or ROOT

    # 1. Permission check
    tier = _check_permission(action_type)
    if tier == "blacklist":
        return {"status": "blocked", "reason": f"{action_type} is blacklisted"}
    if tier == "unknown":
        return {"status": "blocked", "reason": f"{action_type} not in permission matrix"}

    if dry_run:
        return {
            "status": "dry_run",
            "action": action_type,
            "target": target,
            "tier": tier,
            "would_execute": True,
        }

    # 2. Claim worktree
    session = f"autoloop-{action_type}-{int(time.time())}"
    claim = subprocess.run(
        ["bash", str(GAC_WORKTREE), "claim", session],
        capture_output=True, text=True, timeout=60, check=False, cwd=str(root),
    )
    if claim.returncode != 0:
        return {"status": "error", "step": "claim", "stderr": claim.stderr[-200:]}

    worktree = root / ".worktrees" / session
    if not worktree.exists():
        worktree = root / ".subtrees" / session  # fallback path

    # 3. Execute change
    change_result = _dispatch_change(action_type, target, worktree)

    # 4. Verify (gac-local-gate)
    verify = subprocess.run(
        ["make", "gac-local-gate"],
        capture_output=True, text=True, timeout=120, check=False, cwd=str(worktree),
    )

    # 5. Submit PR (only if verify passes)
    pr_submitted = False
    if verify.returncode == 0:
        submit = subprocess.run(
            ["bash", str(GAC_WORKTREE), "submit", session],
            capture_output=True, text=True, timeout=60, check=False, cwd=str(root),
        )
        pr_submitted = submit.returncode == 0

    return {
        "status": "completed",
        "session": session,
        "tier": tier,
        "change": change_result,
        "verify_passed": verify.returncode == 0,
        "pr_submitted": pr_submitted,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", required=True, help="action type from permission matrix")
    parser.add_argument("--target", default=None, help="target item for the action")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    result = execute_in_worktree(args.action, target=args.target, dry_run=args.dry_run, root=args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
