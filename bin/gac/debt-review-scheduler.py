#!/usr/bin/env python3
"""
债务定期复审调度器 (Task: 债务复审机制, 2026-09-20)

扫描债务注册表, 输出两类需要人工关注的条目:
  1. needs_reassessment — 终态 (resolved/closed) 但证据不可核
     (evidence_refs 路径全部不存在, 且无 resolution_evidence/closed_evidence 文本)
  2. overdue — 非终态条目, last_reviewed_at 超过复审间隔
     (critical=14d, high=30d, medium=60d, low=90d)

只读工具: 不写 .omo 治理状态面 (写入走 omo broker)。cron 侧仅记录日志。

Usage:
    python3 bin/gac/debt-review-scheduler.py [--json] [--root <workspace>]
退出码: 0=正常; 1=存在 needs_reassessment (--strict 时 overdue 也返回 1)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

import yaml

TERMINAL_STATES = {"resolved", "closed", "accepted", "archived", "wontfix"}
INTERVAL_DAYS = {"critical": 14, "high": 30, "medium": 60, "low": 90}


def parse_date(value: object) -> datetime | None:
    s = str(value or "").strip().strip("'\"")
    if not s or s.lower() == "null":
        return None
    s = s.replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d"):
        try:
            dt = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None


def load_items(root: Path) -> list[dict]:
    registry = root / ".omo" / "_truth" / "registry" / "debt.yaml"
    paths: list[Path] = []
    if registry.exists():
        data = yaml.safe_load(registry.read_text()) or {}
        paths = [root / ref for ref in data.get("seed_items") or []]
    if not paths:
        items_dir = root / ".omo" / "debt" / "items"
        paths = sorted(items_dir.glob("*.yaml")) if items_dir.is_dir() else []
    items = []
    for p in paths:
        if not p.exists():
            continue
        data = yaml.safe_load(p.read_text())
        if isinstance(data, dict):
            data["_file"] = str(p.relative_to(root))
            items.append(data)
    return items


def has_verifiable_evidence(item: dict, root: Path) -> bool:
    for ref in item.get("evidence_refs") or []:
        if not isinstance(ref, str):
            continue
        p = Path(ref)
        if not p.is_absolute():
            p = root / ref
        if p.exists():
            return True
    for field in ("resolution_evidence", "closed_evidence", "close_reason"):
        value = item.get(field)
        if isinstance(value, str) and value.strip() and "<pending>" not in value:
            return True
        if isinstance(value, list) and any(str(v).strip() for v in value):
            return True
    return False


def assess(items: list[dict], root: Path, now: datetime) -> dict:
    needs_reassessment, overdue = [], []
    for item in items:
        state = str(item.get("lifecycle_state") or "").strip().lower()
        iid = item.get("id") or item.get("_file")
        if state in TERMINAL_STATES:
            if not has_verifiable_evidence(item, root):
                needs_reassessment.append(
                    {
                        "id": iid,
                        "file": item.get("_file"),
                        "state": state,
                        "reason": "终态但证据不可核 (无存在的 evidence_refs 路径, 无结单文本证据)",
                    }
                )
            continue
        interval = INTERVAL_DAYS.get(str(item.get("severity") or "").lower(), 30)
        last = parse_date(item.get("last_reviewed_at")) or parse_date(item.get("opened_at"))
        if last is None:
            overdue.append(
                {
                    "id": iid,
                    "file": item.get("_file"),
                    "state": state,
                    "days_since_review": None,
                    "interval_days": interval,
                    "reason": "从未复审",
                }
            )
            continue
        days = (now - last).days
        if days > interval:
            overdue.append(
                {
                    "id": iid,
                    "file": item.get("_file"),
                    "state": state,
                    "days_since_review": days,
                    "interval_days": interval,
                    "reason": f"超过复审间隔 ({days}d > {interval}d)",
                }
            )
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "total_items": len(items),
        "needs_reassessment": needs_reassessment,
        "overdue": overdue,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="债务定期复审调度器")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", default=".", help="workspace 根目录")
    parser.add_argument("--strict", action="store_true", help="overdue 也视为失败")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    items = load_items(root)
    report = assess(items, root, datetime.now(UTC))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"债务复审报告 @ {report['generated_at']}")
        print(f"  条目总数: {report['total_items']}")
        print(f"  需重评估 (终态无实证): {len(report['needs_reassessment'])}")
        for row in report["needs_reassessment"]:
            print(f"    - {row['id']}: {row['reason']}")
        print(f"  逾期未复审: {len(report['overdue'])}")
        for row in report["overdue"]:
            print(f"    - {row['id']}: {row['reason']}")

    fail = bool(report["needs_reassessment"]) or (args.strict and bool(report["overdue"]))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
