#!/usr/bin/env python3
"""CI workflow runs 清理工具 (ADR-0383).

GitHub repo 达到 40000 runs 保留上限后, check-suite 计算 (cursor queue)
会间歇性卡死 (PR 新 head 无任何 checks), 需要人工换新分支重建 PR.
治本: 定期清理旧 completed runs, 保持 runs 数量远离上限.

注意: GitHub Actions 的 GITHUB_TOKEN 无法删除 workflow runs
(需要更高的 actions 权限), 因此本工具通过 gh CLI (用户级 token) 执行.

用法:
  python3 bin/ssot/prune-ci-runs.py --dry-run          # 预览将删除的 runs
  python3 bin/ssot/prune-ci-runs.py --before 2026-08-01  # 删除指定日期前 completed runs
  python3 bin/ssot/prune-ci-runs.py --keep 5000          # 保留最近 5000 个 runs, 删除更旧的
  python3 bin/ssot/prune-ci-runs.py --status 40000        # 目标: 删到剩余 ~40000-keep

安全: 仅删除 status=completed 的 runs; --dry-run 默认开; 真实删除需 --apply.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone


def gh_api(method: str, path: str, retries: int = 3) -> dict:
    import time

    for attempt in range(retries):
        proc = subprocess.run(
            ["gh", "api", "-X", method, path],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            if not proc.stdout.strip():
                return {}
            return json.loads(proc.stdout)
        if attempt < retries - 1:
            time.sleep(2 * (attempt + 1))
    if method != "DELETE":
        raise RuntimeError(f"gh api {method} {path} failed: {proc.stderr[:200]}")
    return {}


def list_runs(page: int = 1, per_page: int = 100, created_before: str = "") -> list[dict]:
    query = f"per_page={per_page}&page={page}"
    if created_before:
        query += f"&created<{created_before}"
    data = gh_api("GET", f"repos/starlink-awaken/omostation/actions/runs?{query}")
    return data.get("workflow_runs", [])


def delete_run(run_id: int) -> bool:
    proc = subprocess.run(
        ["gh", "api", "-X", "DELETE", f"repos/starlink-awaken/omostation/actions/runs/{run_id}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True, help="只预览 (默认)")
    parser.add_argument("--apply", action="store_true", help="真实删除 (需配合 --dry-run 关闭)")
    parser.add_argument("--before", type=str, default="", help="删除该日期前 (UTC, YYYY-MM-DD) 的 completed runs")
    parser.add_argument("--keep", type=int, default=0, help="保留最近 N 个 runs, 删除更旧的 completed runs")
    args = parser.parse_args()

    if not args.apply:
        print("DRY-RUN 模式 (加 --apply 真实删除)")
    else:
        args.dry_run = False

    if args.before:
        cutoff = datetime.fromisoformat(args.before + "T00:00:00+00:00")
    else:
        cutoff = None
    keep = args.keep

    total = 0
    kept = 0
    deleted = 0
    failed = 0
    page = 1
    api_cutoff = args.before + "T00:00:00Z" if args.before else ""
    while True:
        runs = list_runs(page, created_before=api_cutoff)
        if not runs:
            break
        for run in runs:
            total += 1
            if run["status"] != "completed":
                continue
            created = run.get("created_at", "")
            if cutoff:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if created_dt >= cutoff:
                    kept += 1
                    continue
            elif keep:
                if kept < keep:
                    kept += 1
                    continue
            if args.dry_run:
                print(f"[dry-run] would delete #{run['id']} {run.get('name')} {created}")
                deleted += 1
            else:
                if delete_run(run["id"]):
                    deleted += 1
                    if deleted % 50 == 0:
                        print(f"deleted {deleted}...")
                else:
                    failed += 1
        if len(runs) < 100:
            break
        page += 1
        if page > 200:
            print("page limit reached; stopping")
            break

    print(f"\ntotal scanned={total} kept={kept} deleted={deleted} failed={failed}")
    print("提示: 删除后 GitHub 会自动滚动, 新 runs 才能正常调度 (cursor queue 不卡).")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
