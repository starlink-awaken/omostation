#!/usr/bin/env python3
"""Decision Inbox SLA — 决策收件箱 SLA 管理.

提升北极星 B 轴 (决策吞吐):
- 为每个决策项设置 SLA
- 逾期自动升级
- 决策吞吐度量

Usage:
    python3 bin/gac/decision-inbox-sla.py --add <title> [--priority P0|P1|P2] [--sla-hours 48]
    python3 bin/gac/decision-inbox-sla.py --list
    python3 bin/gac/decision-inbox-sla.py --escalate
    python3 bin/gac/decision-inbox-sla.py --metrics
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INBOX_FILE = REPO / ".omo" / "state" / "decision-inbox.json"
METRICS_FILE = REPO / ".omo" / "state" / "decision-sla-metrics.json"

# SLA by priority (hours)
SLA_HOURS = {"P0": 4, "P1": 24, "P2": 48, "P3": 168}


def _load_inbox() -> dict:
    if INBOX_FILE.exists():
        try:
            return json.loads(INBOX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"items": [], "version": "2.0"}


def _save_inbox(data: dict) -> None:
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INBOX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_decision(title: str, priority: str = "P2", sla_hours: int = 0, source: str = "manual") -> dict:
    """Add a decision item with SLA."""
    if not sla_hours:
        sla_hours = SLA_HOURS.get(priority, 48)

    inbox = _load_inbox()
    item_id = f"DEC-{len(inbox.get('items', [])) + 1:04d}"

    now = datetime.now(UTC)
    item = {
        "id": item_id,
        "title": title,
        "priority": priority,
        "status": "pending",
        "source": source,
        "created_at": now.isoformat(),
        "sla_due": (now + timedelta(hours=sla_hours)).isoformat(),
        "sla_hours": sla_hours,
    }

    inbox.setdefault("items", []).append(item)
    _save_inbox(inbox)

    return {"ok": True, "item": item}


def list_pending() -> list[dict]:
    """List pending decisions."""
    inbox = _load_inbox()
    pending = [i for i in inbox.get("items", []) if i.get("status") == "pending"]

    now = datetime.now(UTC)
    for item in pending:
        due = datetime.fromisoformat(item["sla_due"])
        hours_left = (due - now).total_seconds() / 3600
        item["hours_left"] = round(hours_left, 1)
        item["overdue"] = hours_left < 0

    return sorted(pending, key=lambda x: x.get("sla_due", ""))


def escalate_overdue() -> list[dict]:
    """Escalate overdue decisions."""
    inbox = _load_inbox()
    now = datetime.now(UTC)
    escalated = []

    for item in inbox.get("items", []):
        if item.get("status") != "pending":
            continue
        due = datetime.fromisoformat(item["sla_due"])
        if now > due:
            item["status"] = "escalated"
            item["escalated_at"] = now.isoformat()
            item["escalation_reason"] = f"逾期 {(now - due).total_seconds() / 3600:.1f}h"
            escalated.append(item)

    if escalated:
        _save_inbox(inbox)

    return escalated


def calculate_metrics() -> dict:
    """Calculate decision throughput metrics."""
    inbox = _load_inbox()
    items = inbox.get("items", [])

    total = len(items)
    pending = len([i for i in items if i.get("status") == "pending"])
    approved = len([i for i in items if i.get("status") == "approved"])
    rejected = len([i for i in items if i.get("status") == "rejected"])
    escalated = len([i for i in items if i.get("status") == "escalated"])

    # B axis = decisions made per month
    now = datetime.now(UTC)
    this_month = [i for i in items if i.get("created_at", "")[:7] == now.strftime("%Y-%m")]
    decisions_this_month = len([i for i in this_month if i.get("status") in ("approved", "rejected")])

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "escalated": escalated,
        "b_axis": decisions_this_month,
        "throughput_rate": round(decisions_this_month / max(len(this_month), 1) * 100, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Decision Inbox SLA")
    parser.add_argument("--add", help="Add decision item")
    parser.add_argument("--priority", default="P2", choices=["P0", "P1", "P2", "P3"])
    parser.add_argument("--sla-hours", type=int, default=0)
    parser.add_argument("--source", default="manual", help="Source of decision")
    parser.add_argument("--list", action="store_true", help="List pending")
    parser.add_argument("--escalate", action="store_true", help="Escalate overdue")
    parser.add_argument("--metrics", action="store_true", help="Show metrics")
    args = parser.parse_args()

    if args.add:
        result = add_decision(args.add, args.priority, args.sla_hours, args.source)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.list:
        pending = list_pending()
        print(json.dumps(pending, indent=2, ensure_ascii=False))
        return 0

    if args.escalate:
        escalated = escalate_overdue()
        print(f"✓ Escalated {len(escalated)} overdue decisions")
        for item in escalated:
            print(f"  - {item['id']}: {item['title']}")
        return 0

    if args.metrics:
        metrics = calculate_metrics()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
