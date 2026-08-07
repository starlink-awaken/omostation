#!/usr/bin/env python3
"""CI runs scheduled pruner (ADR-0385 A2).

Quick bounded delete for cron: skips scan, directly starts from oldest
pages (page 301+) and deletes completed runs until failures or page limit.

Usage:
  python3 bin/ssot/prune-ci-runs-cron.py [--keep N] [--apply]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone


def gh_api(path: str) -> dict:
    proc = subprocess.run(
        ["gh", "api", "-X", "GET", path],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    return json.loads(proc.stdout)


def delete_run(run_id: int) -> bool:
    proc = subprocess.run(
        ["gh", "api", "-X", "DELETE", f"repos/starlink-awaken/omostation/actions/runs/{run_id}"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=5000, help="保留最近 N 个 runs")
    parser.add_argument("--apply", action="store_true", help="真实删除")
    parser.add_argument("--start-page", type=int, default=301, help="从第几页开始删 (每页100 runs)")
    parser.add_argument("--max-pages", type=int, default=500, help="最多扫几页")
    args = parser.parse_args()

    if not args.apply:
        print("DRY-RUN (add --apply)")
        return 0

    deleted = 0
    errors = 0
    consecutive_fail = 0

    for page in range(args.start_page, args.start_page + args.max_pages):
        data = gh_api(f"repos/starlink-awaken/omostation/actions/runs?per_page=100&page={page}")
        runs = data.get("workflow_runs", [])
        if not runs:
            break

        for run in runs:
            if run["status"] != "completed":
                continue
            if delete_run(run["id"]):
                deleted += 1
                consecutive_fail = 0
                if deleted % 100 == 0:
                    print(f"deleted {deleted}...", flush=True)
            else:
                errors += 1
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    print(f"5 consecutive API failures at page {page}, stopping")
                    break
        if consecutive_fail >= 5:
            break

    print(f"prune complete: deleted={deleted} errors={errors} scanned_pages={page - args.start_page + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
