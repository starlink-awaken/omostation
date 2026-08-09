#!/usr/bin/env python3
"""PR Review Harvester — BET-Y1Q2-T7-01.

Harvests PR lifecycle events as decision_outcome records for the
engineering-delivery shadow scene. PR merge = accepted verdict;
PR close-without-merge = rejected.

Usage:
  python3 bin/ssot/pr-review-harvester.py                    # harvest all repos, last 7 days
  python3 bin/ssot/pr-review-harvester.py --days 1           # last 24h
  python3 bin/ssot/pr-review-harvester.py --repo projects/cockpit --days 3
  python3 bin/ssot/pr-review-harvester.py --dry-run           # preview without recording
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent.parent
OUTCOMES_DIR = WORKSPACE / ".omo" / "_delivery" / "outcomes"
HARVEST_LOG = OUTCOMES_DIR / "pr-harvest.jsonl"

REPOS = [
    ".",
    "projects/cockpit",
    "projects/agora",
    "projects/kairon",
    "projects/gbrain",
    "projects/omo",
    "projects/ecos",
]


def _gh(repo: str, *args: str) -> list[dict[str, Any]]:
    """Run gh CLI and return parsed JSON."""
    cmd = ["gh"]
    if repo != ".":
        cmd.extend(["-R", f"starlink-awaken/{Path(repo).name}"])
    cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return []
        return json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def _harvest_repo(repo: str, since: datetime, dry_run: bool) -> list[dict[str, Any]]:
    """Harvest merged and closed PRs from one repo since `since`."""
    results: list[dict[str, Any]] = []
    repo_name = repo if repo != "." else "omostation"

    merged = _gh(
        repo,
        "pr", "list", "--state", "merged", "--limit", "100",
        "--json", "number,title,mergedAt,author,additions,deletions,labels",
    )
    for pr in merged:
        merged_at = pr.get("mergedAt") or ""
        if merged_at:
            try:
                merge_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                if merge_dt < since:
                    continue
            except ValueError:
                pass

        results.append({
            "repo": repo_name,
            "pr_number": pr["number"],
            "title": pr.get("title", "")[:120],
            "verdict": "accepted",
            "event": "merged",
            "event_at": merged_at,
            "author": (pr.get("author") or {}).get("login", ""),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
        })

    closed = _gh(
        repo,
        "pr", "list", "--state", "closed", "--limit", "50",
        "--json", "number,title,closedAt,author",
    )
    merged_nums = {r["pr_number"] for r in results}
    for pr in closed:
        if pr["number"] in merged_nums:
            continue
        closed_at = pr.get("closedAt") or ""
        if closed_at:
            try:
                close_dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                if close_dt < since:
                    continue
            except ValueError:
                pass

        results.append({
            "repo": repo_name,
            "pr_number": pr["number"],
            "title": pr.get("title", "")[:120],
            "verdict": "rejected",
            "event": "closed_unmerged",
            "event_at": closed_at,
            "author": (pr.get("author") or {}).get("login", ""),
            "additions": 0,
            "deletions": 0,
        })

    return results


def _record(entry: dict[str, Any], dry_run: bool) -> str:
    """Record one harvested outcome to the JSONL log."""
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "pr-harvest/v1",
        "scene_id": "engineering-delivery",
        "ts": datetime.now(UTC).isoformat(),
        **entry,
    }
    if not dry_run:
        with HARVEST_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record["ts"]


def main() -> int:
    parser = argparse.ArgumentParser(description="PR Review Harvester (BET-Y1Q2-T7-01)")
    parser.add_argument("--days", type=float, default=7.0, help="Look back N days (default 7)")
    parser.add_argument("--repo", type=str, default="", help="Single repo path (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without recording")
    args = parser.parse_args()

    since = datetime.now(UTC) - timedelta(days=args.days)
    repos = [args.repo] if args.repo else REPOS

    total = 0
    for repo in repos:
        repo_path = WORKSPACE / repo if repo != "." else WORKSPACE
        if not (repo_path / ".git").exists():
            continue
        entries = _harvest_repo(repo, since, args.dry_run)
        for entry in entries:
            _record(entry, args.dry_run)
            total += 1
            tag = "[dry-run] " if args.dry_run else ""
            print(f"  {tag}{entry['repo']}#{entry['pr_number']}: {entry['verdict']} — {entry['title'][:60]}")

    print(f"\n{total} outcomes harvested ({'preview' if args.dry_run else 'recorded'})")
    if not args.dry_run and total > 0:
        print(f"Log: {HARVEST_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
