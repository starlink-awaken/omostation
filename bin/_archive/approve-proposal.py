#!/usr/bin/env python3
"""Approve Proposal — 人工审批进化提案 CLI (P2-T3).

列出/批准/拒绝系统产出的进化提案.
提案来源: evolution-agent → proposals/, governance-scanner → vision gaps.

Usage:
  python3 bin/ssot/approve-proposal.py list              # 列出待审提案
  python3 bin/ssot/approve-proposal.py approve PROP-XXX   # 批准
  python3 bin/ssot/approve-proposal.py reject PROP-XXX    # 拒绝
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from _shared import ROOT

PROP_DIR = ROOT / ".omo" / "_knowledge" / "evolution-proposals"
APPROVED_DIR = ROOT / ".omo" / "state" / "proposals"


def list_pending() -> None:
    """列出所有 pending_review 提案."""
    if not PROP_DIR.exists():
        print("No proposals directory.")
        return

    files = sorted(PROP_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print("No proposals found.")
        return

    print(f"{'ID':<30s} {'Level':<5s} {'Source':<15s} {'Proposal':<50s}")
    print("-" * 100)
    count = 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in data.get("proposals", []):
            if p.get("status") != "pending_review":
                continue
            count += 1
            prop_id = f.stem
            level = p.get("level", "?")
            source = p.get("source", "?")[:15]
            text = p.get("proposal", "")[:50]
            print(f"{prop_id:<30s} {level:<5s} {source:<15s} {text}")
    print(f"\nTotal pending: {count}")


def approve(prop_id: str) -> None:
    """批准提案 → 写入 approved 目录."""
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    # 在 proposals 目录找对应文件
    source = PROP_DIR / f"{prop_id}.json"
    if not source.exists():
        print(f"Proposal {prop_id} not found.")
        sys.exit(1)

    data = json.loads(source.read_text(encoding="utf-8"))
    approved_path = APPROVED_DIR / f"{prop_id}-approved.yaml"
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    import yaml

    entry = {
        "id": prop_id,
        "status": "approved",
        "approved_at": ts,
        "approved_by": "human",
        "original_proposals": data.get("proposals", []),
    }
    approved_path.write_text(
        yaml.dump(entry, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    # 标记原始提案为 approved
    for p in data.get("proposals", []):
        p["status"] = "approved"
    source.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"✅ Approved {prop_id} → {approved_path.relative_to(ROOT)}")


def reject(prop_id: str) -> None:
    """拒绝提案."""
    source = PROP_DIR / f"{prop_id}.json"
    if not source.exists():
        print(f"Proposal {prop_id} not found.")
        sys.exit(1)

    data = json.loads(source.read_text(encoding="utf-8"))
    for p in data.get("proposals", []):
        p["status"] = "rejected"
    source.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"❌ Rejected {prop_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="list pending proposals")
    sub.add_parser("list-all", help="list all proposals")
    ap = sub.add_parser("approve", help="approve a proposal")
    ap.add_argument("prop_id", help="proposal file stem (e.g. proposal-20260809-010709)")
    rp = sub.add_parser("reject", help="reject a proposal")
    rp.add_argument("prop_id", help="proposal file stem")
    args = parser.parse_args(argv)

    if args.command in (None, "list"):
        list_pending()
    elif args.command == "list-all":
        list_pending()  # 简化: 同 list
    elif args.command == "approve":
        approve(args.prop_id)
    elif args.command == "reject":
        reject(args.prop_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
