#!/usr/bin/env python3
"""防腐管道接线器 — 闭合 G1/G2 缺口.

G1: meta-doctor 心跳异常 → remediation-engine 修复提案
G2: meta-doctor 输出 → cockpit-inbox 推送

Usage:
    python3 bin/gac/corrosion-pipeline-connector.py --dry-run
    python3 bin/gac/corrosion-pipeline-connector.py --execute
    python3 bin/gac/corrosion-pipeline-connector.py --to-inbox
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/xiamingxing/Workspace")
META_DOCTOR = REPO / "bin" / "gac" / "meta-doctor.py"
REMEDIATION = REPO / "bin" / "gac" / "remediation-engine.py"
INBOX_PATH = REPO / ".omo" / "state" / "decision-inbox.json"


def run_meta_doctor() -> dict:
    """Run meta-doctor and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, str(META_DOCTOR), "--workspace", str(REPO)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"failed to parse meta-doctor output: {e}", "raw": result.stdout[:500]}


def convert_heartbeat_to_proposals(data: dict) -> list[dict]:
    """G1: Convert meta-doctor heartbeat failures to remediation proposals."""
    proposals = []
    for hb in data.get("heartbeat", []):
        if hb.get("ok"):
            continue
        proposals.append({
            "id": f"MDEAD-HB-{Path(hb['file']).name.upper().replace('.', '-')}",
            "type": "heartbeat_lapsed",
            "severity": "P2",
            "target": hb["file"],
            "field": hb.get("field", ""),
            "age_hours": hb.get("age_hours", 0),
            "sla_hours": hb.get("sla_hours", 0),
            "description": f"{hb['file']} 的 {hb.get('field', 'unknown')} 已过期 {hb.get('age_hours', 0):.1f}h (SLA: {hb.get('sla_hours', 0)}h)",
            "remediation": "refresh_heartbeat",
            "auto_fixable": True,
        })
    return proposals


def convert_reference_to_proposals(data: dict) -> list[dict]:
    """G1: Convert meta-doctor reference failures to remediation proposals."""
    proposals = []
    for ref in data.get("references", []):
        if ref.get("ok"):
            continue
        proposals.append({
            "id": f"MDEAD-REF-{Path(ref['target']).name.upper().replace('.', '-')}",
            "type": "reference_broken",
            "severity": "P1",
            "target": ref["target"],
            "source": ref.get("source", ""),
            "description": f"{ref.get('source', 'unknown')} 引用 {ref['target']} 失效",
            "remediation": "fix_reference",
            "auto_fixable": False,
        })
    return proposals


def push_to_cockpit_inbox(proposals: list[dict]) -> dict:
    """G2: Push anomalies to cockpit decision inbox."""
    inbox = _load_inbox()
    for p in proposals:
        item = {
            "id": p["id"],
            "title": f"[防腐] {p['description']}",
            "status": "pending",
            "source": "corrosion-pipeline",
            "severity": p.get("severity", "P2"),
            "auto_fixable": p.get("auto_fixable", False),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        # Avoid duplicates
        existing_ids = {i.get("id") for i in inbox.get("items", [])}
        if p["id"] not in existing_ids:
            inbox.setdefault("items", []).append(item)
    _save_inbox(inbox)
    return {"ok": True, "pushed": len(proposals), "total": len(inbox.get("items", []))}


def _load_inbox() -> dict:
    if INBOX_PATH.exists():
        try:
            return json.loads(INBOX_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"items": [], "version": "1.0"}


def _save_inbox(data: dict) -> None:
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="防腐管道接线器 (G1/G2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--execute", action="store_true", help="Execute remediation proposals")
    parser.add_argument("--to-inbox", action="store_true", help="Push anomalies to cockpit inbox")
    args = parser.parse_args()

    # 1. Run meta-doctor
    data = run_meta_doctor()
    if not data.get("ok", True):
        print(f"[WARN] meta-doctor returned ok=false: {data.get('error', 'unknown')}")

    # 2. Convert to proposals (G1)
    hb_proposals = convert_heartbeat_to_proposals(data)
    ref_proposals = convert_reference_to_proposals(data)
    all_proposals = hb_proposals + ref_proposals

    print(f"防腐管道接线器 — {datetime.now(timezone.utc).isoformat()}")
    print(f"  心跳异常: {len(hb_proposals)}")
    print(f"  引用失效: {len(ref_proposals)}")
    print(f"  总提案数: {len(all_proposals)}")

    if args.dry_run:
        for p in all_proposals:
            print(f"  [DRY-RUN] {p['id']}: {p['description']}")
        return 0

    # 3. Push to cockpit inbox (G2)
    if args.to_inbox or args.execute:
        result = push_to_cockpit_inbox(all_proposals)
        print(f"  收件箱推送: {result['pushed']} 项 (总计: {result['total']})")

    # 4. Output proposals for remediation-engine (G1)
    if args.execute:
        proposal_file = REPO / ".omo" / "state" / "corrosion-proposals.json"
        proposal_file.write_text(json.dumps(all_proposals, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  提案已写入: {proposal_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
