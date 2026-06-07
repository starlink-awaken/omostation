#!/usr/bin/env python3
"""
eCOS v5 — 定时任务状态查询 (task-status)
=============================================
读取 task-index.json 和 runlog，输出任务看板。
Phase 8.3+ / DEBT-006 台账治理

用法:
    python3 task-status.py                  # 全部任务看板
    python3 task-status.py --category daily # 按类别筛选
    python3 task-status.py --stale          # 只显示逾期未运行的任务
    python3 task-status.py --json           # JSON 输出
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

DOCS = Path.home() / "Documents"
INDEX_PATH = DOCS / "驾驶舱" / "CARDS" / "daemon-logs" / "task-index.json"
RUNLOG_PATH = DOCS / "驾驶舱" / "CARDS" / "daemon-logs" / "task-runlog.md"


def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {"count": 0, "tasks": []}
    with open(INDEX_PATH) as f:
        return json.load(f)


def main():
    args = set(sys.argv[1:])
    index = load_index()
    tasks = index.get("tasks", [])

    if "--json" in args:
        print(json.dumps(index, indent=2, ensure_ascii=False))
        return

    # Category filter
    category = None
    for a in args:
        if a.startswith("--category="):
            category = a.split("=", 1)[1]
            break

    # Classify and filter
    now = datetime.now(timezone.utc)
    filtered = []
    for t in tasks:
        name = t["name"]
        if "daily" in name:
            cat = "daily"
        elif "weekly" in name or any(d in name for d in ["monday", "wednesday", "friday"]):
            cat = "weekly"
        elif "monthly" in name or "quarterly" in name:
            cat = "monthly"
        elif "sync" in name:
            cat = "sync"
        elif "fetch" in name or "caiji" in name:
            cat = "fetch"
        elif "check" in name or "health" in name:
            cat = "health"
        else:
            cat = "other"

        t["_category"] = cat
        if category and cat != category:
            continue
        filtered.append(t)

    print(f"\n═══ 定时任务看板 ═══")
    print(f"总计: {len(tasks)} 个任务 | 筛选: {category or '全部'} | 更新: {index.get('updated', '?')[:19]}")
    print()

    # Category summary
    cats = {}
    for t in tasks:
        cats.setdefault(t["_category"], []).append(t)
    for cat in sorted(cats):
        names = cats[cat]
        print(f"  [{cat:10s}] {len(names):2d} 个")

    print(f"\n{'任务':35s} {'类别':8s} {'大小':>6s} {'最后修改':12s}")
    print("-" * 70)
    for t in filtered:
        mtime = t["mtime"][:10] if t["mtime"] else "?"
        print(f"  {t['name']:33s} {t['_category']:8s} {t['size']:5d}B  {mtime}")

    # Stale check
    if "--stale" in args:
        print(f"\n── 逾期检查 ──")
        stale_count = 0
        for t in tasks:
            mtime = t.get("mtime", "")
            if mtime:
                dt = datetime.fromisoformat(mtime)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = (now - dt).days
                if t["_category"] == "daily" and days > 2:
                    print(f"  🔴 {t['name']}: {days}d 未更新 (daily任务)")
                    stale_count += 1
                elif t["_category"] == "weekly" and days > 10:
                    print(f"  🟡 {t['name']}: {days}d 未更新 (weekly任务)")
                    stale_count += 1
        if stale_count == 0:
            print(f"  ✅ 无逾期任务")
    print()


if __name__ == "__main__":
    main()
