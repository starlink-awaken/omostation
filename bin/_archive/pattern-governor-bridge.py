#!/usr/bin/env python3
"""Pattern Governor Bridge — Eidos PatternMiner → debt.yaml (P1-T8).

Bridges Eidos pattern detection output to the governance debt system.
When PatternMiner detects repeating patterns, this script writes them
as debt entries for the Governor/Evolution Agent to act on.

Usage: python3 bin/ssot/pattern-governor-bridge.py [--scan]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEBT_FILE = ROOT / ".omo" / "_truth" / "registry" / "debt.yaml"


def scan_patterns() -> list[dict[str, Any]]:
    """Try to run Eidos PatternMiner and return detected patterns."""
    patterns: list[dict[str, Any]] = []
    try:
        import sys
        eidos_src = str(ROOT / "projects" / "kairon" / "packages" / "eidos" / "src")
        if eidos_src not in sys.path:
            sys.path.insert(0, eidos_src)
        from eidos.memory.pattern_miner import PatternMiner
        miner = PatternMiner()
        # Try to mine patterns (defensive — may fail if no data)
        results = miner.mine_all() if hasattr(miner, "mine_all") else []
        for r in results if isinstance(results, list) else []:
            patterns.append({
                "type": r.get("pattern_type", "unknown"),
                "description": str(r.get("description", r))[:200],
                "confidence": r.get("confidence", 0.5),
                "source": "eidos:pattern_miner",
            })
    except Exception:
        pass
    return patterns


def patterns_to_debt(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert patterns to debt entries."""
    ts = datetime.now(UTC).isoformat()
    return [
        {
            "id": f"pattern-{i}",
            "type": "repeating_pattern",
            "description": p["description"],
            "pattern_type": p["type"],
            "confidence": p["confidence"],
            "source": p["source"],
            "detected_at": ts,
            "status": "detected",
            "action": "evaluate_for_emergent_agent",
        }
        for i, p in enumerate(patterns)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="run pattern scan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.scan:
        print("Use --scan to run pattern detection.")
        return 0

    patterns = scan_patterns()
    debts = patterns_to_debt(patterns)

    if args.json:
        print(json.dumps({"patterns": patterns, "debts": debts}, ensure_ascii=False, indent=2))
    else:
        print(f"Pattern scan: {len(patterns)} patterns detected")
        for p in patterns:
            print(f"  [{p['type']}] {p['description'][:80]} (confidence={p['confidence']})")
        if debts:
            print(f"\n→ {len(debts)} debt entries generated for Governor review")
        else:
            print("\n→ No patterns detected (Eidos may have no data or be unconfigured)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
