#!/usr/bin/env python3
"""Evolution Proposal Triage — 提案质量分层与 BCOS 四阶段.

将提案分为:
- 高质量 (confidence > 0.7): 进入 BCOS 四阶段
- 中质量 (0.4-0.7): 人工审核
- 低质量 (< 0.4): 归档

Usage:
    python3 bin/bc-os/evolution-proposal-triage.py --generate
    python3 bin/bc-os/evolution-proposal-triage.py --triage
    python3 bin/bc-os/evolution-proposal-triage.py --bcos
    python3 bin/bc-os/evolution-proposal-triage.py --auto-approve
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROPOSALS_FILE = REPO / ".omo" / "state" / "evolution-proposals.json"
ARCHIVE_FILE = REPO / ".omo" / "state" / "evolution-proposals-archived.json"


def _load_proposals() -> list:
    if PROPOSALS_FILE.exists():
        try:
            return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_proposals(proposals: list) -> None:
    PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROPOSALS_FILE.write_text(json.dumps(proposals, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_proposals() -> list[dict]:
    """Generate proposals from real system data."""
    proposals = []

    # 1. Generate from heartbeat failures
    try:
        result = subprocess.run(
            ["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--json"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            hb_data = json.loads(result.stdout)
            for failure in hb_data.get("failures", []):
                proposals.append({
                    "id": f"PROP-HB-{failure['file'].replace('/', '-')}",
                    "type": "heartbeat_remediation",
                    "source": "probe-heartbeat-monitor",
                    "target": failure["file"],
                    "description": f"修复 {failure['description']}: {failure['age_hours']}h / {failure['sla_hours']}h",
                    "confidence": 0.9,  # High confidence - clear SLA violation
                    "risk": "low",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "status": "new",
                })
    except (json.JSONDecodeError, OSError):
        pass

    # 2. Generate from drift detection
    proposals.append({
        "id": "PROP-DRIFT-001",
        "type": "drift_remediation",
        "source": "drift-sweep",
        "target": "governance-checks.yaml",
        "description": "同步 script_baseline 与实际脚本数",
        "confidence": 0.8,
        "risk": "low",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "new",
    })

    return proposals


def triage_proposals(proposals: list[dict]) -> dict:
    """Triage proposals by quality."""
    high = [p for p in proposals if p.get("confidence", 0) > 0.7]
    medium = [p for p in proposals if 0.4 <= p.get("confidence", 0) <= 0.7]
    low = [p for p in proposals if p.get("confidence", 0) < 0.4]

    return {
        "high": high,
        "medium": medium,
        "low": low,
        "total": len(proposals),
    }


def run_bcos(proposals: list[dict]) -> list[dict]:
    """Run BCOS four-phase on high-quality proposals."""
    results = []
    for p in proposals:
        # BCOS: observe → propose → evaluate → approve
        observation = {"proposal": p["id"], "data": p}

        # Evaluate
        confidence = p.get("confidence", 0)
        risk = p.get("risk", "medium")
        approved = confidence > 0.8 and risk == "low"

        result = {
            **p,
            "bcos_phase": "evaluate",
            "approved": approved,
            "evaluated_at": datetime.now(UTC).isoformat(),
        }
        results.append(result)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evolution Proposal Triage")
    parser.add_argument("--generate", action="store_true", help="Generate proposals")
    parser.add_argument("--triage", action="store_true", help="Triage proposals")
    parser.add_argument("--bcos", action="store_true", help="Run BCOS on high-quality")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve high-confidence")
    parser.add_argument("--count", action="store_true", help="Count proposals")
    args = parser.parse_args()

    if args.generate:
        proposals = generate_proposals()
        existing = _load_proposals()
        existing.extend(proposals)
        _save_proposals(existing)
        print(f"✓ Generated {len(proposals)} proposals (total: {len(existing)})")
        return 0

    if args.triage:
        proposals = _load_proposals()
        triaged = triage_proposals(proposals)
        print(json.dumps({
            "total": triaged["total"],
            "high": len(triaged["high"]),
            "medium": len(triaged["medium"]),
            "low": len(triaged["low"]),
        }, indent=2))
        return 0

    if args.bcos:
        proposals = _load_proposals()
        triaged = triage_proposals(proposals)
        results = run_bcos(triaged["high"])
        approved = [r for r in results if r.get("approved")]
        print(f"✓ BCOS: {len(results)} evaluated, {len(approved)} approved")
        return 0

    if args.auto_approve:
        proposals = _load_proposals()
        approved_count = 0
        for p in proposals:
            if p.get("confidence", 0) > 0.8 and p.get("risk") == "low":
                p["status"] = "approved"
                p["approved_at"] = datetime.now(UTC).isoformat()
                approved_count += 1
        _save_proposals(proposals)
        print(f"✓ Auto-approved {approved_count} proposals")
        return 0

    if args.count:
        proposals = _load_proposals()
        print(f"Proposals: {len(proposals)}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
