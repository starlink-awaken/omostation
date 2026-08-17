#!/usr/bin/env python3
"""Dogfood decision_outcome 采集器 — BET-Y1Q2-T7-01 (engineering-delivery shadow).

数据管道: 已 merge PR → decision_outcome/v1 (MOS agent_belief namespace)。

verdict 语义 (场景定义, PR 评审即天然 human_verdict):
  - squash merge 到 main → human_verdict = accepted
  - 其余 (open / draft / closed-unmerged) → 不采集 (仅 merge_event 视为 accepted)

每周 ≥ 20 条 = BET-Y1Q2-T7-01 done_when 第 2 项。
本场景产出永不计入 X3 价值指标 (non_goal, 场景卡已标注)。

Usage:
  python3 bin/ssot/dogfood-collector.py --collect [--since 7d] [--min 20]
  python3 bin/ssot/dogfood-collector.py --count  # 只数条数 (周产 gate 检查)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _shared import append_jsonl, read_jsonl, utc_now

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / ".omo" / "_delivery" / "outcomes" / "dogfood-decision-outcomes.jsonl"

# 场景标识 — engineering-delivery-dogfood (BET-Y1Q2-T7-01)
SCENE_ID = "engineering-delivery-dogfood"


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"cmd failed: {' '.join(cmd[:4])}…: {r.stderr[:200]}", file=sys.stderr)
        return ""
    return r.stdout


def _parse_since(spec: str) -> datetime:
    n, unit = int(spec[:-1]), spec[-1]
    delta = {"d": timedelta(days=n), "h": timedelta(hours=n), "w": timedelta(weeks=n)}[unit]
    return datetime.now(UTC) - delta


def collect_merged_prs(since_spec: str) -> list[dict]:
    since = _parse_since(since_spec)
    iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            "starlink-awaken/omostation",
            "--state",
            "merged",
            "--limit",
            "100",
            "--search",
            f"merged:>={iso}",
            "--json",
            "number,title,mergedAt,additions,deletions,changedFiles",
        ]
    )
    if not out:
        return []
    prs = json.loads(out)
    return [p for p in prs if (p.get("mergedAt") or "") >= iso]


def _known_pr_numbers() -> set[int]:
    return {
        entry["payload"]["pr_number"]
        for entry in read_jsonl(STORE)
        if "payload" in entry and "pr_number" in entry["payload"]
    }


def collect(since_spec: str, min_weekly: int) -> int:
    prs = collect_merged_prs(since_spec)
    known = _known_pr_numbers()
    fresh = [p for p in prs if p["number"] not in known]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    for p in fresh:
        append_jsonl(
            STORE,
            {
                "schema": "decision_outcome/v1",
                "namespace": "agent_belief",
                "scene_id": SCENE_ID,
                "decision_id": f"do-dogfood-{p['number']}",
                "payload": {
                    "pr_number": p["number"],
                    "pr_title": p["title"],
                    "human_verdict": "accepted",  # squash merge = human accepted
                    "verdict_source": "merge_event",
                    "merged_at": p.get("mergedAt"),
                    "diff_size": {"additions": p.get("additions"), "deletions": p.get("deletions")},
                    "files_changed": p.get("changedFiles") or 0,
                },
                "recorded_at": now,
                "notes": "dogfood shadow — 永不计入 X3 价值指标 (BET-Y1Q2-T7-01 non_goal)",
            },
        )
    total = len(known) + len(fresh)
    week = len(prs)
    print(f"dogfood: 新增 {len(fresh)} 条 (去重后), 窗口内 merged PR {week} 个, 累计 {total} 条")
    gate = week >= min_weekly
    print(f"周产 gate (>= {min_weekly}/周): {'PASS ✅' if gate else 'FAIL ⏳ (窗口未满, 继续观察)'}")
    return 0 if gate else 1


def count_only() -> int:
    n = len(_known_pr_numbers())
    print(f"dogfood decision_outcome 累计: {n} 条 (store: {STORE})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--collect", action="store_true", help="采集 (幂等, 按 PR 号去重)")
    ap.add_argument("--count", action="store_true", help="只数累计条数")
    ap.add_argument("--since", default="7d", help="窗口 (默认 7d; 支持 h/d/w)")
    ap.add_argument("--min", type=int, default=20, help="周产 gate 门槛 (默认 20)")
    a = ap.parse_args(argv)
    if a.count:
        return count_only()
    if a.collect:
        return collect(a.since, a.min)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
