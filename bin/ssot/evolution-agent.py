#!/usr/bin/env python3
"""Evolution Agent — Meta-3 进化层: 定期扫描 → 提出进化提案 (P3-T2).

Scans internal debt/problems + external research opportunities.
Produces evolution proposals for human review (S2 level: needs confirmation).

Schedule (when run periodically):
  daily: scan internal debt + health anomalies
  weekly: web research on relevant tools/frameworks
  monthly: vision alignment audit

Usage: python3 bin/ssot/evolution-agent.py [--deep]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def scan_internal() -> list[dict[str, Any]]:
    """Scan internal state for improvement opportunities."""
    proposals: list[dict[str, Any]] = []

    # 1. Run problem-detector
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "bin/ssot/problem-detector.py"), "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if result.returncode != 0 and result.stdout:
            data = json.loads(result.stdout)
            for p in data.get("problems", []):
                proposals.append({
                    "source": "problem_detector",
                    "type": p.get("type", "unknown"),
                    "severity": p.get("severity", "medium"),
                    "proposal": f"Address: {p.get('detail', p.get('type', ''))}",
                    "action": "create_debt_task",
                    "level": "S1" if p.get("severity") == "low" else "S2",
                })
    except Exception:
        pass

    # 2. Check dormant tools
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "bin/ssot/tool-usage-audit.py"), "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if result.stdout:
            data = json.loads(result.stdout)
            dormant = data.get("dormant", 0)
            if dormant > 15:
                proposals.append({
                    "source": "tool_audit",
                    "type": "excessive_dormant",
                    "severity": "low",
                    "proposal": f"Evaluate {dormant} dormant tools for retirement or activation",
                    "action": "cleanup_task",
                    "level": "S2",
                })
    except Exception:
        pass

    # 3. Check scene card coverage
    cards_dir = ROOT / "docs" / "scene-cards"
    card_count = len(list(cards_dir.glob("*.yaml"))) if cards_dir.is_dir() else 0
    if card_count < 15:
        proposals.append({
            "source": "scene_coverage",
            "type": "insufficient_cards",
            "severity": "medium",
            "proposal": f"Only {card_count} scene cards — consider adding more domain coverage",
            "action": "create_scene_cards",
            "level": "S2",
        })

    return proposals


def scan_external(*, deep: bool = False) -> list[dict[str, Any]]:
    """Scan external world for improvement opportunities (lightweight)."""
    proposals: list[dict[str, Any]] = []
    # In deep mode, would do web research. For now, return static recommendations.
    if deep:
        proposals.append({
            "source": "external_research",
            "type": "framework_evaluation",
            "severity": "low",
            "proposal": "Evaluate A2A protocol maturity for swarm implementation",
            "action": "research_task",
            "level": "S3",
        })
        proposals.append({
            "source": "external_research",
            "type": "tool_evaluation",
            "severity": "low",
            "proposal": "Evaluate Apple Health API for health-tracking connector",
            "action": "research_task",
            "level": "S2",
        })
    return proposals


def generate_proposals(*, deep: bool = False) -> dict[str, Any]:
    """Generate evolution proposals from internal + external scans."""
    ts = datetime.now(UTC).isoformat()
    internal = scan_internal()
    external = scan_external(deep=deep) if deep else []
    all_proposals = internal + external

    return {
        "schema": "evolution-proposal/v1",
        "generated_at": ts,
        "mode": "deep" if deep else "standard",
        "total_proposals": len(all_proposals),
        "internal_proposals": len(internal),
        "external_proposals": len(external),
        "by_level": {
            "S1": sum(1 for p in all_proposals if p.get("level") == "S1"),
            "S2": sum(1 for p in all_proposals if p.get("level") == "S2"),
            "S3": sum(1 for p in all_proposals if p.get("level") == "S3"),
        },
        "proposals": all_proposals,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep", action="store_true", help="include external research scan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = generate_proposals(deep=args.deep)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Evolution Agent: {result['total_proposals']} proposals ({result['by_level']})")
        for p in result["proposals"]:
            print(f"  [{p.get('level', '?'):3s}] [{p.get('severity', '?'):6s}] {p['proposal']}")
        if not result["proposals"]:
            print("  ✅ No improvement opportunities detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
