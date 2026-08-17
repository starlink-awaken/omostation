#!/usr/bin/env python3
"""Dogfood decision_outcome 采集器 — BET-Y1Q2-T7-01 (engineering-delivery shadow).

数据管道: 已 merge PR → decision_outcome/v1 (MOS agent_belief namespace)。

verdict 语义 (场景定义, PR 评审即天然 human_verdict):
  - squash merge 到 main        → human_verdict = accepted
  - review APPROVE              → accepted (如有)
  - closed unmerged             → rejected (有明确评论拒绝时)
  - 其余 (open / draft)         → 不采集

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
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / ".omo" / "state" / "dogfood-decision-outcomes.jsonl"

# 场景标识 — engineering-delivery-dogfood (BET-Y1Q2-T7-01)
SCENE_ID = "engineering-delivery-dogfood"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"cmd failed: {' '.join(cmd[:4])}…: {r.stderr[:200]}", file=sys.stderr)
        return ""
    return r.stdout


def _parse_since(spec: str) -> datetime:
    n, unit = int(spec[:-1]), spec[-1]
    delta = {"d": timedelta(days=n), "h": timedelta(hours=n), "w": timedelta(weeks=n)}[unit]
    return datetime.now(timezone.utc) - delta


def collect_merged_prs(since_spec: str) -> list[dict]:
    since = _parse_since(since_spec)
    iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = _run([
        "gh", "pr", "list", "--repo", "starlink-awaken/omostation",
        "--state", "merged", "--limit", "100", "--search", f"merged:>={iso}",
        "--json", "number,title,mergedAt,additions,deletions,files",
    ])
    if not out:
        return []
    prs = json.loads(out)
    return [p for p in prs if (p.get("mergedAt") or "") >= iso]


def _known_pr_numbers() -> set[int]:
    if not STORE.exists():
        return set()
    known = set()
    for line in STORE.read_text(encoding="utf-8").splitlines():
        try:
            known.add(json.loads(line)["payload"]["pr_number"])
        except (json.JSONDecodeError, KeyError):
            continue
    return known


def collect(since_spec: str, min_weekly: int) -> int:
    prs = collect_merged_prs(since_spec)
    known = _known_pr_numbers()
    fresh = [p for p in prs if p["number"] not in known]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    now = _utc_now()
    written = 0
    with STORE.open("a", encoding="utf-8") as fh:
        for p in fresh:
            outcome = {
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
                    "files_changed": len(p.get("files") or []),
                },
                "recorded_at": now,
                "notes": "dogfood shadow — 永不计入 X3 价值指标 (BET-Y1Q2-T7-01 non_goal)",
            }
            fh.write(json.dumps(outcome, ensure_ascii=False) + "\n")
            written += 1
    total = len(known) + written
    week = len(prs)
    print(f"dogfood: 新增 {written} 条 (去重后), 窗口内 merged PR {week} 个, 累计 {total} 条")
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
