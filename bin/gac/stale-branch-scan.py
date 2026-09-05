#!/usr/bin/env python3
"""Scan remote branches for staleness and output report.

Used by stale-branch-reminder.yml to identify branches that need attention.

Usage:
    python3 bin/gac/stale-branch-scan.py --days 14 --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STALE_DAYS = 14

# Prefixes to monitor
MONITORED_PREFIXES = (
    "origin/work/",
    "origin/feat/",
    "origin/fix/",
    "origin/agent/",
    "origin/chore/",
    "origin/docs/",
    "origin/refactor/",
    "origin/test/",
)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def get_workspace_root() -> Path:
    r = git(["rev-parse", "--show-toplevel"], cwd=DEFAULT_WORKSPACE_ROOT)
    if r.returncode != 0:
        print(f"ERROR: not inside a git repo: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return Path(r.stdout.strip())


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def scan_stale_branches(
    workspace_root: Path, stale_days: int
) -> list[dict[str, Any]]:
    r = git(
        ["branch", "-r", "--format=%(refname:short)"],
        cwd=workspace_root,
    )
    if r.returncode != 0:
        return []

    stale: list[dict[str, Any]] = []
    cutoff = datetime.now() - timedelta(days=stale_days)
    critical = datetime.now() - timedelta(days=30)

    for branch in r.stdout.splitlines():
        branch = branch.strip()
        if not branch or branch.startswith("origin/HEAD"):
            continue

        # Only monitor specific prefixes
        if not any(branch.startswith(p) for p in MONITORED_PREFIXES):
            continue

        # Skip main
        if branch == "origin/main":
            continue

        # Get last commit date
        lr = git(["log", "--format=%ci;%an;%s", "-1", branch], cwd=workspace_root)
        if lr.returncode != 0 or not lr.stdout.strip():
            continue

        parts = lr.stdout.strip().split(";", 2)
        date_str = parts[0].strip()[:19]
        author = parts[1].strip() if len(parts) > 1 else "?"
        subject = parts[2].strip() if len(parts) > 2 else "?"

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        if dt >= cutoff:
            continue

        severity = "critical" if dt < critical else "warning"
        days_inactive = (datetime.now() - dt).days

        # Get PR status (open/merged/closed)
        pr_status = "no-pr"
        try:
            pr = subprocess.run(
                ["gh", "pr", "list", "--head", branch.replace("origin/", ""),
                 "--state", "all", "--json", "state,number,title",
                 "--limit", "1"],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if pr.returncode == 0 and pr.stdout.strip():
                pr_data = json.loads(pr.stdout)
                if pr_data:
                    pr_info = pr_data[0]
                    pr_status = pr_info.get("state", "unknown")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        short_name = branch.replace("origin/", "")
        stale.append(
            {
                "branch": short_name,
                "full_ref": branch,
                "last_commit": date_str,
                "days_inactive": days_inactive,
                "severity": severity,
                "author": author,
                "subject": subject[:80],
                "pr_status": pr_status,
            }
        )

    stale.sort(key=lambda x: x["days_inactive"], reverse=True)
    return stale


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan remote branches for staleness."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"Days of inactivity to flag (default: {DEFAULT_STALE_DAYS})",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON"
    )
    args = parser.parse_args()

    workspace_root = get_workspace_root()
    stale = scan_stale_branches(workspace_root, args.days)

    report = {
        "timestamp": datetime.now().isoformat() + "Z",
        "threshold_days": args.days,
        "total_stale": len(stale),
        "critical": len([b for b in stale if b["severity"] == "critical"]),
        "warning": len([b for b in stale if b["severity"] == "warning"]),
        "branches": stale,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Stale branches (>{args.days} days): {len(stale)}")
        for b in stale:
            tag = "🔴" if b["severity"] == "critical" else "🟡"
            print(
                f"  {tag} {b['branch']} [{b['days_inactive']}d] "
                f"PR={b['pr_status']} — {b['subject'][:60]}"
            )

    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
